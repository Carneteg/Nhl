from pathlib import Path

from nhlgm.web import NAV
from nhlgm.db import migrate


def test_web_ui_is_english_and_valid_utf8():
    expected = {"Overview", "Inbox", "News", "Roster", "Lines", "Games", "Stats", "Contracts",
                "Cap", "Injuries", "Waivers", "AHL / Farm Team", "Prospects", "Scouting", "Draft",
                "Free Agency", "Trades", "Staff", "Coach", "Owner", "League", "Other Teams",
                "Other GMs", "History", "Settings"}
    assert {label for _, label in NAV} == expected
    root = Path(__file__).resolve().parents[1]
    content = "\n".join((root / path).read_text(encoding="utf-8") for path in ("web/index.html", "web/app.js"))
    server_source = (root / "nhlgm/web.py").read_text(encoding="utf-8")
    assert '<html lang="en">' in content
    assert "Advance one day" in content
    assert "Ã" not in content
    assert "charset=utf-8" in server_source
    assert "format(number || 0)" not in content
    assert "US$0" not in content
    assert "expiry_status || 'UNKNOWN'" not in content


def test_migration_translates_persisted_swedish_messages(db):
    db.execute("INSERT INTO inbox(sender,subject,content,actions) VALUES(?,?,?,?)",
               ("Huvudtränaren", "Första rostermötet", "Vi behöver fastställa kedjor och special teams inför camp.", '["Öppna"]'))
    db.execute("INSERT INTO news(headline,body) VALUES(?,?)",
               ("Ny Edmonton-simulation skapad", "Den verkliga baslinjen kopierades 2025-07-01."))
    db.commit()
    migrate(db)
    message = db.execute("SELECT sender,subject,content,actions FROM inbox").fetchone()
    assert tuple(message) == ("Head Coach", "First roster meeting", "We need to set our lines and special-teams units before camp.", '["Open","Delegate","Postpone"]')
    news = db.execute("SELECT headline,body FROM news").fetchone()
    assert news[0] == "New Edmonton simulation created"
    assert "real-world baseline" in news[1]
