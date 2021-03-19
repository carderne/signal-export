#!/usr/bin/env python3

import json
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
import re

import click
from pysqlcipher3 import dbapi2 as sqlcipher
import markdown
from bs4 import BeautifulSoup


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
        # some contact names are None
        if name is None:
            name = "None"
        contact_path = dest / name / "media"
        contact_path.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            try:
                attachments = msg["attachments"]
                if attachments:
                    date = datetime.fromtimestamp(msg["timestamp"] / 1000.0).strftime(
                        "%Y-%m-%d"
                    )
                    for att in attachments:
                        try:
                            file_name = f"{date}_{att['fileName']}"
                            att["fileName"] = file_name
                            # account for erroneous backslash in path
                            att_path = str(att["path"]).replace("\\", "/")
                            shutil.copy2(src_att / att_path, contact_path / file_name)
                        except KeyError:
                            print(f"Broken attachment:\t{name}\t{att['fileName']}")
                        except FileNotFoundError:
                            print(f"Attachment not found:\t{name}\t{att['fileName']}")
            except KeyError:
                print(f"No attachments for a message: {name}")

    return conversations


def make_simple(dest, conversations, contacts):
    """Output each conversation into a simple text file."""

    dest = Path(dest)
    for key, messages in conversations.items():
        name = contacts[key]["name"]
        is_group = contacts[key]["is_group"]
        # some contact names are None
        if name is None:
            name = "None"
        mdfile = open(dest / name / "index.md", "a")

        for msg in messages:
            try:
                timestamp = msg["timestamp"]
            except KeyError:
                timestamp = msg["sent_at"]
                print("No timestamp; use sent_at")
            if timestamp is None:
                date = "1970-01-01 00:00"
            else:
                date = datetime.fromtimestamp(timestamp / 1000.0).strftime(
                    "%Y-%m-%d %H:%M"
                )
            try:
                body = msg["body"]
            except KeyError:
                print(f"No body:\t\t{date}")
                body = ""
            if body is None:
                body = ""
            body = body.replace("`", "")  # stop md code sections forming
            body += "  "  # so that markdown newlines

            if "type" in msg.keys() and msg["type"] == "outgoing":
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

            try:
                attachments = msg["attachments"]
                for att in attachments:
                    file_name = att["fileName"]
                    # some file names are None
                    if file_name is None:
                        file_name = "None"
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
            except KeyError:
                print(f"No attachments for a message: {name}")


def fetch_data(db_file, key, manual=False, chat=None):
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
            cursor.execute("PRAGMA cipher_page_size = 4096")
            cursor.execute("PRAGMA kdf_iter = 64000")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

    query = "SELECT type, id, e164, name, profileName, members FROM conversations"
    if (chat is not None):
        chat = '","'.join(chat)
        query = query + f' WHERE name IN ("{chat}") OR profileName IN ("{chat}")'
    c.execute(query)
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
            if result[5] is None:
                print("Empty group.")
            else:
                for member in result[5].split():
                    c2.execute(
                        "SELECT name, profileName FROM conversations WHERE id=?",
                        [member],
                    )
                    for name in c2:
                        usable_members.append(name[0] if name else member)
                contacts[cid]["members"] = usable_members

    c.execute("SELECT json, conversationId " "FROM messages " "ORDER BY sent_at")
    for result in c:
        content = json.loads(result[0])
        cid = result[1]
        if cid and cid in convos:
            convos[cid].append(content)

    if db_file_decrypted.exists():
        db_file_decrypted.unlink()

    return convos, contacts


def fix_names(contacts):
    """Remove non-filesystem-friendly characters from names."""

    for key, item in contacts.items():
        contact_name = item["number"] if item["name"] is None else item["name"]
        if contacts[key]["name"] is not None:
            contacts[key]["name"] = "".join(x for x in contact_name if x.isalnum())

    return contacts


