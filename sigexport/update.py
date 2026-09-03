"""Incremental `--update` mode: merge a fresh export into an existing one.

Unlike `--old` (which re-parses the exported Markdown), this treats each chat's
`data.json` as the canonical store: it loads the previously-exported messages,
unions them with the current run by stable message id, and hands the merged set
back so the Markdown/HTML/JSON are all regenerated consistently.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from typer import colors, secho

from sigexport import models
from sigexport.logging import log

MANIFEST = "manifest.json"
MANIFEST_VERSION = 1


class ArchiveReadError(Exception):
    """An archived data.json could not be fully parsed."""


def load_manifest(dest: Path) -> dict[str, dict]:
    """Load the archive manifest (conversation id -> folder metadata)."""
    path = dest / MANIFEST
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        log(f"\tCould not read {path}: {e}; ignoring")
        return {}
    return data.get("conversations", {})


def pinned_folders(dest: Path, contacts: models.Contacts) -> dict[str, str]:
    """Folders to keep stable for conversations already in the manifest."""
    manifest = load_manifest(dest)
    return {
        key: entry["folder"]
        for key, entry in manifest.items()
        if key in contacts and entry.get("folder")
    }


def legacy_without_manifest(dest: Path) -> bool:
    """True if `dest` already holds chats but has no manifest to match against.

    That means it predates the manifest (an older export, or a plain one), so
    `--update` has to fall back to matching by folder name.
    """
    if (dest / MANIFEST).is_file():
        return False
    try:
        return any(
            (child / "data.json").is_file()
            for child in dest.iterdir()
            if child.is_dir()
        )
    except OSError:
        return False


def save_manifest(
    dest: Path, contacts: models.Contacts, exported_keys: Iterable[str]
) -> None:
    """Record each exported conversation's folder, preserving prior entries.

    Renames are tracked: a previous display name that no longer matches is
    kept under ``aliases``.
    """
    existing = load_manifest(dest)
    conversations = dict(existing)  # keep entries for archived-only chats
    for key in exported_keys:
        contact = contacts[key]
        prev = existing.get(key, {})
        aliases = set(prev.get("aliases", []))
        prev_display = prev.get("display")
        if prev_display and prev_display != contact.display:
            aliases.add(prev_display)
        conversations[key] = {
            "folder": contact.name,
            "display": contact.display,
            "aliases": sorted(aliases),
        }
    payload = {"format_version": MANIFEST_VERSION, "conversations": conversations}
    (dest / MANIFEST).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _key(msg: models.Message) -> str:
    """De-duplication key: the Signal message id, or a stable fallback.

    Older archives (exported before message ids were stored) fall back to a
    composite that is unique enough in practice.
    """
    if msg.id:
        return msg.id
    return f"{msg.date.isoformat()}|{msg.sender}|{msg.body}"


def load_archived_messages(data_path: Path) -> list[models.Message]:
    """Load previously-exported messages from a chat's `data.json`.

    Strict: raises `ArchiveReadError` on the first unparseable line rather than
    dropping it, so a corrupt store never gets silently rewritten with the bad
    line's message missing.
    """
    messages: list[models.Message] = []
    with data_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(models.Message.from_dict(json.loads(line)))
            except (ValueError, KeyError, TypeError) as e:
                raise ArchiveReadError(f"{data_path} line {i}: {e}") from e
    return messages


def merge_messages(
    existing: list[models.Message],
    new: list[models.Message],
    *,
    reconcile_disappearing: bool = False,
    keep_disappearing: bool = False,
    forget_disappearing: bool = False,
) -> list[models.Message]:
    """Union `existing` and `new` by message key, newest wins, sorted by date.

    Disappearing-message retention (all default to "respect disappearance"):
    - ``forget_disappearing``: drop every disappearing message outright.
    - ``reconcile_disappearing`` (i.e. this run read disappearing messages):
      an archived disappearing message no longer present in the fresh read has
      expired in Signal, so drop it unless ``keep_disappearing`` is set.
    - otherwise archived disappearing messages are left untouched (we can't
      tell "expired" from "not read this run").
    """
    new_keys = {_key(m) for m in new}
    by_key: dict[str, models.Message] = {}
    for msg in existing:
        if msg.disappearing:
            if forget_disappearing:
                continue
            expired = reconcile_disappearing and _key(msg) not in new_keys
            if expired and not keep_disappearing:
                continue
        by_key[_key(msg)] = msg
    # the current run wins on a key clash, so edits/reactions update in place
    for msg in new:
        if forget_disappearing and msg.disappearing:
            continue
        by_key[_key(msg)] = msg
    return sorted(by_key.values(), key=lambda m: m.date)


def merge_into_archive(
    chat_dict: models.Chats,
    contacts: models.Contacts,
    dest: Path,
    *,
    reconcile_disappearing: bool = False,
    keep_disappearing: bool = False,
    forget_disappearing: bool = False,
) -> models.Chats:
    """Merge each current chat into whatever is already archived at `dest`.

    Chats that only exist in the archive (no current messages) are left
    untouched on disk. Chats new to this run are passed through unchanged.
    """
    skipped: list[str] = []
    for key, new_msgs in chat_dict.items():
        name = contacts[key].name or "None"
        data_path = dest / name / "data.json"
        if not data_path.is_file():
            continue
        try:
            existing = load_archived_messages(data_path)
        except ArchiveReadError as e:
            secho(
                f"Warning: can't read archived store ({e}); leaving '{name}' "
                "untouched this run. Fix or remove it, then re-run.",
                fg=colors.RED,
            )
            skipped.append(key)
            continue
        log(f"\tMerging {len(new_msgs)} new into {len(existing)} archived for {name}")
        chat_dict[key] = merge_messages(
            existing,
            new_msgs,
            reconcile_disappearing=reconcile_disappearing,
            keep_disappearing=keep_disappearing,
            forget_disappearing=forget_disappearing,
        )
    # don't rewrite chats whose existing store we couldn't fully read
    for key in skipped:
        del chat_dict[key]
    return chat_dict
