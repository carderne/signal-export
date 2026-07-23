import os
import re
import shutil
from datetime import date as date_type
from datetime import timedelta
from html import escape
from pathlib import Path

import markdown
from bs4 import BeautifulSoup
from typer import secho

from sigexport import models, templates
from sigexport.logging import log

ASSETS = ("style.css", "chat.js")

# messages closer together than this from the same sender get grouped
GROUP_WINDOW = timedelta(minutes=5)

URL_PATTERN = re.compile(r"(https{0,1}://\S*)")


def prep_html(dest: Path) -> None:
    """Copy the stylesheet and script to the export root."""
    root = Path(__file__).resolve().parents[0]
    for asset in ASSETS:
        source = root / asset
        target = dest / asset
        if os.path.isfile(source):
            shutil.copy2(source, target)
        else:
            secho(
                f"Asset ({source}) not found."
                f"You might want to install one manually at {target}."
            )


def make_pager(page_num: int, last_page: int) -> str:
    """Build the pagination controls for one page."""
    if last_page == 0:
        return ""

    def link(target: int, symbol: str, label: str) -> str:
        if target == page_num:
            return templates.pager_disabled.format(symbol=symbol)
        return templates.pager_link.format(page_num=target, symbol=symbol, label=label)

    return templates.pager.format(
        first=link(0, "&laquo;", "First page"),
        prev=link(max(page_num - 1, 0), "&lsaquo;", "Previous page"),
        page_num=page_num + 1,
        total_pages=last_page + 1,
        next=link(min(page_num + 1, last_page), "&rsaquo;", "Next page"),
        last=link(last_page, "&raquo;", "Last page"),
    )


def make_body(msg: models.Message, fid: str) -> str:
    """Render the message body, with attachments and stickers appended."""
    body = msg.body
    try:
        body = markdown.Markdown().convert(body)
    except RecursionError:
        log(f"Maximum recursion on message {body}, not converted")

    body = re.sub(URL_PATTERN, r"<a href='\1' target='_blank'>\1</a> ", body)

    soup = BeautifulSoup(body, "html.parser")
    for i, att in enumerate(msg.attachments):
        path = att.path
        src = f"./{path}"
        alt = escape(att.name, quote=True)
        if models.is_image(path):
            temp = templates.figure.format(fid=f"{fid}-{i}", src=src, alt=alt)
        elif models.is_audio(path):
            temp = templates.audio.format(src=src)
        elif models.is_video(path):
            temp = templates.video.format(src=src)
        else:
            temp = templates.file_link.format(src=src, name=alt)
        soup.append(BeautifulSoup(temp, "html.parser"))

    if msg.sticker:
        label = escape(msg.sticker.label, quote=True)
        sticker_path = msg.sticker.get_path()
        if sticker_path:
            temp = templates.figure.format(
                fid=f"{fid}-sticker", src=f"../{sticker_path}", alt=label
            )
        else:
            temp = f"(( {label} ))"
        soup.append(BeautifulSoup(temp, "html.parser"))

    return str(soup)


def make_message(msg: models.Message, fid: str, show_meta: bool) -> str:
    """Render a single message bubble."""
    meta = ""
    if show_meta:
        meta = templates.meta.format(
            sender=escape(msg.sender),
            iso=msg.date.isoformat(),
            date=msg.date.strftime("%Y-%m-%d %H:%M:%S"),
            time=msg.date.time().replace(microsecond=0).isoformat(),
        )

    quote = ""
    quote_text = msg.quote.replace(">", "").strip()
    if quote_text:
        quote = templates.quote.format(text=escape(quote_text).replace("\n", "<br>"))

    reactions = ""
    if msg.reactions:
        chips = "".join(
            templates.reaction.format(
                emoji=escape(r.emoji or ""), name=escape(r.name or "Unknown")
            )
            for r in msg.reactions
        )
        reactions = templates.reactions.format(chips=chips)

    cl = "msg me" if msg.sender == "Me" else "msg"
    if not show_meta:
        cl += " cont"

    return templates.message.format(
        cl=cl,
        meta=meta,
        quote=quote,
        body=make_body(msg, fid),
        reactions=reactions,
    )


def create_html(
    name: str, messages: list[models.Message], msgs_per_page: int = 100
) -> str:
    """Create HTML version from Markdown input."""

    log(f"\tDoing html for {name}")
    total_pages = max(1, -(-len(messages) // msgs_per_page))
    last_page = total_pages - 1

    pages = []
    for page_num in range(total_pages):
        chunk = messages[page_num * msgs_per_page : (page_num + 1) * msgs_per_page]
        content = ""
        prev: models.Message | None = None
        prev_day: date_type | None = None
        for i, msg in enumerate(chunk):
            day = msg.date.date()
            if day != prev_day:
                content += templates.day.format(date=day.isoformat())
                prev = None  # always show the sender after a day break
            prev_day = day

            grouped = (
                prev is not None
                and prev.sender == msg.sender
                and msg.date - prev.date < GROUP_WINDOW
            )
            content += make_message(msg, f"m{page_num}-{i}", show_meta=not grouped)
            prev = msg

        pages.append(
            templates.page.format(
                page_num=page_num,
                pager=make_pager(page_num, last_page),
                content=content,
            )
        )

    ht_text = templates.html.format(
        name=escape(name),
        last_page=last_page,
        content="".join(pages),
    )
    ht_text = BeautifulSoup(ht_text, "html.parser").prettify()
    ht_text = re.compile(r"^(\s*)", re.MULTILINE).sub(r"\1\1\1\1", ht_text)
    return ht_text
