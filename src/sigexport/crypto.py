# Modified from:
# https://gist.github.com/flatz/3f242ab3c550d361f8c6d031b07fb6b1

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad
from typer import colors, secho


def get_key(file: Path, password: Optional[str]) -> str:
    with open(file, encoding="utf-8") as f:
        data = json.loads(f.read())
    if "key" in data:
        return data["key"]
    elif "encryptedKey" in data:
        encrypyed_key = data["encryptedKey"]
        if sys.platform == "win32":
            secho(
                "Signal decryption isn't currently supported on Windows"
                "If you know some Python and crypto, please contribute a PR!",
                fg=colors.RED,
            )
        if sys.platform == "darwin":
            pw = get_password()
            return decrypt(pw, encrypyed_key, b"v10", 1003)
        else:
            if password:
                return decrypt(password, encrypyed_key, b"v11", 1)
            else:
                secho("Your Signal data key is encrypted, and requires a password.")
                secho("On Gnome, you can try to get this with this command:")
                secho("secret-tool lookup application Signal\n", fg=colors.BLUE)
                secho("Then please rerun sigexport as follows:")
                secho("sigexport --password=PASSWORD_FROM_COMMAND ...", fg=colors.BLUE)
    else:
        secho("No Signal decryption key found", fg=colors.RED)
    raise


def get_password() -> str:
    cmd = ["security", "find-generic-password", "-ws", "Signal Safe Storage"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")  # NoQA: S603
    pw = p.stdout
    return pw.strip()


def decrypt(password: str, encrypted_key: str, prefix: bytes, iterations: int) -> str:
    encrypted_key_b = bytes.fromhex(encrypted_key)
    if not encrypted_key_b.startswith(prefix):
        raise
    encrypted_key_b = encrypted_key_b[len(prefix) :]

    salt = b"saltysalt"
    key = PBKDF2(
        password, salt=salt, dkLen=128 // 8, count=iterations, hmac_hash_module=SHA1
    )
    iv = b" " * 16
    aes_decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted_key_b)
    decrypted_key = unpad(aes_decrypted, block_size=16).decode("ascii")
    return decrypted_key
