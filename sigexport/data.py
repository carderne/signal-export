"""Extract data from Signal DB."""

import json
from pathlib import Path
from typing import Optional

from sqlcipher3 import dbapi2
from typer import Exit, colors, secho

from sigexport import crypto, models
from sigexport.logging import log


def fetch_data(
    source_dir: Path,
    password: Optional[str],
    key: Optional[str],
    chats: str,
    include_empty: bool,
    include_disappearing: bool,
) -> tuple[models.Convos, models.Contacts, models.Contact]:
    """Load SQLite data into dicts.
    :returns: a tuple of:
        all conversations,
        all contacts,
        the contact object of the db owner
    """
    db_file = source_dir / "sql" / "db.sqlite"

    if key is None:
        try:
            key = crypto.get_key(source_dir, password)
        except Exception as e:
            secho(f"Failed to decrypt Signal password: {e}", fg=colors.RED)
            raise Exit(1)

    log(f"Fetching data from {db_file}\n")
    contacts: models.Contacts = {}
    convos: models.Convos = {}
    chats_list = chats.split(",") if len(chats) > 0 else []

    db = dbapi2.connect(str(db_file))
    c = db.cursor()
    # param binding doesn't work for pragmas, so use a direct string concat
    c.execute(f"PRAGMA KEY = \"x'{key}'\"")
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 64000")
    c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
    c.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

    query = "SELECT type, id, serviceId, e164, name, profileName, members FROM conversations"
    c.execute(query)
    for result in c:
        log(f"\tLoading SQL results for: {result[4]}, aka {result[5]}")
        members = []
        if result[6]:
            members = result[6].split(" ")
        is_group = result[0] == "group"
        cid = result[1]
        contact = models.Contact(
            id=cid,
            serviceId=result[2],
            name=result[4],
            number=result[3],
            profile_name=result[5],
            members=members,
            is_group=is_group,
        )
        if contact.name is None:
            contact.name = contact.profile_name
        contacts[cid] = contact
        if not chats or (result[4] in chats_list or result[5] in chats_list):
            convos[cid] = []

    query = "SELECT conversationId, type, json, id, body, sourceServiceId, timestamp, sent_at, serverTimestamp, hasAttachments, readStatus, seenStatus, expireTimer FROM messages ORDER BY sent_at"
    c.execute(query)
    for result in c:
        cid = result[0]
        type = result[1]
        jsonLoaded = json.loads(result[2])
        if cid and cid in convos:
            if type in ["keychange", "profile-change", None]:
                continue
            expireTimer = result[12]
            if expireTimer and not include_disappearing:
                continue
            con = models.RawMessage(
                conversation_id=cid,
                id=result[3],
                type=type,
                body=result[4],
                source=result[5],
                timestamp=result[6],
                sent_at=result[7],
                server_timestamp=result[8],
                has_attachments=result[9],
                attachments=jsonLoaded.get("attachments", []),
                read_status=result[10],
                seen_status=result[11],
                call_history=jsonLoaded.get("call_history"),
                reactions=jsonLoaded.get("reactions", []),
                sticker=jsonLoaded.get("sticker"),
                quote=jsonLoaded.get("quote"),
            )
            convos[cid].append(con)

    if not include_empty:
        convos = {key: val for key, val in convos.items() if len(val) > 0}

    owner_id = c.execute("select ourServiceId from sessions").fetchone()[0]
    contact_by_service_id: models.Contacts = {
        c.serviceId: c
        for c in contacts.values()
    }

    return convos, contacts, contact_by_service_id[owner_id]