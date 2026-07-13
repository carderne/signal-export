from pathlib import Path

from sqlcipher3 import dbapi2

from sigexport import create, files, models


def test_copy_attachments_sanitizes_filesystem_reserved_characters(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    attachment_path = source / "attachments.noindex" / "ab" / "cd"
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_bytes(b"attachment data")

    attachment = {
        "fileName": 'report<draft>?"v2"\\copy.pdf',
        "contentType": "application/pdf",
        "path": "ab/cd",
        "version": "0",
    }
    message = models.RawMessage(
        conversation_id="contact",
        id="message",
        body="",
        type="incoming",
        source=None,
        timestamp=1,
        sent_at=None,
        server_timestamp=None,
        has_attachments=True,
        attachments=[attachment],
        read_status=None,
        seen_status=None,
        call_history=None,
        reactions=[],
        sticker=None,
        quote=None,
    )
    contacts = {
        "contact": models.Contact(
            id="contact",
            serviceId="service",
            name="Alice",
            number="",
            profile_name="",
            is_group=False,
            members=None,
        )
    }
    destination = tmp_path / "export"

    with dbapi2.connect(":memory:") as connection:
        files.copy_attachments(
            source,
            destination,
            {"contact": [message]},
            contacts,
            connection.cursor(),
        )

    safe_name = attachment["fileName"]
    assert not set('<>:"/\\|?*') & set(safe_name)
    assert (
        destination / "Alice" / "media" / safe_name
    ).read_bytes() == b"attachment data"

    rendered = create.create_message(message, "Alice", False, contacts).to_md()
    assert safe_name in rendered
