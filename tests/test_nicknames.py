import json
import sqlite3
from pathlib import Path

from sigexport import data, utils


def make_cursor(conv_json: dict) -> sqlite3.Cursor:
    """A minimal in-memory stand-in for the Signal DB with one contact."""
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE conversations "
        "(type, id, serviceId, e164, name, profileName, members, json)"
    )
    cur.execute(
        "CREATE TABLE messages (conversationId, type, json, id, body, "
        "sourceServiceId, timestamp, sent_at, serverTimestamp, hasAttachments, "
        "readStatus, seenStatus, expireTimer)"
    )
    cur.execute("CREATE TABLE sessions (ourServiceId)")
    cur.execute(
        "CREATE TABLE callsHistory "
        "(callId, direction, status, type, timestamp, endedTimestamp)"
    )
    cur.execute(
        "INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
        ("private", "c1", "sid1", None, None, "KC", None, json.dumps(conv_json)),
    )
    cur.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("c1", "incoming", json.dumps({}), "m1", "hi", None, 1, 1000, None, 0, None, None, None),
    )
    cur.execute("INSERT INTO sessions VALUES (?)", ("sid1",))
    con.commit()
    return cur


def contact_name(nicknames: bool, conv_json: dict) -> str | None:
    cur = make_cursor(conv_json)
    _, contacts, _ = data.fetch_data(
        Path("/unused"),
        cur,
        chats="",
        include_empty=False,
        include_disappearing=False,
        nicknames=nicknames,
    )
    return contacts["c1"].name


def test_fetch_data_uses_nickname_when_enabled() -> None:
    assert contact_name(True, {"nicknameGivenName": "Nocturnal"}) == "Nocturnal"


def test_fetch_data_ignores_nickname_when_disabled() -> None:
    # falls back to profileName ("KC") since name is NULL
    assert contact_name(False, {"nicknameGivenName": "Nocturnal"}) == "KC"


def test_fetch_data_without_nickname_set_falls_back() -> None:
    assert contact_name(True, {}) == "KC"


def test_format_nickname_given_only() -> None:
    assert utils.format_nickname("Nocturnal", None) == "Nocturnal"


def test_format_nickname_given_and_family() -> None:
    assert utils.format_nickname("Ada", "Lovelace") == "Ada Lovelace"


def test_format_nickname_family_only() -> None:
    assert utils.format_nickname(None, "Lovelace") == "Lovelace"


def test_format_nickname_empty_is_none() -> None:
    assert utils.format_nickname(None, None) is None
    assert utils.format_nickname("", "  ") is None


def test_display_name_prefers_nickname() -> None:
    assert utils.display_name("KC", "KC", "Nocturnal") == "Nocturnal"


def test_display_name_without_nickname_uses_name() -> None:
    assert utils.display_name("Mykayla", "profile", None) == "Mykayla"


def test_display_name_falls_back_to_profile_when_no_name() -> None:
    assert utils.display_name(None, "pandora", None) == "pandora"


def test_display_name_ignores_empty_nickname() -> None:
    assert utils.display_name("KC", "KC", None) == "KC"
