import json

from sigexport import create, html, models

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


def raw(edits: list[dict], body: str = "col") -> models.RawMessage:
    return models.RawMessage(
        conversation_id="c",
        id="m",
        body=body,
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
        edits=edits,
    )


def build(edits: list[dict], body: str = "col") -> models.Message:
    return create.create_message(raw(edits, body), "Aya", False, CONTACTS)


def test_current_body_comes_from_edit_history_not_column() -> None:
    # editHistory is newest-first; the body column is stale here
    m = build([{"timestamp": 3, "body": "newest"}, {"timestamp": 1, "body": "old"}], "STALE")
    assert m.body.strip() == "newest"


def test_edits_are_prior_versions_oldest_first() -> None:
    m = build(
        [
            {"timestamp": 3, "body": "v3"},
            {"timestamp": 2, "body": "v2"},
            {"timestamp": 1, "body": "v1"},
        ]
    )
    assert [e.body for e in m.edits] == ["v1", "v2"]  # excludes current, oldest first


def test_single_edit_history_entry_is_not_an_edit() -> None:
    m = build([{"timestamp": 1, "body": "only"}], "col")
    assert m.edits == []
    assert m.body.strip() == "col"


def test_no_edit_history() -> None:
    m = build([], "plain")
    assert m.edits == []
    assert m.body.strip() == "plain"


def test_edits_serialize_with_iso_dates() -> None:
    m = build([{"timestamp": 2, "body": "new"}, {"timestamp": 1, "body": "old"}])
    d = json.loads(m.dict_str())
    assert d["edits"][0]["body"] == "old"
    assert isinstance(d["edits"][0]["date"], str)  # datetime -> isoformat


def test_html_shows_edit_disclosure_with_prior_versions() -> None:
    m = build([{"timestamp": 2, "body": "current"}, {"timestamp": 1, "body": "was original"}])
    out = html.create_html("Aya", [m])
    assert 'class="edits"' in out
    assert "was original" in out
    assert "current" in out


def test_html_no_disclosure_when_not_edited() -> None:
    out = html.create_html("Aya", [build([], "plain")])
    assert 'class="edits"' not in out
