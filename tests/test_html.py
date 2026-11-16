import json
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


def test_link_at_end_of_message_does_not_swallow_closing_tag() -> None:
    """A trailing URL must not absorb the </p> Markdown emitted around it (#225)."""
    out = html.create_html("Chat", [msg(body="look https://example.com")])
    assert 'href="https://example.com"' in out
    assert "&lt;/p&gt;" not in out


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


def test_image_reply_renders_as_quote() -> None:
    """A reply whose quote is just a photo label still shows the reply block."""
    out = html.create_html("Chat", [msg(body="nice", quote="\n\n> Photo\n\n")])
    assert 'class="quote"' in out
    assert "Photo" in out


def test_sentinel_attachment_renders_placeholder() -> None:
    """An attachment marked missing (no file at all) shows its placeholder."""
    att = models.Attachment(name="", path="", missing_kind="media")
    out = html.create_html("Chat", [msg(body="here", attachments=[att])])
    assert "Media not exported" in out
    assert "<img" not in out


def test_messages_carry_anchor_ids() -> None:
    """Every bubble gets a stable id so search can jump straight to it."""
    out = html.create_html("Chat", [msg(0), msg(1, sender="Bob")], msgs_per_page=5)
    assert 'id="m0-0"' in out
    assert 'id="m0-1"' in out


def test_search_record_ids_match_rendered_anchors() -> None:
    """The index id for a message is exactly the DOM id it's rendered with."""
    messages = [msg(i) for i in range(7)]
    out = html.create_html("Chat", messages, msgs_per_page=3)
    records = html.search_records(messages, 3)
    assert [r["id"] for r in records] == [
        "m0-0",
        "m0-1",
        "m0-2",
        "m1-0",
        "m1-1",
        "m1-2",
        "m2-0",
    ]
    for r in records:
        assert f'id="{r["id"]}"' in out


def test_search_records_skip_deleted_and_empty() -> None:
    """Deleted/blank bubbles are left out, but later ids stay aligned."""
    messages = [
        msg(0, body="keep me"),
        msg(1, body="", deleted=True),
        msg(2, body="   "),
        msg(3, body="Missed voice call", call=True, missed=True),
    ]
    records = html.search_records(messages, 100)
    assert {r["id"] for r in records} == {"m0-0", "m0-3"}
    texts = [r["t"] for r in records]
    assert "keep me" in texts
    assert "Missed voice call" in texts


def test_write_search_index_is_a_js_global(tmp_path: Path) -> None:
    chats: list[dict[str, object]] = [
        {
            "folder": "Alice",
            "title": "Alice",
            "messages": [
                {"id": "m0-0", "d": "2024-06-01T00:00:00", "s": "Alice", "t": "hi"}
            ],
        }
    ]
    html.write_search_index(tmp_path, chats)
    content = (tmp_path / "search-index.js").read_text(encoding="utf-8")
    assert content.startswith("window.SIGEXPORT_SEARCH = ")
    payload = json.loads(content[len("window.SIGEXPORT_SEARCH = ") :].rstrip(";\n"))
    assert payload["chats"][0]["messages"][0]["t"] == "hi"


def test_write_search_index_keeps_unicode_readable(tmp_path: Path) -> None:
    """Non-ASCII is written verbatim, not \\uXXXX, so search matches it."""
    chats: list[dict[str, object]] = [
        {
            "folder": "C",
            "title": "C",
            "messages": [{"id": "m0-0", "d": "x", "s": "s", "t": "café ☕"}],
        }
    ]
    html.write_search_index(tmp_path, chats)
    content = (tmp_path / "search-index.js").read_text(encoding="utf-8")
    assert "café ☕" in content
