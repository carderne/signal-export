from datetime import datetime, timedelta
from pathlib import Path

from sigexport import html, models


def msg(
    offset_minutes: int = 0,
    sender: str = "Alice",
    body: str = "hello",
    **kwargs: object,
) -> models.Message:
    base = datetime(2024, 6, 1, 14, 0, 0)
    return models.Message(
        date=base + timedelta(minutes=offset_minutes),
        sender=sender,
        body=body,
        quote=kwargs.get("quote", ""),  # type: ignore[arg-type]
        sticker=kwargs.get("sticker"),  # type: ignore[arg-type]
        reactions=kwargs.get("reactions", []),  # type: ignore[arg-type]
        attachments=kwargs.get("attachments", []),  # type: ignore[arg-type]
        deleted=kwargs.get("deleted", False),  # type: ignore[arg-type]
        call=kwargs.get("call", False),  # type: ignore[arg-type]
        missed=kwargs.get("missed", False),  # type: ignore[arg-type]
    )


def test_theme_switcher_and_assets_present() -> None:
    out = html.create_html("Chat", [msg()])
    assert 'data-theme-choice="auto"' in out
    assert 'data-theme-choice="light"' in out
    assert 'data-theme-choice="dark"' in out
    assert "chat.js" in out
    assert "style.css" in out


def test_name_is_escaped_not_injected() -> None:
    out = html.create_html("<script>evil</script>", [msg()])
    assert "<script>evil" not in out
    assert "&lt;script&gt;evil" in out


def test_consecutive_messages_are_grouped() -> None:
    """A quick follow-up from the same sender hides the repeated meta header."""
    out = html.create_html("Chat", [msg(0), msg(1)])
    assert out.count('class="sender"') == 1
    assert "msg cont" in out


def test_sender_change_breaks_grouping() -> None:
    out = html.create_html("Chat", [msg(0, sender="Alice"), msg(1, sender="Bob")])
    assert out.count('class="sender"') == 2


def test_day_divider_between_dates() -> None:
    out = html.create_html("Chat", [msg(0), msg(60 * 24)])
    assert out.count('class="day"') == 2


def test_pagination_splits_pages_and_adds_pager() -> None:
    messages = [msg(i) for i in range(5)]
    out = html.create_html("Chat", messages, msgs_per_page=2)
    assert out.count('class="page"') == 3
    assert 'class="pager"' in out
    assert "/ 3" in out


def test_page_jump_field_is_readonly_until_js() -> None:
    """The jump input ships readonly so the arrows still work with JS off."""
    messages = [msg(i) for i in range(5)]
    out = html.create_html("Chat", messages, msgs_per_page=2)
    assert 'class="pagejump"' in out
    assert 'max="3"' in out
    assert "readonly" in out


def test_no_pager_on_single_page() -> None:
    out = html.create_html("Chat", [msg()], msgs_per_page=100)
    assert 'class="pager"' not in out


def test_non_media_attachment_becomes_file_link() -> None:
    attachment = models.Attachment(name="report.pdf", path="media/report.pdf")
    out = html.create_html("Chat", [msg(attachments=[attachment])])
    assert 'class="file"' in out
    assert "report.pdf" in out


def test_image_attachment_gets_lightbox() -> None:
    attachment = models.Attachment(name="cat.jpg", path="media/cat.jpg")
    out = html.create_html("Chat", [msg(attachments=[attachment])])
    assert "modal-state" in out
    assert "media/cat.jpg" in out


def test_deleted_message_shows_placeholder_not_blank() -> None:
    """A message deleted for everyone should read as deleted, not an empty bubble."""
    out = html.create_html("Chat", [msg(body="", deleted=True)])
    assert "deleted" in out
    assert "This message was deleted" in out


def test_deleted_message_hides_original_content() -> None:
    """Any residual body/attachment must not leak out of a deleted message."""
    attachment = models.Attachment(name="secret.jpg", path="media/secret.jpg")
    out = html.create_html(
        "Chat", [msg(body="oops wrong chat", deleted=True, attachments=[attachment])]
    )
    assert "oops wrong chat" not in out
    assert "secret.jpg" not in out
    assert "This message was deleted" in out


def test_deleted_message_markdown_placeholder() -> None:
    """The Markdown export should not emit a blank line for a deleted message."""
    rendered = msg(body="", deleted=True).to_md()
    assert "(This message was deleted)" in rendered


def test_call_renders_as_event_not_bubble() -> None:
    out = html.create_html("Chat", [msg(body="Incoming voice call (accepted)", call=True)])
    assert 'class="event' in out
    assert "Incoming voice call (accepted)" in out
    # not a chat bubble
    assert 'class="msg' not in out


def test_missed_call_gets_missed_class() -> None:
    out = html.create_html("Chat", [msg(body="Missed voice call", call=True, missed=True)])
    assert "event call missed" in out


def test_video_call_uses_video_icon() -> None:
    out = html.create_html(
        "Chat", [msg(body="Outgoing video call (accepted)", call=True)]
    )
    assert "\U0001f4f9" in out  # video camera


def test_missing_attachment_shows_placeholder(tmp_path: Path) -> None:
    """An image whose file isn't in the export reads as excluded, not blank."""
    attachment = models.Attachment(name="photo.jpg", path="media/photo.jpg")
    # tmp_path has no media/photo.jpg, so it counts as not exported
    out = html.create_html(
        "Chat", [msg(body="pic", attachments=[attachment])], media_dir=tmp_path
    )
    assert "Image not exported" in out
    assert "<img" not in out


def test_present_attachment_renders_normally(tmp_path: Path) -> None:
    attachment = models.Attachment(name="photo.jpg", path="media/photo.jpg")
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "photo.jpg").write_bytes(b"x")
    out = html.create_html(
        "Chat", [msg(body="pic", attachments=[attachment])], media_dir=tmp_path
    )
    assert "not exported" not in out
    assert "media/photo.jpg" in out
