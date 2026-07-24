from sigexport import models, utils


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
