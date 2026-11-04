import base64
import hashlib
import hmac
import json
import sqlite3
from pathlib import Path

from Crypto.Cipher import AES

from sigexport import data

LONG = "word " * 1000  # well past Signal's ~2 KB inline body


def write_encrypted_attachment(src_path: Path, plaintext: bytes) -> str:
    """A v2 (locally encrypted) attachment on disk, as Signal stores it; returns its localKey."""
    cipher_key, mac_key, iv = bytes(range(32)), bytes(range(32, 64)), bytes(16)
    padding = -len(plaintext) % AES.block_size
    ciphertext = AES.new(cipher_key, AES.MODE_CBC, iv).encrypt(plaintext + bytes(padding))
    mac = hmac.new(mac_key, iv + ciphertext, hashlib.sha256).digest()
    src_path.write_bytes(iv + ciphertext + mac)
    return base64.b64encode(cipher_key + mac_key).decode()


def make_cursor(attachments_row: tuple | None) -> sqlite3.Cursor:
    """A minimal Signal DB with one long message, stored the way Signal stores it:
    the first ~2 KB inline, the whole text as a 'long-message' attachment."""
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
        "CREATE TABLE message_attachments (messageId, editHistoryIndex, "
        "attachmentType, orderInMessage, size, contentType, path, fileName, "
        "localKey, version, pending)"
    )
    cur.execute(
        "INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
        ("private", "c1", "sid1", None, "Alice", None, None, "{}"),
    )
    cur.execute(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("c1", "incoming", json.dumps({}), "m1", LONG[:2048], None, 1, 1000, None, 1, None, None, None),
    )
    if attachments_row is not None:
        cur.execute(
            "INSERT INTO message_attachments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            attachments_row,
        )
    con.commit()
    return cur


def body_of_m1(source: Path, cur: sqlite3.Cursor) -> str:
    convos, _, _ = data.fetch_data(
        source, cur, chats="", include_empty=False, include_disappearing=False
    )
    return convos["c1"][0].body


def test_long_message_body_is_the_whole_text(tmp_path: Path) -> None:
    blob = tmp_path / "attachments.noindex" / "ab" / "long"
    blob.parent.mkdir(parents=True)
    local_key = write_encrypted_attachment(blob, LONG.encode())
    row = ("m1", -1, "long-message", 0, len(LONG), "text/x-signal-plain", "ab/long", None, local_key, 2, 0)
    assert body_of_m1(tmp_path, make_cursor(row)) == LONG


def test_unreadable_long_message_keeps_the_inline_body(tmp_path: Path) -> None:
    row = ("m1", -1, "long-message", 0, len(LONG), "text/x-signal-plain", "ab/missing", None, "", 2, 0)
    assert body_of_m1(tmp_path, make_cursor(row)) == LONG[:2048]


def test_without_a_long_message_attachment_the_body_is_unchanged(tmp_path: Path) -> None:
    assert body_of_m1(tmp_path, make_cursor(None)) == LONG[:2048]
