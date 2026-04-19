import re
from pathlib import Path
from typing import Any

from sigexport import models, utils
from sigexport.logging import log


def _format_call(call_history: dict[str, Any] | None) -> str:
    """Format a human-readable call description from call_history data."""
    if not call_history:
        return "Outgoing call"

    # Legacy format (older Signal versions)
    if "wasIncoming" in call_history and "direction" not in call_history:
        return "Incoming call" if call_history["wasIncoming"] else "Outgoing call"

    direction = call_history.get("direction", "")
    status = call_history.get("status", "")
    call_type = (call_history.get("callType") or "").lower()  # "audio" or "video"
    started_ts = call_history.get("timestamp")
    ended_ts = call_history.get("endedTimestamp")

    # Duration string (only if call was accepted and we have both timestamps)
    duration_str = ""
    if status == "Accepted" and started_ts and ended_ts and ended_ts > started_ts:
        total_secs = (ended_ts - started_ts) // 1000
        mins, secs = divmod(total_secs, 60)
        duration_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    label = f"{call_type} call" if call_type else "call"
    label = label.replace("audio", "voice")

    if direction == "Incoming":
        if status == "Accepted":
            detail = f"accepted, {duration_str}" if duration_str else "accepted"
            return f"Incoming {label} ({detail})"
        elif status == "Missed":
            return f"Missed {label}"
        elif status == "Declined":
            return f"Incoming {label} (declined)"
        else:
            return f"Incoming {label} ({status.lower()})" if status else f"Incoming {label}"
    elif direction == "Outgoing":
        if status == "Accepted":
            detail = f"accepted, {duration_str}" if duration_str else "accepted"
            return f"Outgoing {label} ({detail})"
        elif status in ("Missed", "NotAccepted"):
            return f"Outgoing {label} (unanswered)"
        elif status == "Declined":
            return f"Outgoing {label} (declined by recipient)"
        else:
            return f"Outgoing {label} ({status.lower()})" if status else f"Outgoing {label}"
    else:
        # Fallback
        return "Incoming call" if call_history.get("wasIncoming") else "Outgoing call"


def create_message(
    msg: models.RawMessage,
    name: str,  # only used for debug logging
    is_group: bool,
    contacts: models.Contacts,
) -> models.Message:
    ts = msg.get_ts()
    date = utils.dt_from_ts(ts)
    if ts == 0:
        log("\t\tNo timestamp or sent_at; date set to 1970")
    log(f"\t\tDoing {name}, msg: {date}")

    if msg.type == "call-history":
        body = _format_call(msg.call_history)
    else:
        body = msg.body or ""

    body = body.replace("`", "")  # stop md code sections forming
    body += "  "  # so that markdown newlines

    sender = "No-Sender"
    if msg.type == "outgoing":
        sender = "Me"
    elif msg.type == "call-history" and msg.call_history and msg.call_history.get("direction") == "Outgoing":
        sender = "Me"
    else:
        try:
            if is_group:
                for c in contacts.values():
                    serviceId = c.serviceId
                    if serviceId is not None and serviceId == msg.source:
                        sender = c.name
            else:
                sender = contacts[msg.conversation_id].name
        except KeyError:
            log(f"\t\tNo sender:\t\t{date}")

    attachments: list[models.Attachment] = []
    for att in msg.attachments:
        file_name = att["fileName"]
        path = Path("media") / file_name
        path = Path(re.sub(r"\s", "%20", str(path)))
        attachments.append(models.Attachment(name=file_name, path=str(path)))

    reactions: list[models.Reaction] = []
    if msg.reactions:
        for r in msg.reactions:
            try:
                reactions.append(
                    models.Reaction(contacts[r["fromId"]].name, r["emoji"])
                )
            except KeyError:
                log(
                    f"\t\tReaction fromId not found in contacts: [{date}] {sender}: {r}"
                )

    sticker = ""
    if msg.sticker:
        try:
            sticker = msg.sticker["data"]["emoji"]
        except KeyError:
            pass

    quote = ""
    if msg.quote:
        try:
            quote = msg.quote["text"].rstrip("\n")
            quote = quote.replace("\n", "\n> ")
            quote = f"\n\n> {quote}\n\n"
        except (AttributeError, KeyError, TypeError):
            pass

    return models.Message(
        date=date,
        sender=sender,
        body=body,
        quote=quote,
        sticker=sticker,
        reactions=reactions,
        attachments=attachments,
    )


def create_chats(
    convos: models.Convos,
    contacts: models.Contacts,
) -> models.Chats:
    """Convert convos and contacts into messages"""
    res: models.Chats = {}
    for key, raw_messages in convos.items():
        name = contacts[key].name
        log(f"\tDoing markdown for: {name}")
        is_group = contacts[key].is_group
        # some contact names are None
        if not name:
            name = "None"

        res[key] = [
            create_message(raw, name, is_group, contacts) for raw in raw_messages
        ]

    return res


# def create_member_lists(contacts: models.Contacts) -> str:
#
