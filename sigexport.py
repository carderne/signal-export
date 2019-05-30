#!/usr/bin/env python

import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

import click
from pysqlcipher3 import dbapi2 as sqlcipher


def config_location():
    """Get OS-dependent config location."""
    home = Path.home()
    if sys.platform == "linux" or sys.platform == "linux2":
        config_path = home / ".config/Signal"
    elif sys.platform == "darwin":
        config_path = home / "Library/Application Support/Signal"
    elif sys.platform == "win32":
        config_path = path / "AppData/Roaming/Signal"
    else:
        print("Please manually enter Signal location using --config.")
        sys.exit(1)

    return config_path


def copy_attachments(src, dst, conversations, contacts):
    """Copy attachments and reorganise in destination directory."""

    src_att = Path(src) / "attachments.noindex"
    dst = Path(dst)

    for key, messages in conversations.items():
        contact_path = dst / contacts[key]["name"]
        contact_path.mkdir(exist_ok=True)
        for msg in messages:
            attachments = msg["attachments"]
            timestamp = msg["timestamp"]
            date = datetime.fromtimestamp(timestamp / 1000.0).strftime("%Y-%m-%d")
            for att in attachments:
                file_name = date + "_" + att["fileName"]
                att["fileName"] = file_name
                shutil.copy2(src_att / att["path"], contact_path / file_name)

    return conversations


def make_simple(dst, conversations, contacts):
    """Output each conversation into a simple text file."""

    dst = Path(dst)

    for key, messages in conversations.items():
        name = contacts[key]["name"]
        fname = name + ".md"
        with open(dst / fname, "w") as f:
            for msg in messages:
                timestamp = msg["timestamp"]
                date = datetime.fromtimestamp(timestamp / 1000.0).strftime(
                    "%Y-%m-%d, %H-%M-%S"
                )
                body = msg["body"]
                body = body if body else ""
                body += "  "  # so that markdown newlines
                attachments = msg["attachments"]

                if msg["type"] == "outgoing":
                    sender = "Me"
                else:
                    try:
                        id = int(msg["source"][1:])
                    except ValueError:
                        id = msg["source"]
                    sender = contacts[id]["name"]

                if len(attachments) > 0:
                    body += "**attachments:** "
                for att in attachments:
                    file_name = att["fileName"]
                    path = Path(name) / file_name
                    body += f" ![{file_name}]({path})"
                print(f"[{date}] {sender} : {body}", file=f)


def fetch_data(db_file, key):
    """Load SQLite data into dicts."""

    contacts = {}
    convos = {}

    db = sqlcipher.connect(str(db_file))
    c = db.cursor()
    c2 = db.cursor()

    # param binding doesn't work for pragmas, so use a direct string concat
    for cursor in [c, c2]:
        cursor.execute(f"PRAGMA KEY = \"x'{key}'\"")
        cursor.execute(f"PRAGMA cipher_page_size = 1024")
        cursor.execute(f"PRAGMA kdf_iter = 64000")
        cursor.execute(f"PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
        cursor.execute(f"PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1")

    c.execute("SELECT json, id, name, profileName, type, members FROM conversations")
    for result in c:
        cId = result[1]
        isGroup = result[4] == "group"
        contacts[cId] = {
            "id": result[1],
            "name": result[2],
            "profileName": result[3],
            "isGroup": isGroup,
        }
        convos[cId] = []

        if isGroup:
            usableMembers = []
            # Match group members from ID (phone number) back to real
            for member in result[5].split():
                c2.execute(
                    "SELECT name, profileName FROM conversations WHERE id=?", [member]
                )
                for name in c2:
                    useName = name[0] if name else member
                    usableMembers.append(useName)

            contacts[cId]["members"] = usableMembers

    c.execute(
        "SELECT json, conversationId, sent_at, received_at FROM messages ORDER BY sent_at"
    )
    messages = []
    for result in c:
        content = json.loads(result[0])
        cId = result[1]
        if not cId:
            # Signal's data model isn't as stable as one would imagine
            continue
        convos[cId].append(content)

    return convos, contacts


@click.command()
@click.argument("dst", type=click.Path(), default="output")
@click.option(
    "--config", "-c", type=click.Path(), help="Path to Signal config and database"
)
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    default=False,
    help="Flag to overwrite existing output",
)
def main(dst, config=None, overwrite=False):
    """
    Read the Signal directory and output attachments and chat files to DST directory.
    Assumes the following default directories, can be over-ridden wtih --config.

    \b
    Default Signal directories:
     - Linux: ~/.config/Signal
     - macOS: ~/Library/Application Support/Signal
     - Windows: ~/AppData/Roaming/Signal
    """

    if config:
        src = Path(config)
    else:
        src = config_location()
    config = src / "config.json"
    db_file = src / "sql" / "db.sqlite"

    dst = Path(dst).expanduser()
    if not dst.is_dir():
        dst.mkdir(parents=True)
    elif not overwrite:
        print("Output folder already exists, didn't do anything!")
        sys.exit(1)

    # Read sqlcipher key from Signal config file
    if config.is_file():
        with open(config, "r") as conf:
            key = json.loads(conf.read())["key"]
    else:
        print(f"Error: {config} not found in directory {src}")
        sys.exit(1)

    convos, contacts = fetch_data(db_file, key)
    convos = copy_attachments(src, dst, convos, contacts)
    make_simple(dst, convos, contacts)

    print(f"Done! Files exported to {dst}.")


if __name__ == "__main__":
    main()
