from datetime import datetime

from bs4 import BeautifulSoup

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


def hrefs(body: str) -> list[str]:
    out = html.create_html(name="Alice", messages=[make_message(body)])
    soup = BeautifulSoup(out, "html.parser")
    return [str(a["href"]) for a in soup.select("span.body a")]


def test_link_at_end_of_message_does_not_swallow_closing_tag() -> None:
    """The body is already HTML, so a trailing URL is followed by "</p>"."""
    assert hrefs("see https://ex.com") == ["https://ex.com"]


def test_link_before_newline_does_not_swallow_break_tag() -> None:
    """A newline after a link becomes "<br />", which must stay outside it."""
    assert hrefs("see https://ex.com  \nnext") == ["https://ex.com"]
