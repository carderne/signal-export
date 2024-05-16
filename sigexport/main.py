"""Main script for sigexport."""

import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from typer import Argument, Exit, Option, colors, run, secho

from sigexport import create, files, html, logging, merge, models, utils
from sigexport.logging import log

DATA_DELIM = "-----DATA-----"


# these are here because tiangolo/typer doesn't like Foo | None syntax
OptionalPath = Optional[Path]
OptionalStr = Optional[str]


def main(
    dest: Path = Argument(None),
    source: OptionalPath = Option(None, help="Path to Signal source database"),
    old: OptionalPath = Option(None, help="Path to previous export to merge"),
    paginate: int = Option(
        100, "--paginate", "-p", help="Messages per page in HTML; set to 0 for infinite"
    ),
    chats: str = Option(
        "", help="Comma-separated chat names to include: contact names or group names"
    ),
    json_output: bool = Option(
        False, "--json/--no-json", "-j", help="Whether to create JSON output"
    ),
    html_output: bool = Option(
        False, "--html/--no-html", "-h", help="Whether to create HTML output"
    ),
    list_chats: bool = Option(
        False, "--list-chats", "-l", help="List available chats and exit"
    ),
    include_empty: bool = Option(
        False, "--include-empty", help="Whether to include empty chats"
    ),
    verbose: bool = Option(False, "--verbose", "-v"),
    use_docker: bool = Option(
        True, help="Use Docker container for SQLCipher extraction"
    ),
    docker_image: str = Option(None, help="Docker image to use"),
    print_data: bool = Option(
        False, help="Print extracted DB data and exit (for use by Docker container)"
    ),
    _: bool = Option(False, "--version", callback=utils.version_callback),
) -> None:
    """Read the Signal directory and output attachments and chat to DEST directory."""
    logging.verbose = verbose

    if not any((dest, list_chats, print_data)):
        secho("Error: Missing argument 'DEST'", fg=colors.RED)
        raise Exit(code=1)

    if source:
        src = Path(source).expanduser().absolute()
    else:
        src = utils.source_location()
    source = src / "config.json"
    db_file = src / "sql" / "db.sqlite"

    # Read sqlcipher key from Signal config file
    if source.is_file():
        with open(source, encoding="utf-8") as conf:
            key = json.loads(conf.read())["key"]
    else:
        secho(f"Error: {source} not found in directory {src}")
        raise Exit(code=1)

    log(f"Fetching data from {db_file}\n")

    if use_docker:
        if not docker_image:
            docker_version = utils.VERSION.split(".dev")[0]
            docker_image = f"carderne/sigexport:v{docker_version}"
        secho(
            "Using Docker to extract data, this may take a while the first time!",
            fg=colors.BLUE,
        )
        cmd = [
            "docker",
            "run",
            "--rm",
            f"--volume={src}:/Signal",
            docker_image,
            "--no-use-docker",
            "--print-data",
        ]
        if chats:
            cmd.append(f"--chats={chats}")
        if include_empty:
            cmd.append("--include-empty")
        if verbose:
            cmd.append("--verbose")
        try:
            p = subprocess.run(
                cmd,  # NoQA: S603
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
            )
        except FileNotFoundError:
            secho("Error: using Docker method, but is Docker installed?", fg=colors.RED)
            secho("Try running this from the command line:\ndocker run hello-world")
            raise Exit(1)
        except subprocess.TimeoutExpired:
            secho("Docker process timed out.")
            raise Exit(1)
        try:
            docker_logs_1, data_raw, docker_logs_2 = p.stdout.split(DATA_DELIM)
        except ValueError:
            secho(f"Docker process failed, see logs below:\n{p.stderr}", fg=colors.RED)
            if sys.platform == "win32":
                secho("If the Signal app is still running, exit it and try again.")
            raise Exit(1)
        try:
            data = json.loads(data_raw)
            log(docker_logs_1)
            log(docker_logs_2)
        except json.JSONDecodeError:
            secho("Unable to decode data from Docker, see logs below:", fg=colors.RED)
            secho(p.stdout)
            secho(p.stderr, fg=colors.RED)
            raise Exit(1)
        try:
            convos_dict = data["convos"]
            contacts_dict = data["contacts"]

            convos: models.Convos = {}
            for k, cs in convos_dict.items():
                convos[k] = [models.RawMessage(**c) for c in cs]

            contacts: models.Contacts = {}
            for k, v in contacts_dict.items():
                contacts[k] = models.Contact(**v)

        except (KeyError, TypeError):
            secho(
                "Unable to extract convos and contacts from Docker, see data below",
                fg=colors.RED,
            )
            secho(data)
            raise Exit(1)
    else:
        try:
            from sigexport.data import fetch_data

            convos, contacts = fetch_data(
                db_file,
                key,
                chats=chats,
                include_empty=include_empty,
            )

            if print_data:
                convos_dict = {k: [asdict(c) for c in cs] for k, cs in convos.items()}
                contacts_dict = {k: asdict(v) for k, v in contacts.items()}
                data = {"convos": convos_dict, "contacts": contacts_dict}
                print(DATA_DELIM, json.dumps(data), DATA_DELIM)
                raise Exit()
        except Exception:
            secho("You set 'no-use-docker' but `pysqlcipher3` not installed properly")
            sys.exit(1)

    if list_chats:
        names = sorted(v.name for v in contacts.values() if v.name is not None)
        secho(" | ".join(names))
        raise Exit()

    dest = Path(dest).expanduser()
    if not dest.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
    else:
        secho(
            f"Output folder '{dest}' already exists, didn't do anything!", fg=colors.RED
        )
        raise Exit()

    contacts = utils.fix_names(contacts)

    secho("Copying and renaming attachments")
    for att_src, att_dst in files.copy_attachments(src, dest, convos, contacts):
        try:
            shutil.copy2(att_src, att_dst)
        except FileNotFoundError:
            secho(f"No file to copy at {att_src}, skipping!", fg=colors.MAGENTA)
        except OSError as exc:
            secho(f"Error copying file {att_src}, skipping!\n{exc}", fg=colors.MAGENTA)

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


if __name__ == "__main__":
    cli()
