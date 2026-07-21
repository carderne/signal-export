import base64
import hashlib
import hmac
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from sqlcipher3 import dbapi2

from sigexport import create, files, models


def write_encrypted_attachment(src_path: Path, plaintext: bytes) -> dict[str, str]:
    """Build a v2 (locally encrypted) attachment on disk, as Signal stores it."""
    cipher_key = bytes(range(files.CIPHER_KEY_SIZE))
    mac_key = bytes(range(files.MAC_KEY_SIZE))
    iv = bytes(files.IV_SIZE)

    padding = -len(plaintext) % AES.block_size
    ciphertext = AES.new(cipher_key, AES.MODE_CBC, iv).encrypt(
        plaintext + bytes(padding)
    )
    mac = hmac.new(mac_key, iv + ciphertext, hashlib.sha256).digest()
    src_path.write_bytes(iv + ciphertext + mac)

    return {
        "localKey": base64.b64encode(cipher_key + mac_key).decode(),
        "size": str(len(plaintext)),
        "version": "2",
    }


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


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_decrypt_attachment_without_type_detection(tmp_path: Path) -> None:
    """copy_attachments() calls this with detect_file_type defaulted to False."""
    src_path = tmp_path / "encrypted"
    att = write_encrypted_attachment(src_path, b"attachment data")
    dst_path = tmp_path / "decrypted.pdf"

    files.decrypt_attachment(att, src_path, dst_path)

    assert dst_path.read_bytes() == b"attachment data"


def test_decrypt_attachment_detects_extension(tmp_path: Path) -> None:
    src_path = tmp_path / "encrypted"
    att = write_encrypted_attachment(src_path, PNG)
    dst_path = tmp_path / "decrypted"

    files.decrypt_attachment(att, src_path, dst_path, detect_file_type=True)

    assert dst_path.with_suffix(".png").read_bytes() == PNG


def test_decrypt_attachment_rejects_undetectable_type(tmp_path: Path) -> None:
    """Callers only catch ValueError, so an unguessable type must raise that."""
    src_path = tmp_path / "encrypted"
    att = write_encrypted_attachment(src_path, bytes(64))
    dst_path = tmp_path / "decrypted"

    with pytest.raises(ValueError):
        files.decrypt_attachment(att, src_path, dst_path, detect_file_type=True)
