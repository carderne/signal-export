import os
import re
import shutil
from pathlib import Path

import markdown
from bs4 import BeautifulSoup
from typer import secho

from sigexport import models, templates
from sigexport.logging import log


def prep_html(dest: Path) -> None:
    """Prepare CSS etc"""
    root = Path(__file__).resolve().parents[0]
    css_source = root / "style.css"
    css_dest = dest / "style.css"
    if os.path.isfile(css_source):
        shutil.copy2(css_source, css_dest)
    else:
        secho(
            f"Stylesheet ({css_source}) not found."
            f"You might want to install one manually at {css_dest}."
        )


def create_html(
    name: str, messages: list[models.Message], msgs_per_page: int = 100
) -> str:
    """Create HTML version from Markdown input."""

    log(f"\tDoing html for {name}")
    # touch first
    ht_content = ""
    last_page = int(len(messages) / msgs_per_page)

    page_num = 0
    for i, msg in enumerate(messages):
        if i % msgs_per_page == 0:
            nav = "\n"
            if i > 0:
                nav += "</div>"
            nav += f"<div class=page id=pg{page_num}>"
            nav += "<nav>"
            nav += "<div class=prev>"
            if page_num != 0:
                nav += f"<a href=#pg{page_num - 1}>PREV</a>"
            else:
                nav += "PREV"
            nav += "</div><div class=next>"
            if page_num != last_page:
                nav += f"<a href=#pg{page_num + 1}>NEXT</a>"
            else:
                nav += "NEXT"
            nav += "</div></nav>\n"
            ht_content += nav
            page_num += 1

        sender = msg.sender
        date = msg.date.date().isoformat()
        time = msg.date.time().replace(microsecond=0).isoformat()

        reactions = " ".join(f"{r.name}: {r.emoji}" for r in msg.reactions)
        quote = ""
        if msg.quote:
            quote = f"<div class=quote>{msg.quote.replace('>', '')}</div>"

        body = msg.body
        try:
            body = markdown.Markdown().convert(body)
        except RecursionError:
            log(f"Maximum recursion on message {body}, not converted")

        # links
        p = re.compile(r"(https{0,1}://\S*)")
        a_template = r"<a href='\1' target='_blank'>\1</a> "
        body = re.sub(p, a_template, body)

        soup = BeautifulSoup(body, "html.parser")
        # attachments
        for att in msg.attachments:
            path = att.path
            src = f"./{path}"
            if models.is_image(path):
                temp = templates.figure.format(src=src, alt=att.name)
            elif models.is_audio(path):
                temp = templates.audio.format(src=src)
            elif models.is_video(path):
                temp = templates.video.format(src=src)
            else:
                temp = None
            if temp:
                soup.append(BeautifulSoup(temp, "html.parser"))

        cl = "msg me" if sender == "Me" else "msg"
        ht_content += templates.message.format(
            cl=cl,
            date=date,
            time=time,
            sender=sender,
            quote=quote,
            body=soup,
            reactions=reactions,
        )
    ht_text = templates.html.format(
        name=name,
        last_page=last_page,
        content=ht_content,
    )
    ht_text = BeautifulSoup(ht_text, "html.parser").prettify()
    ht_text = re.compile(r"^(\s*)", re.MULTILINE).sub(r"\1\1\1\1", ht_text)
    return ht_text
