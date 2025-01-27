import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypedDict, Union, cast

import emoji
from typer import Exit, secho
from typing_extensions import TypeGuard

from sigexport import models

VERSION = version("signal-export")


class Timestamp64(TypedDict):
    high: int
    low: int


def dt_from_ts(ts: Union[float, dict[str, Any]]) -> datetime:
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
    exception = cast(ValueError, last_exception)
    raise (exception)


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
    """Convert contact names to filesystem-friendly."""
    fixed_contact_names = set()
    for key, item in contacts.items():
        contact_name = item.number if item.name is None else item.name
        if contacts[key].name is not None:
            contacts[key].name = "".join(
                x for x in emoji.demojize(contact_name) if x.isalnum()
            )
            if contacts[key].name == "":
                contacts[key].name = "unnamed"
            fixed_contact_name = contacts[key].name
            if fixed_contact_name in fixed_contact_names:
                name_differentiating_number = 2
                while (
                    fixed_contact_name + str(name_differentiating_number)
                ) in fixed_contact_names:
                    name_differentiating_number += 1
                fixed_contact_name += str(name_differentiating_number)
                contacts[key].name = fixed_contact_name
            fixed_contact_names.add(fixed_contact_name)

    return contacts
