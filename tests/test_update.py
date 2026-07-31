from datetime import datetime, timedelta
from pathlib import Path

from sigexport import models, update


def msg(
    minute: int = 0,
    body: str = "hi",
    sender: str = "Alice",
    mid: str = "",
) -> models.Message:
    return models.Message(
        date=datetime(2024, 6, 1, 12, minute, 0),
        sender=sender,
        body=body,
        quote="",
        sticker=None,
        reactions=[],
        attachments=[],
        id=mid,
    )


def test_message_round_trips_through_dict() -> None:
    original = models.Message(
        date=datetime(2024, 6, 1, 14, 3, 5),
        sender="Alice",
        body="hello",
        quote="\n\n> earlier\n\n",
        sticker=models.Sticker(id="1", packId="p", packKey="k", emoji="x"),
        reactions=[models.Reaction("Bob", "👍")],
        attachments=[models.Attachment(name="cat.jpg", path="media/cat.jpg")],
        deleted=True,
        id="guid-1",
    )
    import json

    assert models.Message.from_dict(json.loads(original.dict_str())) == original


def test_merge_unions_by_id() -> None:
    existing = [msg(0, "one", mid="a"), msg(1, "two", mid="b")]
    new = [msg(2, "three", mid="c")]
    merged = update.merge_messages(existing, new)
    assert [m.body for m in merged] == ["one", "two", "three"]


def test_merge_new_wins_on_id_collision() -> None:
    """An edited message (same id) should replace the archived copy."""
    existing = [msg(0, "typo", mid="a")]
    new = [msg(0, "fixed", mid="a")]
    merged = update.merge_messages(existing, new)
    assert len(merged) == 1
    assert merged[0].body == "fixed"


def test_merge_sorts_by_date() -> None:
    existing = [msg(5, "late", mid="a")]
    new = [msg(1, "early", mid="b")]
    merged = update.merge_messages(existing, new)
    assert [m.body for m in merged] == ["early", "late"]


def test_merge_without_ids_falls_back_to_composite_key() -> None:
    """Legacy archives have no ids; dedup on date+sender+body instead."""
    existing = [msg(0, "same", sender="Alice")]
    new = [msg(0, "same", sender="Alice"), msg(1, "different")]
    merged = update.merge_messages(existing, new)
    assert len(merged) == 2  # the identical one de-duped, the new one kept


def test_load_archived_messages(tmp_path: Path) -> None:
    data = tmp_path / "data.json"
    lines = [msg(0, "one", mid="a").dict_str(), msg(1, "two", mid="b").dict_str()]
    data.write_text("\n".join(lines) + "\n", encoding="utf-8")
    loaded = update.load_archived_messages(data)
    assert [m.body for m in loaded] == ["one", "two"]


def test_load_archived_messages_skips_bad_lines(tmp_path: Path) -> None:
    data = tmp_path / "data.json"
    data.write_text(
        msg(0, "good", mid="a").dict_str() + "\n\nnot json\n", encoding="utf-8"
    )
    loaded = update.load_archived_messages(data)
    assert [m.body for m in loaded] == ["good"]


def contact(name: str) -> models.Contact:
    return models.Contact(
        id="c",
        serviceId="s",
        name=name,
        number="",
        profile_name="",
        is_group=False,
        members=None,
    )


def test_merge_into_archive_merges_existing_chat(tmp_path: Path) -> None:
    contacts = {"c": contact("Alice")}
    (tmp_path / "Alice").mkdir()
    archived = tmp_path / "Alice" / "data.json"
    archived.write_text(msg(0, "old", mid="a").dict_str() + "\n", encoding="utf-8")

    chat_dict = {"c": [msg(1, "new", mid="b")]}
    merged = update.merge_into_archive(chat_dict, contacts, tmp_path)
    assert [m.body for m in merged["c"]] == ["old", "new"]


def test_merge_into_archive_passes_through_new_chat(tmp_path: Path) -> None:
    """A chat with no existing folder is left as-is (first export of it)."""
    contacts = {"c": contact("Alice")}
    chat_dict = {"c": [msg(0, "new", mid="a")]}
    merged = update.merge_into_archive(chat_dict, contacts, tmp_path)
    assert [m.body for m in merged["c"]] == ["new"]
