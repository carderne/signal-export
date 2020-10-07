#!/usr/bin/env python

import json
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
import re

import click
from pysqlcipher3 import dbapi2 as sqlcipher

from style import style


def source_location():
    """Get OS-dependent source location."""

    home = Path.home()
    if sys.platform == "linux" or sys.platform == "linux2":
        source_path = home / ".config/Signal"
    elif sys.platform == "darwin":
        source_path = home / "Library/Application Support/Signal"
    elif sys.platform == "win32":
        source_path = home / "AppData/Roaming/Signal"
    else:
        print("Please manually enter Signal location using --source.")
        sys.exit(1)

    return source_path


def copy_attachments(src, dest, conversations, contacts):
    """Copy attachments and reorganise in destination directory."""

    src_att = Path(src) / "attachments.noindex"
    dest = Path(dest)

    for key, messages in conversations.items():
        name = contacts[key]["name"]
        contact_path = dest / name / "media"
        contact_path.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            attachments = msg["attachments"]
            if attachments:
                date = datetime.fromtimestamp(msg["timestamp"] / 1000.0).strftime(
                    "%Y-%m-%d"
                )
                for att in attachments:
                    try:
                        file_name = f"{date}_{att['fileName']}"
                        att["fileName"] = file_name
                        shutil.copy2(src_att / att["path"], contact_path / file_name)
                    except KeyError:
                        print(f"Broken attachment:\t{name}\t{att['fileName']}")
                    except FileNotFoundError:
                        print(f"Attachment not found:\t{name}\t{att['fileName']}")

    return conversations


def make_simple(dest, conversations, contacts):
    """Output each conversation into a simple text file."""

    dest = Path(dest)
    with open(dest / "style.css", "w") as stylefile:
        print(style, file=stylefile)

    for key, messages in conversations.items():
        name = contacts[key]["name"]
        is_group = contacts[key]["is_group"]
        mdfile = open(dest / name / "index.md", "w")

        for msg in messages:
            try:
                timestamp = msg["timestamp"]
            except KeyError:
                timestamp = msg["sent_at"]
                print("No timestamp; use sent_at")
            date = datetime.fromtimestamp(timestamp / 1000.0).strftime("%Y-%m-%d %H:%M")
            try:
                body = msg["body"]
            except KeyError:
                print(f"No body:\t\t{date}")
            body = body if body else ""
            body = body.replace("`", "")  # stop md code sections forming
            body += "  "  # so that markdown newlines
            attachments = msg["attachments"]

            if msg["type"] == "outgoing":
                sender = "Me"
            else:
                try:
                    if is_group:
                        for c in contacts.values():
                            num = c["number"]
                            if num is not None and num == msg["source"]:
                                sender = c["name"]
                    else:
                        sender = contacts[msg["conversationId"]]["name"]
                except KeyError:
                    print(f"No sender:\t\t{date}")
                    sender = "No-Sender"

            for att in attachments:
                file_name = att["fileName"]
                path = Path("media") / file_name
                path = Path(str(path).replace(" ", "%20"))
                if path.suffix and path.suffix.split(".")[1] in [
                    "png",
                    "jpg",
                    "jpeg",
                    "gif",
                    "tif",
                    "tiff",
                ]:
                    body += "!"
                body += f"[{file_name}](./{path})  "
            print(f"[{date}] {sender}: {body}", file=mdfile)


def fetch_data(db_file, key, manual=False):
    """Load SQLite data into dicts."""

    contacts = {}
    convos = {}

    db_file_decrypted = db_file.parents[0] / "db-decrypt.sqlite"
    if manual:
        if db_file_decrypted.exists():
            db_file_decrypted.unlink()
        command = (
            f'echo "'
            f"PRAGMA key = \\\"x'{key}'\\\";"
            f"ATTACH DATABASE '{db_file_decrypted}' AS plaintext KEY '';"
            f"SELECT sqlcipher_export('plaintext');"
            f"DETACH DATABASE plaintext;"
            f'" | sqlcipher {db_file}'
        )
        os.system(command)
        db = sqlcipher.connect(str(db_file_decrypted))
        c = db.cursor()
        c2 = db.cursor()
    else:
        db = sqlcipher.connect(str(db_file))
        c = db.cursor()
        c2 = db.cursor()
        # param binding doesn't work for pragmas, so use a direct string concat
        for cursor in [c, c2]:
            cursor.execute(f"PRAGMA KEY = \"x'{key}'\"")
            cursor.execute("PRAGMA cipher_page_size = 1024")
            cursor.execute("PRAGMA kdf_iter = 64000")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1")

    c.execute("SELECT type, id, e164, name, profileName, members FROM conversations")
    for result in c:
        is_group = result[0] == "group"
        cid = result[1]
        contacts[cid] = {
            "id": cid,
            "name": result[3],
            "number": result[2],
            "profileName": result[4],
            "is_group": is_group,
        }
        if contacts[cid]["name"] is None:
            contacts[cid]["name"] = contacts[cid]["profileName"]
        convos[cid] = []

        if is_group:
            usable_members = []
            # Match group members from phone number to name
            for member in result[5].split():
                c2.execute(
                    "SELECT name, profileName FROM conversations WHERE id=?", [member]
                )
                for name in c2:
                    usable_members.append(name[0] if name else member)
            contacts[cid]["members"] = usable_members

    c.execute("SELECT json, conversationId " "FROM messages " "ORDER BY sent_at")
    for result in c:
        content = json.loads(result[0])
        cid = result[1]
        if cid:
            convos[cid].append(content)

    if db_file_decrypted.exists():
        db_file_decrypted.unlink()

    return convos, contacts


