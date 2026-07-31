"""Incremental `--update` mode: merge a fresh export into an existing one.

Unlike `--old` (which re-parses the exported Markdown), this treats each chat's
`data.json` as the canonical store: it loads the previously-exported messages,
unions them with the current run by stable message id, and hands the merged set
back so the Markdown/HTML/JSON are all regenerated consistently.
"""

import json
from pathlib import Path

from sigexport import models
from sigexport.logging import log


def _key(msg: models.Message) -> str:
    """De-duplication key: the Signal message id, or a stable fallback.

    Older archives (exported before message ids were stored) fall back to a
    composite that is unique enough in practice.
    """
    if msg.id:
        return msg.id
    return f"{msg.date.isoformat()}|{msg.sender}|{msg.body}"


def load_archived_messages(data_path: Path) -> list[models.Message]:
    """Load previously-exported messages from a chat's `data.json`."""
    messages: list[models.Message] = []
    with data_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(models.Message.from_dict(json.loads(line)))
            except (ValueError, KeyError, TypeError) as e:
                log(f"\t\tSkipping unparseable archived message in {data_path}: {e}")
    return messages


def merge_messages(
    existing: list[models.Message], new: list[models.Message]
) -> list[models.Message]:
    """Union `existing` and `new` by message key, newest wins, sorted by date."""
    by_key: dict[str, models.Message] = {}
    for msg in existing:
        by_key[_key(msg)] = msg
    # the current run wins on a key clash, so edits/reactions update in place
    for msg in new:
        by_key[_key(msg)] = msg
    return sorted(by_key.values(), key=lambda m: m.date)


def merge_into_archive(
    chat_dict: models.Chats, contacts: models.Contacts, dest: Path
) -> models.Chats:
    """Merge each current chat into whatever is already archived at `dest`.

    Chats that only exist in the archive (no current messages) are left
    untouched on disk. Chats new to this run are passed through unchanged.
    """
    for key, new_msgs in chat_dict.items():
        name = contacts[key].name or "None"
        data_path = dest / name / "data.json"
        if not data_path.is_file():
            continue
        existing = load_archived_messages(data_path)
        log(f"\tMerging {len(new_msgs)} new into {len(existing)} archived for {name}")
        chat_dict[key] = merge_messages(existing, new_msgs)
    return chat_dict
