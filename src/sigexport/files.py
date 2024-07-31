import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from typer import colors

from sigexport import models
from sigexport.logging import log


def copy_attachments(
    src: Path, dest: Path, convos: models.Convos, contacts: models.Contacts
) -> Iterable[tuple[Path, Path]]:
    """Copy attachments and reorganise in destination directory."""
    src_att = Path(src) / "attachments.noindex"
    dest = Path(dest)

    for key, messages in convos.items():
        name = contacts[key].name
        log(f"\tCopying attachments for: {name}")
        # some contact names are None
        if not name:
            name = "None"
        contact_path = dest / name / "media"
        contact_path.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            if msg.attachments:
                attachments = msg.attachments
                date = (
                    datetime.fromtimestamp(msg.get_ts() / 1000)
                    .isoformat(timespec="milliseconds")
                    .replace(":", "-")
                )
                for i, att in enumerate(attachments):
                    try:
                        # Account for no fileName key
                        file_name = (
                            str(att["fileName"]) if "fileName" in att else "None"
                        )
                        # Sometimes the key is there but it is None, needs extension
                        if "." not in file_name:
                            content_type = att["contentType"].split("/")
                            try:
                                ext = content_type[1]
                            except IndexError:
                                ext = content_type[0]
                            file_name += "." + ext
                        att["fileName"] = (
                            f"{date}_{i:02}_{file_name}".replace(" ", "_")
                            .replace("/", "-")
                            .replace(",", "")
                            .replace(":", "-")
                            .replace("|", "-")
                        )
                        # account for erroneous backslash in path
                        att_path = str(att["path"]).replace("\\", "/")
                        yield src_att / att_path, contact_path / att["fileName"]
                    except KeyError:
                        p = att["path"] if "path" in att else ""
                        log(f"\t\tBroken attachment:\t{name}\t{p}")
                    except FileNotFoundError:
                        p = att["path"] if "path" in att else ""
                        log(f"\t\tAttachment not found:\t{name}\t{p}")
            else:
                msg.attachments = []


def merge_attachments(media_new: Path, media_old: Path) -> None:
    """Merge new and old attachments directories."""
    for f in media_old.iterdir():
        if f.is_file():
            try:
                shutil.copy2(f, media_new)
            except shutil.SameFileError:
                log(
                    f"Skipped file {f} as duplicate found in new export directory!",
                    fg=colors.RED,
                )
