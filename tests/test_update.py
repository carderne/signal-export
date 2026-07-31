from datetime import datetime, timedelta
from pathlib import Path

from sigexport import models, update


def msg(
    minute: int = 0,
    body: str = "hi",
    sender: str = "Alice",
    mid: str = "",
    disappearing: bool = False,
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
        disappearing=disappearing,
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


def test_load_archived_messages_raises_on_bad_line(tmp_path: Path) -> None:
    import pytest

    data = tmp_path / "data.json"
    data.write_text(
        msg(0, "good", mid="a").dict_str() + "\n\nnot json\n", encoding="utf-8"
    )
    with pytest.raises(update.ArchiveReadError):
        update.load_archived_messages(data)


def test_merge_into_archive_leaves_corrupt_chat_untouched(tmp_path: Path) -> None:
    """A chat whose store can't be fully read must not be rewritten (no loss)."""
    contacts = {"c": contact("Alice")}
    (tmp_path / "Alice").mkdir()
    corrupt = tmp_path / "Alice" / "data.json"
    corrupt.write_text("this is not json\n", encoding="utf-8")

    chat_dict = {"c": [msg(1, "new", mid="b")]}
    merged = update.merge_into_archive(chat_dict, contacts, tmp_path)
    # the corrupt chat is dropped from the write set, so its files stay as-is
    assert "c" not in merged
    assert corrupt.read_text(encoding="utf-8") == "this is not json\n"


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


# --- disappearing-message retention ---


def test_disappearing_forgotten_when_expired() -> None:
    """Default: a captured disappearing msg gone from the fresh read is dropped."""
    existing = [msg(0, "vanishing", mid="a", disappearing=True), msg(1, "keep", mid="b")]
    new = [msg(1, "keep", mid="b")]  # 'a' has expired from Signal
    merged = update.merge_messages(existing, new, reconcile_disappearing=True)
    assert [m.id for m in merged] == ["b"]


def test_disappearing_kept_with_flag() -> None:
    existing = [msg(0, "vanishing", mid="a", disappearing=True)]
    new: list[models.Message] = []
    merged = update.merge_messages(
        existing, new, reconcile_disappearing=True, keep_disappearing=True
    )
    assert [m.id for m in merged] == ["a"]


def test_disappearing_left_alone_when_not_reconciling() -> None:
    """Without --include-disappearing we can't tell expired from unread, so keep."""
    existing = [msg(0, "vanishing", mid="a", disappearing=True)]
    merged = update.merge_messages(existing, [], reconcile_disappearing=False)
    assert [m.id for m in merged] == ["a"]


def test_forget_disappearing_purges_all() -> None:
    existing = [msg(0, "gone", mid="a", disappearing=True), msg(1, "stay", mid="b")]
    new = [msg(2, "also gone", mid="c", disappearing=True)]
    merged = update.merge_messages(existing, new, forget_disappearing=True)
    assert [m.id for m in merged] == ["b"]


def test_disappearing_flag_round_trips() -> None:
    import json

    m = msg(0, "secret", mid="a", disappearing=True)
    back = models.Message.from_dict(json.loads(m.dict_str()))
    assert back.disappearing is True


# --- manifest ---


def test_manifest_round_trip_and_pins(tmp_path: Path) -> None:
    contacts = {"c1": contact("Alice"), "c2": contact("Bob")}
    contacts["c1"].display = "Alice"
    contacts["c2"].display = "Bob"
    update.save_manifest(tmp_path, contacts, ["c1", "c2"])

    pins = update.pinned_folders(tmp_path, contacts)
    assert pins == {"c1": "Alice", "c2": "Bob"}


def test_manifest_records_rename_alias(tmp_path: Path) -> None:
    contacts = {"c1": contact("Alice")}
    contacts["c1"].display = "Alice"
    update.save_manifest(tmp_path, contacts, ["c1"])

    # next run: same conversation, renamed to Bob (folder pinned to Alice)
    contacts["c1"].name = "Alice"
    contacts["c1"].display = "Bob"
    update.save_manifest(tmp_path, contacts, ["c1"])

    manifest = update.load_manifest(tmp_path)
    assert manifest["c1"]["display"] == "Bob"
    assert "Alice" in manifest["c1"]["aliases"]


def test_pinned_folders_ignores_unknown_conversations(tmp_path: Path) -> None:
    contacts = {"c1": contact("Alice")}
    contacts["c1"].display = "Alice"
    update.save_manifest(tmp_path, contacts, ["c1"])
    # a different run with a different conversation set
    assert update.pinned_folders(tmp_path, {"other": contact("Zed")}) == {}


def test_legacy_without_manifest_detection(tmp_path: Path) -> None:
    assert update.legacy_without_manifest(tmp_path) is False  # empty
    chat = tmp_path / "Alice"
    chat.mkdir()
    (chat / "data.json").write_text("{}", encoding="utf-8")
    assert update.legacy_without_manifest(tmp_path) is True  # chats, no manifest
    c = contact("Alice")
    c.display = "Alice"
    update.save_manifest(tmp_path, {"c1": c}, ["c1"])
    assert update.legacy_without_manifest(tmp_path) is False  # now has manifest


def test_toggling_nicknames_keeps_folder_stable(tmp_path: Path) -> None:
    """Plain export names by nickname; a later --update without --nicknames must
    keep the folder (via the manifest) instead of orphaning it."""
    from sigexport import utils

    # run 1: nickname naming -> folder "Nocturnal"
    nick = contact("Nocturnal")
    contacts = {"c1": nick}
    utils.fix_names(contacts, pinned=None)
    update.save_manifest(tmp_path, contacts, ["c1"])
    assert contacts["c1"].name == "Nocturnal"

    # run 2: same conversation, profile naming -> would be "KC" without a pin
    contacts = {"c1": contact("KC")}
    pins = update.pinned_folders(tmp_path, contacts)
    utils.fix_names(contacts, pinned=pins)
    assert contacts["c1"].name == "Nocturnal"  # folder held stable
    assert contacts["c1"].display == "KC"  # display follows the current run
