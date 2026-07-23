from datetime import datetime, timedelta

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