def fix_names(contacts):
    """Remove non-filesystem-friendly characters from names."""

    for key, item in contacts.items():
        contacts[key]["name"] = "".join(x for x in item["name"] if x.isalnum())

    return contacts


def create_html(dest):
    for sub in dest.iterdir():
        if sub.is_dir():
            name = sub.stem
            print(f"Doing html for {name}")
            path = sub / "index.md"
            with path.open() as f:
                md = f.readlines()
            md = lines_to_msgs(md)
            htfile = open(sub / "index.html", "w")
            print(
                "<!doctype html>"
                "<html><head>"
                f"<title>{name}</title>"
                "<link rel=stylesheet href='../style.css'>"
                "</head>"
                "<body>"
                f"<h1>{name}</h1>",
                file=htfile,
            )
            for msg in md:
                date, sender, body = msg
                print(
                    f"<div class=msg><span class=date>{date}</span>"
                    f"<span class=sender>{sender}</span>"
                    f"<span class=body>{body}</span></div>",
                    file=htfile,
                )
            print("</body></html>", file=htfile)


def lines_to_msgs(lines):
    p = re.compile(r"^(\[\d{4}-\d{2}-\d{2},{0,1} \d{2}:\d{2}\])(.*?:)(.*\n)")
    msgs = []
    for li in lines:
        m = p.match(li)
        if m:
            msgs.append(list(m.groups()))
        else:
            msgs[-1][-1] += li
    return msgs


def merge_chat(path_new, path_old):
    with path_old.open() as f:
        old = f.readlines()
    with path_new.open() as f:
        new = f.readlines()

    print(f"Last line old:\n{old[-1][:30]}\nFirst line new:\n{new[0][:30]}")
    print(f"Len old: {len(old)}  -  Len new: {len(new)}")
    old = lines_to_msgs(old)
    new = lines_to_msgs(new)
    print(f"Should be shorter: Len old: {len(old)}  -  Len new: {len(new)}")

    merged = old + new
    merged = [m[0] + m[1] + m[2] for m in merged]
    merged = list(dict.fromkeys(merged))

    with path_new.open("w") as f:
        f.writelines(merged)


def merge_with_old(dest, old):
    print("Going to merge output with old export at:")
    print(old)
    print("No existing files will be deleted or overwritten")
    for sub in dest.iterdir():
        if sub.is_dir():
            name = sub.stem
            print(f"Merging {name}")
            path_new = sub / "index.md"
            path_old = old / name / "index.md"
            try:
                merge_chat(path_new, path_old)
            except FileNotFoundError:
                print(f"No old for {name}")
            print()


@click.command()
@click.argument("dest", type=click.Path())
@click.option(
    "--source", "-s", type=click.Path(), help="Path to Signal source and database"
)
@click.option(
    "--old", "-s", type=click.Path(), help="Path to previous export to merge with"
)
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    default=False,
    help="Flag to overwrite existing output",
)
@click.option(
    "--manual",
    "-m",
    is_flag=True,
    default=False,
    help="Whether to manually decrypt the db",
)
def main(dest, old=None, source=None, overwrite=False, manual=False):
    """
    Read the Signal directory and output attachments and chat files to DEST directory.
    Assumes the following default directories, can be overridden wtih --source.

    Deafault for DEST is a sub-directory output/ in the current directory.

    \b
    Default Signal directories:
     - Linux: ~/.config/Signal
     - macOS: ~/Library/Application Support/Signal
     - Windows: ~/AppData/Roaming/Signal
    """

    if source:
        src = Path(source)
    else:
        src = source_location()
    source = src / "config.json"
    db_file = src / "sql" / "db.sqlite"

    dest = Path(dest).expanduser()
    if not dest.is_dir():
        dest.mkdir(parents=True)
    elif not overwrite:
        print("Output folder already exists, didn't do anything!")
        print("Use --overwrite to ignore existing directory.")
        sys.exit(1)

    # Read sqlcipher key from Signal config file
    if source.is_file():
        with open(source, "r") as conf:
            key = json.loads(conf.read())["key"]
    else:
        print(f"Error: {source} not found in directory {src}")
        sys.exit(1)

    convos, contacts = fetch_data(db_file, key, manual=manual)
    contacts = fix_names(contacts)
    convos = copy_attachments(src, dest, convos, contacts)
    make_simple(dest, convos, contacts)
    if old:
        merge_with_old(dest, Path(old))
    create_html(dest)

    print(f"\nDone! Files exported to {dest}.")


if __name__ == "__main__":
    main()
