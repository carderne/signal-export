from datetime import datetime

from sigexport import html, models


def make_message(body: str) -> models.Message:
    return models.Message(
        date=datetime(2025, 1, 1, 12, 0, 0),
        sender="Alice",
        body=body,
        quote="",
        sticker=None,
        reactions=[],
        attachments=[],
    )


def test_link_at_end_of_message_does_not_swallow_closing_tag() -> None:
    """A trailing URL must not absorb the </p> Markdown emitted around it."""
    out = html.create_html("Alice", [make_message("look https://example.com")])

    assert 'href="https://example.com"' in out
    assert "&lt;/p&gt;" not in out
