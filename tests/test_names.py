from sigexport import create, models, utils


def raw(**kwargs: object) -> models.RawMessage:
    base = dict(
        conversation_id="c",
        id="i",
        body="hi",
        type="incoming",
        source=None,
        timestamp=1,
        sent_at=1,
        server_timestamp=None,
        has_attachments=False,
        attachments=[],
        read_status=None,
        seen_status=None,
        call_history=None,
        reactions=[],
        sticker=None,
        quote=None,
    )
    base.update(kwargs)
    return models.RawMessage(**base)  # type: ignore[arg-type]


def contact(
    cid: str,
    name: str | None,
    service_id: str = "",
    is_group: bool = False,
) -> models.Contact:
    return models.Contact(
        id=cid,
        serviceId=service_id,
        name=name,
        number="",
        profile_name="",
        is_group=is_group,
        members=None,
    )


def names(contacts: models.Contacts) -> dict[str, str | None]:
    utils.fix_names(contacts)
    return {cid: c.name for cid, c in contacts.items()}


def test_distinct_names_are_kept() -> None:
    out = names({"1": contact("1", "Alice", "a"), "2": contact("2", "Bob", "b")})
    assert out == {"1": "Alice", "2": "Bob"}


def test_colliding_names_are_numbered() -> None:
    out = names({"1": contact("1", "Alex", "a"), "2": contact("2", "Alex", "b")})
    assert out == {"1": "Alex", "2": "Alex2"}


def test_nameless_contacts_do_not_all_become_none() -> None:
    """The core bug: multiple no-name contacts used to share one None/ folder."""
    out = names(
        {
            "1": contact("1", None, "a"),
            "2": contact("2", None, "b"),
            "3": contact("3", None, "c"),
        }
    )
    assert sorted(out.values()) == ["None", "None2", "None3"]


def test_suffix_assignment_is_deterministic_by_service_id() -> None:
    """Insertion order must not decide who keeps the bare name."""
    forward = names({"1": contact("1", "Sam", "aaa"), "2": contact("2", "Sam", "bbb")})
    reverse = names({"2": contact("2", "Sam", "bbb"), "1": contact("1", "Sam", "aaa")})
    assert forward == reverse == {"1": "Sam", "2": "Sam2"}


def test_note_to_self_label_is_filesystem_safe() -> None:
    out = names({"1": contact("1", "Note to Self", "self")})
    assert out == {"1": "NotetoSelf"}


def test_spaces_and_punctuation_are_stripped() -> None:
    out = names({"1": contact("1", "John Smith", "a")})
    assert out == {"1": "JohnSmith"}


def test_emoji_only_name_falls_back_to_unnamed() -> None:
    # a name that demojizes to nothing alphanumeric... use a bare symbol
    out = names({"1": contact("1", "!!!", "a")})
    assert out == {"1": "unnamed"}


def test_display_drops_the_folder_dedup_suffix() -> None:
    """Folders disambiguate (Alice / Alice2) but both still read "Alice"."""
    contacts = {"1": contact("1", "Alice", "a"), "2": contact("2", "Alice", "b")}
    utils.fix_names(contacts)
    assert (contacts["1"].name, contacts["2"].name) == ("Alice", "Alice2")
    assert (contacts["1"].display, contacts["2"].display) == ("Alice", "Alice")


def test_group_sender_uses_display_not_suffixed_folder() -> None:
    """A message from the de-duplicated "Alice2" should still read "Alice"."""
    contacts = {
        "a": contact("a", "Alice", "sid-a"),
        "b": contact("b", "Alice", "sid-b"),
    }
    utils.fix_names(contacts)  # a -> Alice, b -> Alice2 (by serviceId order)
    msg = create.create_message(raw(source="sid-b"), "grp", True, contacts)
    assert msg.sender == "Alice"


def test_one_to_one_sender_uses_display() -> None:
    contacts = {
        "a": contact("a", "Alice", "sid-a"),
        "b": contact("b", "Alice", "sid-b"),
    }
    utils.fix_names(contacts)
    # a 1:1 message in conversation "b" (the de-duplicated Alice2)
    msg = create.create_message(raw(conversation_id="b"), "Alice2", False, contacts)
    assert msg.sender == "Alice"


def test_own_reactions_show_as_me_not_note_to_self() -> None:
    """Your own reactions must read 'Me', not the owner folder's 'Note to Self'."""
    owner = contact("me", "Note to Self", "sid-me")
    owner.is_owner = True
    owner.display = "NotetoSelf"  # as fix_names would set it
    contacts = {"me": owner, "c": contact("c", "Alice", "sid-a")}
    contacts["c"].display = "Alice"
    msg = create.create_message(
        raw(conversation_id="c", reactions=[{"fromId": "me", "emoji": "👍"}]),
        "Alice",
        False,
        contacts,
    )
    assert msg.reactions == [models.Reaction("Me", "👍")]


def test_other_peoples_reactions_use_their_display() -> None:
    contacts = {"c": contact("c", "Alice", "sid-a")}
    contacts["c"].display = "Alice"
    msg = create.create_message(
        raw(conversation_id="c", reactions=[{"fromId": "c", "emoji": "❤️"}]),
        "Alice",
        False,
        contacts,
    )
    assert msg.reactions == [models.Reaction("Alice", "❤️")]


def test_pinned_folder_survives_a_rename() -> None:
    """A renamed contact keeps its archive folder but shows the new name."""
    contacts = {"a": contact("a", "Bob", "sid-a")}  # was "Alice" last export
    utils.fix_names(contacts, pinned={"a": "Alice"})
    assert contacts["a"].name == "Alice"  # folder unchanged
    assert contacts["a"].display == "Bob"  # display follows the rename


def test_new_contacts_avoid_pinned_folders() -> None:
    """A new "Alice" can't take a folder pinned to someone else."""
    contacts = {
        "a": contact("a", "Alice", "sid-a"),  # pinned to Alice
        "b": contact("b", "Alice", "sid-b"),  # new, must not clash
    }
    utils.fix_names(contacts, pinned={"a": "Alice"})
    assert contacts["a"].name == "Alice"
    assert contacts["b"].name == "Alice2"
