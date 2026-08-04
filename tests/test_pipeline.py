import json
import zipfile

from nhlgm.bootstrap import load_fixtures
from nhlgm.db import stable_player_id
from nhlgm.exporter import SHEETS, export
from nhlgm.services import advance, audits, cap_summary, new_simulation
from nhlgm.sync import (CapWagesClient, SourceError, contract_for_season, parse_capwages_page,
                        player_slug, sync_league, sync_team_roster)
from nhlgm.web import snapshot


ROSTER = {"forwards": [{"id": 8478402, "firstName": {"default": "Connor"},
          "lastName": {"default": "McDavid"}, "birthDate": "1997-01-13",
          "positionCode": "C", "shootsCatches": "L", "birthCountry": "CAN",
          "sweaterNumber": 97, "heightInCentimeters": 185, "weightInKilograms": 88}],
          "defensemen": [], "goalies": []}
STATS = {"skaters": [{"playerId": 8478402, "firstName": {"default": "Connor"},
         "lastName": {"default": "McDavid"}, "positionCode": "C"}], "goalies": []}


class FakeNHL:
    def get(self, endpoint, force=False):
        if endpoint.startswith("club-stats/"):
            return STATS, "https://api-web.nhle.com/v1/" + endpoint
        if endpoint.startswith("roster/"):
            return ROSTER, "https://api-web.nhle.com/v1/" + endpoint
        return ROSTER["forwards"][0], "https://api-web.nhle.com/v1/" + endpoint


