"""Main script for sigexport."""

import shutil
from pathlib import Path
from typing import Optional

from typer import Argument, Context, Exit, Option, colors, run, secho

from sigexport import create, data, files, html, logging, merge, utils
from sigexport.export_channel_metadata import export_channel_metadata

OptionalPath = Optional[Path]
OptionalStr = Optional[str]


def main(
    ctx: Context,
    dest: Path = Argument(None),
    source: OptionalPath = Option(None, help="Path to Signal source directory"),
    old: OptionalPath = Option(None, help="Path to previous export to merge"),
    password: OptionalStr = Option(None, help="Linux-only. Password to decrypt DB key"),
    key: OptionalStr = Option(
        None, help="Linux-only. DB key, as found in the old config.json"
    ),
    paginate: int = Option(
        100, "--paginate", "-p", help="Messages per page in HTML; set to 0 for infinite"
    ),
    chats: str = Option(
        "", help="Comma-separated chat names to include: contact names or group names"
    ),
    json_output: bool = Option(
        True, "--json/--no-json", "-j", help="Whether to create JSON output"
    ),
    html_output: bool = Option(
        True, "--html/--no-html", "-h", help="Whether to create HTML output"
    ),
    list_chats: bool = Option(
        False, "--list-chats", "-l", help="List available chats and exit"
    ),
    include_empty: bool = Option(
        False, "--include-empty", help="Whether to include empty chats"
    ),
    include_disappearing: bool = Option(
        False,
        "--include-disappearing",
        help="Whether to include disappearing messages",
    ),
    overwrite: bool = Option(
        False,
        "--overwrite/--no-overwrite",
        help="Overwrite contents of output directory if it exists",
    ),
    verbose: bool = Option(False, "--verbose", "-v"),
    channel_members_only: bool = Option(
        False,
        "--chat-members",
        help="Export membership information for all chats (or for a subset of chats given by the --chats option)",
    ),
    _: bool = Option(False, "--version", callback=utils.version_callback),
) -> None:
    """
    Read the Signal directory and output attachments and chat to DEST directory.

    Example to list chats:

        sigexport --list-chats

    Example to export all to a directory:

        sigexport ~/outputdir
    """
    logging.verbose = verbose

    if not any((dest, list_chats)):
        secho(ctx.get_help())
        # secho("Error: Missing argument 'DEST'", fg=colors.RED)
        raise Exit(code=1)

    if source:
        source_dir = Path(source).expanduser().absolute()
    else:
        source_dir = utils.source_location()
    if not (source_dir / "config.json").is_file():
        secho(f"Error: config.json not found in directory {source_dir}")
        raise Exit(code=1)

    convos, contacts, owner = data.fetch_data(
        source_dir,
        password=password,
        key=key,
        chats=chats,
        include_empty=include_empty,
        include_disappearing=include_disappearing,
    )

    if list_chats:
        names = sorted(v.name for v in contacts.values() if v.name is not None)
        secho(" | ".join(names))
        raise Exit()

    if channel_members_only:
        export_channel_metadata(dest, contacts, owner, chats.split(","))
        raise Exit()

    dest = Path(dest).expanduser()
    if not dest.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
    elif overwrite:
        shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
    else:
        secho(
            f"Output folder '{dest}' already exists, didn't do anything!", fg=colors.RED
        )
        raise Exit()

    contacts = utils.fix_names(contacts)

    secho("Copying and renaming attachments")
    files.copy_attachments(source_dir, dest, convos, contacts, password, key)

    if json_output and old:
        secho(
            "Warning: currently, JSON does not support merging with the --old flag",
            fg=colors.RED,
        )

    secho("Creating output files")
    chat_dict = create.create_chats(convos, contacts)

    if old:
        secho(f"Merging old at {old} into output directory")
        secho("No existing files will be deleted or overwritten!")
        chat_dict = merge.merge_with_old(chat_dict, contacts, dest, Path(old))

    if paginate <= 0:
        paginate = int(1e20)

    if html_output:
        html.prep_html(dest)
    for key, messages in chat_dict.items():
        name = contacts[key].name
        # some contact names are None
        if not name:
            name = "None"
        md_path = dest / name / "chat.md"
        js_path = dest / name / "data.json"
        ht_path = dest / name / "index.html"

        md_f = md_path.open("a", encoding="utf-8")
        js_f = js_path.open("a", encoding="utf-8")
        ht_f = None
        if html_output:
            ht_f = ht_path.open("w", encoding="utf-8")

        try:
            for msg in messages:
                print(msg.to_md(), file=md_f)
                print(msg.dict_str(), file=js_f)
            if html_output:
                ht = html.create_html(
                    name=name, messages=messages, msgs_per_page=paginate
                )
                print(ht, file=ht_f)
        finally:
            md_f.close()
            js_f.close()
            if ht_f:
                ht_f.close()

    secho("Done!", fg=colors.GREEN)


def cli() -> None:
    """cli."""
    run(main)
