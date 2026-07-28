from sigexport import create, models


def raw(**kwargs: object) -> models.RawMessage:
    base = dict(
        conversation_id="c",
        id="i",
        body="",
        type="incoming",
        source=None,
        timestamp=1000,
        sent_at=1000,
        server_timestamp=None,
        has_attachments=False,
        attachments=[],
        read_status=None,
        seen_status=None,
        call_history=None,
        reactions=[],
        sticker=None,
        quote=None,
        deleted=False,
        has_visual_media=False,
    )
    base.update(kwargs)
    return models.RawMessage(**base)  # type: ignore[arg-type]


CONTACTS = {
    "c": models.Contact(
        id="c",
        serviceId="s",
        name="Aya",
        number="",
        profile_name="",
        is_group=False,
        members=None,
    )
}


def build(msg: models.RawMessage) -> models.Message:
    return create.create_message(msg, "Aya", False, CONTACTS)


def test_image_only_reply_is_labelled_photo() -> None:
    """A reply to an image (no quoted text) should still read as a reply."""
    msg = raw(
        body="nice",
        quote={"text": None, "attachments": [{"contentType": "image/jpeg"}]},
    )
    assert "> Photo" in build(msg).quote


def test_voice_note_reply_is_labelled() -> None:
    msg = raw(body="lol", quote={"attachments": [{"contentType": "audio/aac"}]})
    assert "> Voice message" in build(msg).quote


def test_reply_with_text_keeps_text() -> None:
    msg = raw(body="agreed", quote={"text": "original words"})
    assert "> original words" in build(msg).quote


def test_reply_with_no_text_and_no_attachments_has_no_quote() -> None:
    msg = raw(body="hmm", quote={"text": ""})
    assert build(msg).quote == ""


def test_unexported_visual_attachment_gets_media_placeholder() -> None:
    """Attachments the export skipped shouldn't vanish into a blank message."""
    msg = raw(body="here", has_attachments=1, has_visual_media=1, attachments=[])
    atts = build(msg).attachments
    assert len(atts) == 1
    assert atts[0].missing_kind == "media"


def test_unexported_file_attachment_gets_generic_placeholder() -> None:
    msg = raw(body="doc", has_attachments=1, has_visual_media=0, attachments=[])
    atts = build(msg).attachments
    assert len(atts) == 1
    assert atts[0].missing_kind == "attachment"


def test_no_placeholder_when_message_had_no_attachments() -> None:
    assert build(raw(body="plain")).attachments == []