def create_html(dest):
    root = Path(__file__).resolve().parents[0]
    css_source = root / "style.css"
    css_dest = dest / "style.css"
    if os.path.isfile(css_source):
        shutil.copy2(css_source, css_dest)
    else:
        print(
            f"Stylesheet ({css_source}) not found."
            f"You might want to install one manually at {css_dest}."
        )

    md = markdown.Markdown()

    for sub in dest.iterdir():
        if sub.is_dir():
            name = sub.stem
            print(f"Doing html for {name}")
            path = sub / "index.md"
            # touch first
            open(path, "a")
            with path.open() as f:
                lines = f.readlines()
            lines = lines_to_msgs(lines)
            htfile = open(sub / "index.html", "w")
            print(
                "<!doctype html>"
                "<html lang='en'><head>"
                "<meta charset='utf-8'>"
                f"<title>{name}</title>"
                "<link rel=stylesheet href='../../style.css'>"
                "<link rel=stylesheet href='../style.css'>"
                "</head>"
                "<body>"
                f"<h1>{name}</h1>",
                file=htfile,
            )
            for msg in lines:
                date, sender, body = msg
                body = md.convert(body)

                # links
                p = r"(https{0,1}://\S*)"
                template = r"<a href='\1' target='_blank'>\1</a> "
                body = re.sub(p, template, body)

                # images
                soup = BeautifulSoup(body, "html.parser")
                imgs = soup.find_all("img")
                for im in imgs:
                    alt = im["alt"]
                    src = im["src"]
                    temp = BeautifulSoup(figure_template, "html.parser")
                    temp.figure.label["for"] = alt
                    temp.figure.label.img["src"] = src
                    temp.figure.label.img["alt"] = alt
                    temp.figure.input["id"] = alt
                    temp.figure.div.label["for"] = alt
                    temp.figure.div.label.div.img["src"] = src
                    temp.figure.div.label.div.img["alt"] = alt
                    im.replace_with(temp)

                # voice notes
                voices = soup.select(r"a[href*=Message\.m4a]")
                for v in voices:
                    href = v["href"]
                    temp = BeautifulSoup(audio_template, "html.parser")
                    temp.audio.source["src"] = href
                    v.insert_after(temp)

                # videos
                videos = soup.select(r"a[href*=\.mp4]")
                for v in videos:
                    href = v["href"]
                    temp = BeautifulSoup(video_template, "html.parser")
                    temp.video.source["src"] = href
                    v.insert_after(temp)

                print(
                    f"<div class=msg><span class=date>{date}</span>"
                    f"<span class=sender>{sender}</span>"
                    f"<span class=body>{soup.prettify()}</span></div>",
                    file=htfile,
                )
            print("</body></html>", file=htfile)


video_template = """
<video controls>
    <source src="src" type="video/mp4">
    </source>
</video>
"""

audio_template = """
<audio controls>
<source src="src" type="audio/mp4">
</audio>
"""

figure_template = """
<figure>
    <label for="src">
        <img load="lazy" src="src" alt="img">
    </label>
    <input class="modal-state" id="src" type="checkbox">
    <div class="modal">
        <label for="src">
            <div class="modal-content">
                <img class="modal-photo" loading="lazy" src="src" alt="img">
            </div>
        </label>
    </div>
</figure>
"""


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


def merge_attachments(media_new, media_old):
    for f in media_old.iterdir():
        if f.is_file():
            shutil.copy2(f, media_new)


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
            print("Copying files")
            dir_old = old / name
            if dir_old.is_dir():
                merge_attachments(sub / "media", dir_old / "media")
                path_new = sub / "index.md"
                path_old = dir_old / "index.md"
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
    "--chat", "-c", help="Comma-separated chat names to include. These are contact names or group names"
)
@click.option("--old", type=click.Path(), help="Path to previous export to merge with")
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
def main(
    dest, old=None, source=None, overwrite=False, manual=False, chat=None
):
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

    if chat:
        chat = chat.split(',')

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

    convos, contacts = fetch_data(db_file, key, manual=manual, chat=chat)
    contacts = fix_names(contacts)
    convos = copy_attachments(src, dest, convos, contacts)
    make_simple(dest, convos, contacts)
    if old:
        merge_with_old(dest, Path(old))
    create_html(dest)

    print(f"\nDone! Files exported to {dest}.")


if __name__ == "__main__":
    main()
