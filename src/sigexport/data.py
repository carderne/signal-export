"""Extract data from Signal DB."""

import json
from pathlib import Path
from typing import Optional

from pysqlcipher3 import dbapi2 as sqlcipher
from typer import Exit, colors, secho

from sigexport import crypto, models
from sigexport.logging import log


def fetch_data(
    source_dir: Path,
    password: Optional[str],
    chats: str,
    include_empty: bool,
) -> tuple[models.Convos, models.Contacts]:
    """Load SQLite data into dicts."""
    db_file = source_dir / "sql" / "db.sqlite"
    signal_config = source_dir / "config.json"

    try:
        key = crypto.get_key(signal_config, password)
    except Exception:
        secho("Failed to decrypt Signal password", fg=colors.RED)
        raise Exit(1)

    log(f"Fetching data from {db_file}\n")
    contacts: models.Contacts = {}
    convos: models.Convos = {}
    chats_list = chats.split(",") if len(chats) > 0 else []

    db = sqlcipher.connect(str(db_file))  # type: ignore
    c = db.cursor()
    # param binding doesn't work for pragmas, so use a direct string concat
    c.execute(f"PRAGMA KEY = \"x'{key}'\"")
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 64000")
    c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
    c.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

    query = "SELECT type, id, e164, name, profileName, members FROM conversations"
    c.execute(query)
    for result in c:
        log(f"\tLoading SQL results for: {result[3]}, aka {result[4]}")
        members = []
        if result[5]:
            members = result[5].split(" ")
        is_group = result[0] == "group"
        cid = result[1]
        contacts[cid] = models.Contact(
            id=cid,
            name=result[3],
            number=result[2],
            profile_name=result[4],
            members=members,
            is_group=is_group,
        )
        if contacts[cid].name is None:
            contacts[cid].name = contacts[cid].profile_name

        if not chats or (result[3] in chats_list or result[4] in chats_list):
            convos[cid] = []

    query = "SELECT json, conversationId FROM messages ORDER BY sent_at"
    c.execute(query)
    for result in c:
        res = json.loads(result[0])
        cid = result[1]
        if cid and cid in convos:
            if res.get("type") in ["keychange", "profile-change"]:
                continue
            con = models.RawMessage(
                conversation_id=res["conversationId"],
                id=res["id"],
                type=res.get("type"),
                body=res.get("body", ""),
                contact=res.get("contact"),
                source=res.get("source"),
                timestamp=res.get("timestamp"),
                sent_at=res.get("sent_at"),
                server_timestamp=res.get("serverTimestamp"),
                has_attachments=res.get("has_attachments", False),
                attachments=res.get("attachments", []),
                read_status=res.get("read_status"),
                seen_status=res.get("seen_status"),
                call_history=res.get("call_history"),
                reactions=res.get("reactions", []),
                sticker=res.get("sticker"),
                quote=res.get("quote"),
            )
            convos[cid].append(con)

    if not include_empty:
        convos = {key: val for key, val in convos.items() if len(val) > 0}

    return convos, contacts
