from pathlib import Path

from sigexport import create, files, models


def make_message(sticker: dict) -> models.RawMessage:
    return models.RawMessage(
        conversation_id="contact",
        id="message",
        body="",
        type="incoming",
        source=None,
        timestamp=1,
        sent_at=None,
        server_timestamp=None,
        has_attachments=False,
        attachments=[],
        read_status=None,
        seen_status=None,
        call_history=None,
        reactions=[],
        sticker=sticker,
        quote=None,
    )


CONTACTS = {
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


def render(message: models.RawMessage) -> str:
    return create.create_message(message, "Alice", False, CONTACTS).to_md()


def test_missing_sticker_file_falls_back_to_emoji(tmp_path: Path) -> None:
    """A sticker we never downloaded should not be linked as if we had."""
    sticker = {"stickerId": 102, "packId": "pack", "packKey": "key", "emoji": "🐺"}
    message = make_message(sticker)
    destination = tmp_path / "export"
    destination.mkdir()

    files.check_stickers_existence({"contact": [message]}, CONTACTS, destination)

    assert sticker["extension"] is None
    rendered = render(message)
    assert "(( 🐺 ))" in rendered
    assert "exported_stickers" not in rendered


def test_present_sticker_file_is_linked(tmp_path: Path) -> None:
    sticker = {"stickerId": 102, "packId": "pack", "packKey": "key", "emoji": "🐺"}
    message = make_message(sticker)
    destination = tmp_path / "export"
    (destination / "exported_stickers" / "pack").mkdir(parents=True)
    (destination / "exported_stickers" / "pack" / "102.webp").write_bytes(b"sticker")

    files.check_stickers_existence({"contact": [message]}, CONTACTS, destination)

    assert sticker["extension"] == "webp"
    assert "[🐺](../exported_stickers/pack/102.webp)" in render(message)


def test_sticker_without_emoji_still_gets_a_label() -> None:
    """Signal omits the emoji entirely for stickers that have none assigned."""
    message = make_message({"stickerId": 102, "packId": "pack", "packKey": "key"})
    assert "(( sticker ))" in render(message)


def test_sticker_survives_skipped_sticker_export() -> None:
    """Without --stickers nothing backfills the extension, so don't invent a link."""
    message = make_message(
        {"stickerId": 102, "packId": "pack", "packKey": "key", "emoji": "🐺"}
    )
    rendered = render(message)
    assert "(( 🐺 ))" in rendered
    assert "exported_stickers" not in rendered
