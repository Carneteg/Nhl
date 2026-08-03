"""Official NHL roster sync and public CapWages contract enrichment.

The league import intentionally uses season statistics as the authoritative list
of players who belonged to an NHL club during the selected season.  The roster
endpoint is merged in because it supplies sweater/biographical fields.  A player
landing request fills any missing identity fields.  No contract value is inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from .db import json_dump, stable_player_id

NHL_API = "https://api-web.nhle.com/v1"
CAPWAGES = "https://capwages.com"
USER_AGENT = "NHL-GM-Simulation/2.0 (+local educational project; respectful cached importer)"
NHL_TEAMS = ("ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WSH", "WPG")


class SourceError(RuntimeError):
    pass


class CachedHttpClient:
    def __init__(self, cache: Path, delay: float, retries: int = 3):
        self.cache, self.delay, self.retries = Path(cache), delay, retries
        self.cache.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0

    def get_bytes(self, url: str, force: bool = False) -> bytes:
        key = hashlib.sha256(url.encode()).hexdigest()
        target = self.cache / key
        if target.exists() and not force:
            return target.read_bytes()
        for attempt in range(self.retries):
            try:
                wait = self.delay - (time.monotonic() - self._last_request)
                if wait > 0:
                    time.sleep(wait)
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read()
                self._last_request = time.monotonic()
                target.write_bytes(body)
                return body
            except (OSError, urllib.error.HTTPError) as exc:
                if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 404}:
                    # Access restrictions are authoritative. Never retry as a way
                    # to work around authentication, bot protection or denial.
                    raise SourceError(f"HTTP {exc.code} for {url}") from exc
                if attempt + 1 == self.retries:
                    raise SourceError(f"request failed for {url}: {exc}") from exc
                time.sleep(2**attempt)
        raise AssertionError("unreachable")


class NHLClient(CachedHttpClient):
    def __init__(self, cache=Path("data/cache/nhl"), delay=0.12, retries=3):
        super().__init__(cache, delay, retries)

    def get(self, endpoint: str, force: bool = False):
        url = f"{NHL_API}/{endpoint.lstrip('/')}"
        try:
            data = json.loads(self.get_bytes(url, force))
        except json.JSONDecodeError as exc:
            raise SourceError(f"invalid JSON from {url}") from exc
        if not isinstance(data, (dict, list)):
            raise SourceError(f"unexpected NHL payload from {url}")
        return data, url


class CapWagesClient(CachedHttpClient):
    def __init__(self, cache=Path("data/cache/capwages"), delay=0.2, retries=3):
        super().__init__(cache, delay, retries)

    def player(self, slug: str, force: bool = False):
        url = f"{CAPWAGES}/players/{slug}"
        html = self.get_bytes(url, force).decode("utf-8", "replace")
        return parse_capwages_page(html), url


def _text(value):
    if isinstance(value, dict):
        return value.get("default") or next(iter(value.values()), None)
    return value


def source_record(db, source, url, endpoint, payload, confidence="HIGH", parser="nhl-api-v2"):
    now = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(json_dump(payload).encode()).hexdigest()
    db.execute("""INSERT OR IGNORE INTO source_records
      (source,source_url,endpoint,fetched_at,verified_at,parser_version,confidence,payload_hash)
      VALUES(?,?,?,?,?,?,?,?)""", (source, url, endpoint, now, now, parser, confidence, digest))
    return db.execute("SELECT id FROM source_records WHERE source_url=? AND payload_hash=?", (url, digest)).fetchone()[0]


def queue_unknown(db, entity_type, entity_id, field, reason, source_url=None):
    db.execute("""INSERT OR IGNORE INTO verification_queue
      (entity_type,entity_id,field,reason,source_url,created_at) VALUES(?,?,?,?,?,?)""",
      (entity_type, entity_id, field, reason, source_url, datetime.now(timezone.utc).isoformat()))


def player_slug(name: str) -> str:
    # CapWages uses first-last, lower-case ASCII slugs.
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def parse_capwages_page(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise SourceError("CapWages page structure changed: __NEXT_DATA__ missing")
    try:
        page = json.loads(match.group(1))["props"]["pageProps"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SourceError("CapWages page structure changed: player payload missing") from exc
    if not isinstance(page.get("player"), dict):
        raise SourceError("CapWages page structure changed: player missing")
    return page["player"]


def contract_for_season(player: dict, season_label: str):
    for contract in player.get("contracts") or []:
        for detail in contract.get("details") or []:
            if detail.get("season") == season_label:
                seasons = [d.get("season") for d in contract.get("details", []) if d.get("season")]
                return contract, detail, min(seasons), max(seasons)
    return None


def dollars(value):
    if value in (None, "", "UNKNOWN"):
        return None
    cleaned = re.sub(r"[^0-9.-]", "", str(value))
    return int(float(cleaned)) if cleaned else None


def _upsert_player(db, team, raw, detail, source_id, roster_status="ACTIVE"):
    nhl_id = raw.get("id") or raw.get("playerId")
    first = _text((detail or raw).get("firstName")) or _text(raw.get("firstName")) or ""
    last = _text((detail or raw).get("lastName")) or _text(raw.get("lastName")) or ""
    name = f"{first} {last}".strip()
    if not nhl_id or not name:
        return None
    dob = (detail or {}).get("birthDate") or raw.get("birthDate")
    born = date.fromisoformat(dob) if dob else None
    start = date(2025, 7, 1)
    age = start.year - born.year - ((start.month, start.day) < (born.month, born.day)) if born else None
    pid = stable_player_id(nhl_id, name, dob)
    pos = raw.get("positionCode") or (detail or {}).get("position") or "UNKNOWN"
    db.execute("""INSERT INTO players
      (id,nhl_player_id,source_ids,full_name,date_of_birth,age_at_start,nationality,shoots_catches,primary_position,
       height_cm,weight_kg,real_team_id,level,roster_status,jersey_number,source_record_id,confidence)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET full_name=excluded.full_name,date_of_birth=excluded.date_of_birth,
       nationality=excluded.nationality,shoots_catches=excluded.shoots_catches,
       primary_position=excluded.primary_position,height_cm=excluded.height_cm,weight_kg=excluded.weight_kg,
       real_team_id=excluded.real_team_id,level='NHL',roster_status=excluded.roster_status,jersey_number=excluded.jersey_number,
       source_record_id=excluded.source_record_id,confidence='HIGH'""",
      (pid, nhl_id, json_dump({"nhl": nhl_id}), name, dob, age, (detail or {}).get("birthCountry"),
       (detail or {}).get("shootsCatches"), pos, (detail or {}).get("heightInCentimeters"),
       (detail or {}).get("weightInKilograms"), team, "NHL", roster_status, raw.get("sweaterNumber"), source_id, "HIGH"))
    for field in ("date_of_birth", "nationality"):
        if not {"date_of_birth": dob, "nationality": (detail or {}).get("birthCountry")}[field]:
            queue_unknown(db, "player", pid, field, "Official NHL response did not provide the field")
    return pid, name


def sync_team_roster(db, team="EDM", season="20252026", dry_run=False, force=False, client=None,
                     contract_client=None, contracts=True, commit=True):
    nhl = client or NHLClient()
    stats, stats_url = nhl.get(f"club-stats/{team}/{season}/2", force)
    roster, roster_url = nhl.get(f"roster/{team}/{season}", force)
    stats_src = source_record(db, "NHL Official API", stats_url, f"club-stats/{team}/{season}/2", stats)
    roster_src = source_record(db, "NHL Official API", roster_url, f"roster/{team}/{season}", roster)
    roster_by_id = {p["id"]: p for group in roster.values() if isinstance(group, list) for p in group if p.get("id")}
    season_players = {p["playerId"]: p for group in (stats.get("skaters", []), stats.get("goalies", [])) for p in group}
    # Players listed on the season roster but without a game are still members of the organization.
    for player_id, value in roster_by_id.items():
        season_players.setdefault(player_id, value)
    db.execute("INSERT OR IGNORE INTO teams(id,league,name,abbreviation) VALUES(?,?,?,?)", (team, "NHL", team, team))
    counts = {"team": team, "players": 0, "contracts": 0, "unknown_contracts": 0, "conflicts": 0}
    cap = contract_client or CapWagesClient()
    label = f"{season[:4]}-{season[6:]}"
    for nhl_id, raw in season_players.items():
        detail = roster_by_id.get(nhl_id)
        if not detail or not detail.get("birthDate"):
            try:
                detail, detail_url = nhl.get(f"player/{nhl_id}/landing", force)
                source_record(db, "NHL Official API", detail_url, f"player/{nhl_id}/landing", detail)
            except SourceError:
                detail = detail or {}
        source_id = roster_src if nhl_id in roster_by_id else stats_src
        existing = db.execute("SELECT id,real_team_id,roster_status FROM players WHERE nhl_player_id=?", (nhl_id,)).fetchone()
        resolved_team = team
        if existing and existing["real_team_id"] and existing["real_team_id"] != team:
            # Season stats legitimately include traded players.  A roster-endpoint
            # membership outranks stats-only evidence; otherwise keep the first
            # assignment and expose the ambiguity instead of silently moving him.
            if nhl_id not in roster_by_id:
                resolved_team = existing["real_team_id"]
            db.execute("""INSERT INTO data_conflicts
              (entity_type,entity_id,field,old_value,new_value,old_source,new_source,priority_old,priority_new,recommendation,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              ("player", existing["id"], "real_team_id", existing["real_team_id"], team,
               "previous 2025-26 team evidence", roster_url if nhl_id in roster_by_id else stats_url,
               3, 3 if nhl_id in roster_by_id else 2,
               "Review dated official transaction/opening roster; season membership retained for both clubs",
               datetime.now(timezone.utc).isoformat()))
            counts["conflicts"] += 1
        roster_status = "ACTIVE" if nhl_id in roster_by_id or (existing and existing["roster_status"] == "ACTIVE") else "HISTORICAL"
        result = _upsert_player(db, resolved_team, raw, detail, source_id, roster_status)
        if not result:
            continue
        pid, name = result
        db.execute("""INSERT OR REPLACE INTO season_roster_memberships
          (player_id,team_id,season,evidence,source_record_id) VALUES(?,?,?,?,?)""",
          (pid, team, season, "NHL_ROSTER" if nhl_id in roster_by_id else "NHL_SEASON_STATS", source_id))
        counts["players"] += 1
        if not contracts:
            continue
        try:
            cap_player, cap_url = cap.player(player_slug(name), force)
            found = contract_for_season(cap_player, label)
            cap_src = source_record(db, "CapWages public player page", cap_url, "next-data/contracts", cap_player, "MEDIUM", "capwages-next-data-v1")
            if not found:
                raise SourceError(f"no {label} contract on public player page")
            contract, detail_row, start, end = found
            hit, salary = dollars(detail_row.get("capHit") or contract.get("aav")), dollars(detail_row.get("totalSalary"))
            if hit is None:
                raise SourceError(f"no {label} cap hit on public player page")
            expiry = contract.get("expiryStatus") or "UNKNOWN"
            clause = detail_row.get("clause") or ""
            db.execute("""INSERT INTO contracts
              (player_id,team_id,start_season,end_season,cap_hit,salary,contract_type,one_two_way,
               expiry_status,nmc,ntc,verification_status,source_record_id)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(player_id,team_id,start_season) DO UPDATE SET end_season=excluded.end_season,
               cap_hit=excluded.cap_hit,salary=excluded.salary,contract_type=excluded.contract_type,
               expiry_status=excluded.expiry_status,nmc=excluded.nmc,ntc=excluded.ntc,
               verification_status=excluded.verification_status,source_record_id=excluded.source_record_id""",
              (pid, team, int(start[:4]), int(end[:4]), hit, salary, contract.get("type"), "UNKNOWN", expiry,
               int("NMC" in clause), clause if "NTC" in clause else None, "SECONDARY_VERIFIED", cap_src))
            queue_unknown(db, "contract", pid, "one_two_way",
                          "Public contract source does not expose a reliable one-way/two-way field", cap_url)
            if expiry == "UNKNOWN":
                queue_unknown(db, "contract", pid, "expiry_status",
                              "Public contract source did not expose expiry status", cap_url)
            counts["contracts"] += 1
        except SourceError as exc:
            counts["unknown_contracts"] += 1
            queue_unknown(db, "contract", pid, "cap_hit", str(exc), f"{CAPWAGES}/players/{player_slug(name)}")
    if dry_run:
        db.rollback()
    elif commit:
        db.commit()
    return counts


