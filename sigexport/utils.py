import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypedDict, TypeGuard

import emoji
from typer import Exit, secho

from sigexport import models

VERSION = version("signal-export")


class Timestamp64(TypedDict):
    high: int
    low: int


def dt_from_ts(ts: float | dict[str, Any]) -> datetime:
    if isinstance(ts, dict) and is_timestamp64(ts):
        val = _combine_timestamp(ts)
        return datetime.fromtimestamp(val / 1000.0)
    elif isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000.0)
    else:
        raise ValueError(f"Invalid timestamp: {ts}")


def is_timestamp64(ts: dict[str, Any]) -> TypeGuard[Timestamp64]:
    return (
        "high" in ts
        and "low" in ts
        and isinstance(ts["high"], int)
        and isinstance(ts["low"], int)
    )


def _combine_timestamp(ts: Timestamp64) -> int:
    high = ts["high"]
    low = ts["low"] if ts["low"] >= 0 else (ts["low"] + 2**32)
    return (high << 32) | low


def parse_datetime(input_str: str) -> datetime:
    last_exception = None
    for fmt in [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d, %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d, %H:%M:%S",
    ]:
        try:
            return datetime.strptime(input_str, fmt)
        except ValueError as e:
            last_exception = e
    if last_exception is None:
        raise ValueError(f"Could not parse datetime: {input_str}")
    raise last_exception


def version_callback(value: bool) -> None:
    """Get sigexport version."""
    if value:
        print(f"v{VERSION}")
        raise Exit()


def source_location() -> Path:
    """Get OS-dependent source location."""
    home = Path.home()
    paths = {
        "linux": home / ".config/Signal",
        "linux2": home / ".config/Signal",
        "darwin": home / "Library/Application Support/Signal",
        "win32": home / "AppData/Roaming/Signal",
    }
    try:
        source_path = paths[sys.platform]
    except KeyError:
        secho("Please manually enter Signal location using --source.")
        raise Exit(code=1)

    return source_path


def fix_names(contacts: models.Contacts) -> models.Contacts:
    """Convert contact names to filesystem-friendly, de-duplicating collisions.

    Every contact ends up with a non-empty, unique name so each gets its own
    output folder. Nameless contacts previously kept ``None`` and all collided
    in a single ``None/`` folder (their messages interleaved); now they are
    de-duplicated like any other clash.

    Iteration is in a stable order (serviceId, then id) so the numeric suffixes
    are deterministic across exports and a contact keeps the same folder from
    run to run (important for ``--old`` merges).
    """
    used: set[str] = set()
    for key in sorted(contacts, key=lambda k: (contacts[k].serviceId or "", k)):
        item = contacts[key]
        if item.name is None:
            base = "None"
        else:
            base = "".join(x for x in emoji.demojize(item.name) if x.isalnum())
            if base == "":
                base = "unnamed"

        name = base
        suffix = 2
        while name in used:
            name = f"{base}{suffix}"
            suffix += 1
        used.add(name)
        item.name = name

    return contacts
