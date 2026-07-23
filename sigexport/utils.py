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


# Top-level system directories that should never *themselves* be a target.
# We only refuse an exact match (not their contents), so e.g. /var/backups is
# still allowed; that case is handled by the looks-like-an-export check.
SYSTEM_DIRS = (
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/opt",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/sys",
    "/usr",
    "/var",
)


def is_dangerous_overwrite_target(dest: Path) -> str | None:
    """Return a reason string if `dest` is too dangerous to delete, else None.

    These paths are never a legitimate export target, so `--overwrite` must
    refuse them outright rather than recursively deleting them.
    """
    resolved = dest.expanduser().resolve()
    if resolved == Path(resolved.anchor):
        return "the filesystem root"
    if resolved == Path.home().resolve():
        return "your home directory"
    cwd = Path.cwd().resolve()
    if resolved == cwd:
        return "the current working directory"
    if resolved in cwd.parents:
        return "a parent of the current working directory"
    for sysdir in SYSTEM_DIRS:
        # resolve() so /var matches even where it's a symlink (e.g. macOS)
        if resolved == Path(sysdir).resolve():
            return f"a system directory ({sysdir})"
    return None


def looks_like_export_dir(dest: Path) -> bool:
    """Whether `dest` looks like a previous signal-export output.

    Used to avoid `--overwrite` deleting an arbitrary directory the user
    pointed at by mistake. An empty directory is fine; otherwise we look for
    our own artifacts (the root stylesheet, or a chat folder with its files).
    """
    try:
        entries = list(dest.iterdir())
    except OSError:
        return False
    if not entries:
        return True
    if (dest / "style.css").is_file():
        return True
    markers = ("chat.md", "index.html", "data.json")
    for child in entries:
        if child.is_dir() and any((child / m).is_file() for m in markers):
            return True
    return False


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
