import shutil
import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypedDict, TypeGuard

import emoji
from typer import Exit, colors, confirm, secho

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


def format_nickname(given: str | None, family: str | None) -> str | None:
    """Combine Signal's nickname given/family parts into one name, or None.

    Signal stores nicknames split into given and family parts in the
    conversation JSON (`nicknameGivenName` / `nicknameFamilyName`); either may
    be absent.
    """
    parts = [p.strip() for p in (given, family) if p and p.strip()]
    return " ".join(parts) if parts else None


def display_name(
    name: str | None, profile_name: str | None, nickname: str | None
) -> str | None:
    """Pick the name to show for a contact.

    A nickname (when present and requested) wins, then the system/contact
    name, then the profile name; mirrors Signal's own precedence.
    """
    if nickname:
        return nickname
    if name is not None:
        return name
    return profile_name


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


def safe_delete(dest: Path, yes: bool = False) -> None:
    """Recursively delete `dest`, refusing dangerous or non-export targets.

    Guards `--overwrite` before removing an existing output directory: refuses
    obviously dangerous targets (root, home, the cwd, a system dir) and
    directories that don't look like a previous export, and asks for
    confirmation when running interactively (skip with `yes`).
    """
    reason = is_dangerous_overwrite_target(dest)
    if reason:
        secho(
            f"Refusing to delete {dest.resolve()}: that's {reason}.",
            fg=colors.RED,
        )
        raise Exit(1)

    if not looks_like_export_dir(dest):
        secho(
            f"'{dest}' doesn't look like a signal-export output "
            "(no style.css or chat folders), so it won't be deleted. "
            "Remove it yourself or choose another path.",
            fg=colors.RED,
        )
        raise Exit(1)

    if not yes and sys.stdin.isatty():
        count = sum(1 for _ in dest.iterdir())
        if not confirm(f"Delete {count} item(s) in {dest.resolve()} and re-export?"):
            secho("Aborted.", fg=colors.YELLOW)
            raise Exit(1)

    shutil.rmtree(dest)


def fix_names(
    contacts: models.Contacts, pinned: dict[str, str] | None = None
) -> models.Contacts:
    """Convert contact names to filesystem-friendly, de-duplicating collisions.

    Every contact ends up with a non-empty, unique name so each gets its own
    output folder. Nameless contacts previously kept ``None`` and all collided
    in a single ``None/`` folder (their messages interleaved); now they are
    de-duplicated like any other clash.

    Iteration is in a stable order (serviceId, then id) so the numeric suffixes
    are deterministic across exports and a contact keeps the same folder from
    run to run (important for ``--old`` merges).

    The de-duplication suffix is only applied to ``name`` (the folder). The
    conversation-facing ``display`` keeps the un-suffixed base, so two "Alice"s
    live in Alice/ and Alice2/ but both still read "Alice" inside the export.

    ``pinned`` maps a contact id to a folder it must keep (from an archive
    manifest, for ``--update``). Pinned folders are reserved up front so a
    renamed contact keeps its existing folder even though its display updates.
    """
    pinned = pinned or {}
    used: set[str] = set(pinned.values())
    for key in sorted(contacts, key=lambda k: (contacts[k].serviceId or "", k)):
        item = contacts[key]
        if item.name is None:
            base = "None"
        else:
            base = "".join(x for x in emoji.demojize(item.name) if x.isalnum())
            if base == "":
                base = "unnamed"

        item.display = base

        if key in pinned:
            item.name = pinned[key]
            continue

        name = base
        suffix = 2
        while name in used:
            name = f"{base}{suffix}"
            suffix += 1
        used.add(name)
        item.name = name

    return contacts