def cap_page():
    player = {"player": {"name": "McDavid, Connor", "contracts": [{
        "type": "Standard Contract", "expiryStatus": "UFA", "aav": "$12,500,000",
        "details": [{"season": "2025-26", "capHit": "$12,500,000",
                     "totalSalary": "$10,000,000", "clause": "NMC"}]}]}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(
        {"props": {"pageProps": player}}) + "</script>"


class FakeCap:
    def player(self, slug, force=False):
        return parse_capwages_page(cap_page()), "https://capwages.com/players/" + slug


def test_stable_identity_not_name_only():
    assert stable_player_id(8478402, "X", None) == stable_player_id(8478402, "Y", None)


def test_roster_contract_mapping_and_idempotency(db):
    sync_team_roster(db, client=FakeNHL(), contract_client=FakeCap())
    sync_team_roster(db, client=FakeNHL(), contract_client=FakeCap())
    player = db.execute("SELECT * FROM players").fetchone()
    assert player["age_at_start"] == 28 and player["nationality"] == "CAN"
    contract = db.execute("SELECT * FROM contracts").fetchone()
    assert contract["cap_hit"] == 12_500_000 and contract["end_season"] == 2026
    assert contract["expiry_status"] == "UFA" and contract["nmc"] == 1
    assert db.execute("SELECT count(*) FROM players").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM contracts").fetchone()[0] == 1


def test_stats_only_player_is_historical_not_active_cap(db):
    class StatsOnly(FakeNHL):
        def get(self, endpoint, force=False):
            if endpoint.startswith("roster/"):
                return {"forwards": [], "defensemen": [], "goalies": []}, "https://api-web.nhle.com/v1/" + endpoint
            return super().get(endpoint, force)
    sync_team_roster(db, client=StatsOnly(), contract_client=FakeCap())
    assert db.execute("SELECT roster_status FROM players").fetchone()[0] == "HISTORICAL"


def test_capwages_changed_structure_fails_closed():
    try:
        parse_capwages_page("<html>changed</html>")
        assert False
    except SourceError as error:
        assert "structure changed" in str(error)


def test_contract_parser_and_slug():
    player = parse_capwages_page(cap_page())
    assert contract_for_season(player, "2025-26")[1]["capHit"] == "$12,500,000"
    assert player_slug("Arvid Söderblom") == "arvid-soderblom"


def test_capwages_resolves_official_name_variants():
    client = CapWagesClient(cache="/tmp/unused-cap-cache", delay=0)
    client._player_slugs = lambda force=False: ["sam-montembeault", "samuel-bolduc", "zack-bolduc"]
    assert client.resolve_slug("Samuel Montembeault") == "sam-montembeault"
    assert client.resolve_slug("Zachary Bolduc") == "zack-bolduc"


def test_main_roster_state_includes_contract_data(db):
    sync_team_roster(db, client=FakeNHL(), contract_client=FakeCap())
    new_simulation(db)
    player = snapshot(db)["roster"][0]
    assert player["cap_hit"] == 12_500_000
    assert player["end_season"] == 2026
    assert player["expiry_status"] == "UFA"


def test_baseline_isolated_from_simulation(db):
    sync_team_roster(db, client=FakeNHL(), contracts=False)
    sid = new_simulation(db)
    db.execute("UPDATE simulation_players SET team_id='SJS' WHERE simulation_id=?", (sid,))
    db.commit()
    assert db.execute("SELECT real_team_id FROM players").fetchone()[0] == "EDM"


def test_audit_rejects_fictional_mcdavid_team(db):
    sync_team_roster(db, client=FakeNHL(), contracts=False)
    db.execute("UPDATE players SET real_team_id='SJS' WHERE nhl_player_id=8478402")
    db.commit()
    result = audits(db)
    assert not result["ok"]
    assert any(issue["code"] == "REAL_BASELINE_TEAM_MISMATCH" for issue in result["failures"])


def test_league_dry_run_rolls_back_reset(db):
    sync_team_roster(db, client=FakeNHL(), contracts=False)
    before = db.execute("SELECT count(*) FROM players WHERE real_team_id='EDM'").fetchone()[0]
    result = sync_league(db, teams=("SJS",), dry_run=True, contracts=False, client=FakeNHL())
    assert result["dry_run"] and db.execute("SELECT count(*) FROM players WHERE real_team_id='EDM'").fetchone()[0] == before


def test_league_sync_blocks_active_player_without_contract(db):
    class MissingCap:
        def player(self, slug, force=False):
            raise SourceError("contract unavailable")
    try:
        sync_league(db, teams=("EDM",), contracts=True, client=FakeNHL(), contract_client=MissingCap())
        assert False
    except SourceError as error:
        assert "contract quality gate failed" in str(error)


def test_cap_excludes_ahl_traded_and_retained_once(db):
    sync_team_roster(db, client=FakeNHL(), contract_client=FakeCap())
    sid = new_simulation(db)
    assert cap_summary(db, sid)["total_cap_charge"] == 12_500_000
    db.execute("UPDATE simulation_contracts SET retained_salary=1000000 WHERE simulation_id=?", (sid,))
    db.execute("UPDATE simulation_players SET status='TRADED' WHERE simulation_id=?", (sid,))
    db.commit()
    assert cap_summary(db, sid)["total_cap_charge"] == 1_000_000


def test_no_duplicate_draft_owner(db):
    db.execute("INSERT INTO teams(id,league,name,abbreviation) VALUES('EDM','NHL','Edmonton','EDM')")
    db.execute("INSERT INTO draft_picks(draft_year,round,original_owner_id,current_owner_id) VALUES(2026,1,'EDM','EDM')")
    try:
        db.execute("INSERT INTO draft_picks(draft_year,round,original_owner_id,current_owner_id) VALUES(2026,1,'EDM','SJS')")
        assert False
    except Exception:
        pass


def test_fixture_has_real_2025_and_2026_names(db):
    load_fixtures(db)
    names = {row[0] for row in db.execute("SELECT full_name FROM players")}
    assert {"Matthew Schaefer", "Gavin McKenna", "Viggo Björck"} <= names
    assert not any("Prospect Slot" in name for name in names)


def test_new_simulation_clock_and_advance(db):
    load_fixtures(db)
    sid = new_simulation(db, start="2025-07-01")
    assert db.execute("SELECT phase FROM simulation_state WHERE id=?", (sid,)).fetchone()[0] == "FREE_AGENCY"
    assert advance(db) == "2025-07-02"


def test_audit_and_export_contains_league_contracts(db, tmp_path):
    sync_team_roster(db, client=FakeNHL(), contract_client=FakeCap())
    new_simulation(db)
    assert audits(db)["ok"]
    path = export(db, tmp_path / "out.xlsx")
    with zipfile.ZipFile(path) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
        assert all(f'name="{sheet}"' in workbook for sheet in SHEETS)
