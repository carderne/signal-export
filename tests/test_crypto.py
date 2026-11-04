import json
import sys
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad

from sigexport import crypto

DB_KEY = "00112233445566778899aabbccddeeff" * 2


def encrypt_key(password: str, prefix: bytes, iterations: int) -> str:
    """config.json's encryptedKey, as Electron's safeStorage writes it."""
    key = PBKDF2(password, salt=b"saltysalt", dkLen=16, count=iterations, hmac_hash_module=SHA1)
    ciphertext = AES.new(key, AES.MODE_CBC, b" " * 16).encrypt(pad(DB_KEY.encode(), 16))
    return (prefix + ciphertext).hex()


def write_config(tmp_path: Path, **config: str) -> Path:
    (tmp_path / "config.json").write_text(json.dumps(config))
    return tmp_path


def test_decrypt_known_answer_macos() -> None:
    encrypted = encrypt_key("hunter2", b"v10", 1003)
    assert crypto.decrypt("hunter2", encrypted, b"v10", 1003) == DB_KEY


def test_decrypt_rejects_an_unexpected_prefix() -> None:
    encrypted = encrypt_key("hunter2", b"v11", 1)
    with pytest.raises(ValueError, match="expected b'v10'"):
        crypto.decrypt("hunter2", encrypted, b"v10", 1)


def test_linux_without_a_keyring_uses_the_basic_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    appdir = write_config(
        tmp_path,
        encryptedKey=encrypt_key("peanuts", b"v10", 1),
        safeStorageBackend="basic_text",
    )
    assert crypto.get_key(appdir, None) == DB_KEY


def test_a_failed_password_lookup_says_what_failed() -> None:
    with pytest.raises(RuntimeError, match="exited with status 1"):
        crypto.get_password(["false"], "test")
