from datetime import datetime
from pathlib import Path

from sigexport import merge, models


def test_merge_keeps_new_chat_when_old_markdown_is_missing(tmp_path: Path) -> None:
    message = models.Message(
        date=datetime(2026, 1, 1),
        sender="Alice",
        body="new message",
        quote="",
        sticker=None,
        reactions=[],
        attachments=[],
    )
    chats = {"contact": [message]}
    contacts = {
        "contact": models.Contact(
            id="contact",
            serviceId="service",
            name="Alice",
            number="",
            profile_name="",
            is_group=False,
            members=None,
        )
    }
    destination = tmp_path / "new"
    old = tmp_path / "old"
    (destination / "Alice" / "media").mkdir(parents=True)
    (old / "Alice" / "media").mkdir(parents=True)

    merged = merge.merge_with_old(chats, contacts, destination, old)

    assert merged == chats
