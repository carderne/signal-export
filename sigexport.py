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
        config_path = path / "AppData\Roaming\Signal"
    else:
        print("Please manually enter Signal config location.")
        sys.exit(1)

    return config_path


def copy_attachments(src, dst, conversations):
    """Copy attachments and reorganise in destination directory."""
    src = Path(src)
    dst = Path(dst)
    dst_thumb = dst / "thumb"
    if dst.is_dir():
        shutil.rmtree(dst)
    dst_thumb.mkdir(parents=True)

    for key, messages in conversations.items():
        for msg in messages:
            attachments = msg["attachments"]
            if len(attachments) > 0:
                timestamp = msg["timestamp"]
                date = datetime.fromtimestamp(timestamp / 1000.0).strftime("%Y-%m-%d")
                for att in attachments:
                    file_name = date + "_" + att["fileName"]
                    att["fileName"] = file_name
                    shutil.copy2(src / att["path"], dst / file_name)
                    if "thumbnail" in att:
                        shutil.copy2(
                            src / att["thumbnail"]["path"], dst_thumb / file_name
                        )

    return conversations


def make_simple(dst, conversations, contacts):
    """Output each conversation into a simple text file."""

    dst = Path(dst)
    if dst.is_dir():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    for key, messages in conversations.items():
        fname = dst / contacts[key]["name"]
        with open(fname, "w") as f:
            for msg in messages:
                timestamp = msg["timestamp"]
                date = datetime.fromtimestamp(timestamp / 1000.0).strftime(
                    "%Y-%m-%d, %H-%M-%S"
                )
                body = msg["body"]
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
                    body = f"[attachments] {body}"
                print(f"[{date}] {sender} : {body}", file=f)


@click.command()
@click.option(
    "--config", "-c", type=click.Path(), help="Path to Signal config and database"
)
@click.argument("dst", type=click.Path(), default="output")
def export(dst, config=None):
    """
    Read the Signal directory and output .json and .html files to DST directory.
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
    html_in = Path(os.path.dirname(os.path.abspath(__file__))) / "chattr.html"

    dst = Path(dst).expanduser()
    if dst.is_dir():
        print("Output folder already exists, didn't do anything!")
        sys.exit(1)
    dst.mkdir(parents=True)
    cont = dst / "contacts.json"
    conv = dst / "conversations.json"
    html = dst / "conversations.html"
    attachments = dst / "attachments"
    simple = dst / "simple"

    # Read sqlcipher key from Signal config file
    try:
        with open(config, "r") as conf:
            key = json.loads(conf.read())["key"]
    except FileNotFoundError:
        print(f"Error: {config} not found in directory {src}")
        sys.exit(1)

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

    contacts = {}
    convos = {}

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
            # Attempt to match group members from ID (phone number) back to real
            # names if the real names are also in your contact/conversation list.
            for member in result[5].split():
                c2.execute(
                    "SELECT name, profileName FROM conversations WHERE id=?", [member]
                )
                for name in c2:
                    useName = name[0] if name else member
                    usableMembers.append(useName)

            contacts[cId]["members"] = usableMembers

    # We either need an ORDER BY or a manual sort() below because our web interface
    # processes message history in array order with javascript object traversal.
    # If we skip ordering here, the web interface will show the message history in
    # a random order, which can be amusing but not necessarily very useful.
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

    convos = copy_attachments(src / "attachments.noindex", attachments, convos)
    make_simple(simple, convos, contacts)

    with open(cont, "w") as con:
        json.dump(contacts, con)
        contactsJSON = json.dumps(contacts)

    with open(conv, "w") as ampc:
        json.dump(convos, ampc)
        convosJSON = json.dumps(convos)

    # Create end result of interactive HTML interface with embedded and formatted
    # chat history for all contacts/conversations.
    with open(html_in, "r") as chattr:
        newChat = chattr.read()
        updated = newChat.replace(
            "JSONINSERTHERE",
            f"var contacts = {contactsJSON}; var convos = {convosJSON};",
        )

        with open(html, "w") as mine:
            mine.write(updated)

    print(f"Done! Files exported to {dst}.")


if __name__ == "__main__":
    export()
