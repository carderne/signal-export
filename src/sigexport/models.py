from __future__ import annotations

import json
import re
from collections import namedtuple
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass
class RawMessage:
    conversation_id: str
    id: str

    body: str
    type: str | None
    contact: str | None
    source: Any | None

    timestamp: int | None
    sent_at: int | None
    server_timestamp: int | None

    has_attachments: bool
    attachments: list[dict[str, str]]

    read_status: bool | None
    seen_status: bool | None

    call_history: dict[str, Any] | None
    reactions: list[dict[str, Any]]
    sticker: dict[str, Any] | None
    quote: dict[str, Any] | None

    def get_ts(self: RawMessage) -> int:
        if self.sent_at and self.server_timestamp:
            if self.server_timestamp < self.sent_at:
                return self.server_timestamp
            else:
                return self.sent_at
        elif self.sent_at:
            return self.sent_at
        elif self.timestamp:
            return self.timestamp
        return 0


@dataclass
class Contact:
    id: str
    name: str
    number: str
    profile_name: str
    is_group: bool
    members: list[str] | None


Contacts = dict[str, Contact]
Convos = dict[str, list[RawMessage]]

Reaction = namedtuple("Reaction", ["name", "emoji"])


def is_image(p: str) -> bool:
    suffix = p.split(".")
    return len(suffix) > 1 and suffix[-1] in [
        "png",
        "jpg",
        "jpeg",
        "gif",
        "tif",
        "tiff",
    ]


def is_audio(p: str) -> bool:
    suffix = p.split(".")
    return len(suffix) > 1 and suffix[-1] in [
        "m4a",
        "aac",
    ]


def is_video(p: str) -> bool:
    suffix = p.split(".")
    return len(suffix) > 1 and suffix[-1] in [
        "mp4",
    ]


@dataclass
class Attachment:
    name: str
    path: str


@dataclass
class Message:
    date: datetime
    sender: str
    body: str
    quote: str
    sticker: str
    reactions: list[Reaction]
    attachments: list[Attachment]

    def to_md(self: Message) -> str:
        date_str = self.date.strftime("%Y-%m-%d %H:%M:%S")
        body = self.body

        if len(self.reactions) > 0:
            reactions = [f"{r.name}: {r.emoji}" for r in self.reactions]
            body = body + "\n(- " + ", ".join(reactions) + " -)"

        if len(self.sticker) > 0:
            body = body + "\n(( " + self.sticker + " ))"

        for att in self.attachments:
            if is_image(att.path):
                body += "!"
            body += f"[{att.name}](./{att.path})  "

        return f"[{date_str}] {self.sender}: {self.quote}{body}\n"

    def comp(self: Message) -> tuple[datetime, str, str]:
        date = self.date.replace(second=0, microsecond=0)
        return (date, self.sender, self.body.replace("\n", "").replace(">", ""))

    def dict(self: Message) -> dict:
        msg_dict = asdict(self)
        msg_dict["date"] = msg_dict["date"].isoformat()
        return msg_dict

    def dict_str(self: Message) -> str:
        return json.dumps(self.dict(), ensure_ascii=False)


Chats = dict[str, list[Message]]


@dataclass
class MergeMessage:
    date: datetime
    sender: str
    body: str

    def to_message(self: MergeMessage) -> Message:
        body = self.body

        p_reactions = re.compile(r"\n\(- (.*) -\)")
        m_reactions = re.findall(p_reactions, body)
        reactions = []
        if m_reactions:
            reactions = [Reaction(*r.split(":")) for r in m_reactions[0].split(", ")]
        body = re.sub(p_reactions, "", body)

        p_stickers = r"\n\(\( (.*) \)\)"
        stickers = re.findall(p_stickers, self.body)
        sticker = stickers[0] if stickers else ""
        body = re.sub(p_stickers, "", body)

        p_quote = re.compile(r"\n> (.*)$")
        m_quote = re.findall(p_quote, self.body)
        quote = ""
        if m_quote:
            quote = "".join(m_quote)
        body = re.sub(p_quote, "", body)

        p_attachments = r"!{0,1}\[(.*?)\]\((.*?)\)"
        m_attachments = re.findall(p_attachments, self.body)
        attachments = []
        if m_attachments:
            attachments = [Attachment(name=g[0], path=g[1]) for g in m_attachments]
        body = re.sub(p_attachments, "", body)

        body = body.rstrip("\n")

        return Message(
            date=self.date,
            sender=self.sender,
            body=body,
            quote=quote,
            reactions=reactions,
            sticker=sticker,
            attachments=attachments,
        )