def reset_real_baseline(db):
    """Archive simulations/locks and remove imported real-world roster facts."""
    db.execute("UPDATE simulation_state SET active=0 WHERE active=1")
    db.execute("UPDATE source_records SET overridden_by_canon=0")
    db.execute("DELETE FROM canon_locks")
    db.execute("DELETE FROM roster_assignments")
    db.execute("DELETE FROM simulation_players")
    db.execute("DELETE FROM contracts")
    db.execute("DELETE FROM season_roster_memberships")
    db.execute("DELETE FROM data_conflicts")
    db.execute("UPDATE players SET real_team_id=NULL,level='PROSPECT',roster_status='UNKNOWN' WHERE nhl_player_id IS NOT NULL")
    db.execute("DELETE FROM verification_queue")


def sync_league(db, season="20252026", teams=None, dry_run=False, force=False, contracts=True,
                client=None, contract_client=None, reset=True):
    teams = list(teams or NHL_TEAMS)
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO sync_runs VALUES(?,?,?,?,?,?,?,?)", (run_id, started, None, season, ",".join(teams), int(dry_run), "RUNNING", None))
    if reset:
        reset_real_baseline(db)
    results = []
    for team in teams:
        results.append(sync_team_roster(db, team, season, False, force, client, contract_client, contracts, False))
    summary = {"run_id": run_id, "season": season, "dry_run": dry_run, "teams": results,
               "totals": {key: sum(r[key] for r in results) for key in ("players", "contracts", "unknown_contracts", "conflicts")}}
    db.execute("UPDATE sync_runs SET finished_at=?,status=?,summary=? WHERE id=?",
               (datetime.now(timezone.utc).isoformat(), "DRY_RUN" if dry_run else "COMPLETE", json_dump(summary), run_id))
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return summary
