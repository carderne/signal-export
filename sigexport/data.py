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
    start_date: Optional[int] = None,
    end_date: Optional[int] = None,
) -> tuple[models.Convos, models.Contacts, Optional[models.Contact]]:
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

    query = "SELECT conversationId, type, json, id, body, sourceServiceId, timestamp, sent_at, serverTimestamp, hasAttachments, readStatus, seenStatus, expireTimer FROM messages"

    # Add date range filtering to the query if provided
    if start_date or end_date:
        query += " WHERE "

        if start_date:
            query += f"sent_at >= {start_date}"
        if start_date and end_date:
            query += " AND "
        if end_date:
            query += f"sent_at <= {end_date}"

    query += " ORDER BY sent_at"

    c.execute(query)
    for result in c:
        cid = result[0]
        _type = result[1]
        jsonLoaded = json.loads(result[2])
        if cid and cid in convos:
            if _type in ["keychange", "profile-change", None]:
                continue
            expireTimer = result[12]
            if expireTimer and not include_disappearing:
                continue
            con = models.RawMessage(
                conversation_id=cid,
                id=result[3],
                type=_type,
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

            # Filter messages based on their timestamp
            message_ts = con.get_ts()
            if (start_date is None or message_ts >= start_date) and (
                end_date is None or message_ts <= end_date
            ):
                convos[cid].append(con)

    if not include_empty:
        convos = {key: val for key, val in convos.items() if len(val) > 0}

    owner_row = c.execute("select ourServiceId from sessions").fetchone()
    owner_id = owner_row[0] if owner_row is not None else None
    contact_by_service_id: models.Contacts = {c.serviceId: c for c in contacts.values()}
    owner_contact = contact_by_service_id[owner_id] if owner_id else None

    return convos, contacts, owner_contact
