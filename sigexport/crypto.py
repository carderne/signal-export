# Modified from:
# https://gist.github.com/flatz/3f242ab3c550d361f8c6d031b07fb6b1

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    from base64 import b64decode
    from ctypes import *
    from ctypes.wintypes import DWORD

    class DataBlob(Structure):
        _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]


from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad
from typer import colors, secho

PASSWORD_CMD_DARWIN = [
    "security",
    "find-generic-password",
    "-ws",
    "Signal Safe Storage",
]
PASSWORD_CMD_GNOME = ["secret-tool", "lookup", "application", "Signal"]
PASSWORD_CMD_KDE = [
    "kwallet-query",
    "kdewallet",
    "-f",
    "Chromium Keys",
    "-r",
    "Chromium Safe Storage",
]


def get_key(appdir: Path, password: Optional[str]) -> Optional[str]:
    """Get key for decrypting database.

    Retrieves key depending on key encryption software.

    If it cannot be decrypted, print an explanation message.

    Args:
        file: Signal config json file path
        password: password that user could have supplied to decrypt key
    Returns:
        (decrypted) password or None
    """

    with open(appdir / "config.json", encoding="utf-8") as cf:
        data = json.loads(cf.read())
    if "key" in data:
        return data["key"]
    elif "encryptedKey" in data:
        encrypted_key = data["encryptedKey"]
        if sys.platform == "win32":
            if not password:
                with open(appdir / "Local State", encoding="utf-8") as lsf:
                    data = json.loads(lsf.read())
                if "os_crypt" in data and "encrypted_key" in data["os_crypt"]:
                    pw_encrypted_b64 = data["os_crypt"]["encrypted_key"]
                else:
                    secho("Encrypted password not found in Local State", fg=colors.RED)
                    raise

                # base64decode the encrypted password, and cut off the first 5 bytes ('D' 'P' 'A' 'P' 'I')
                pw_encrypted = b64decode(pw_encrypted_b64)[5:]

                # decrypt the password
                data_in = DataBlob(
                    len(pw_encrypted), c_buffer(pw_encrypted, len(pw_encrypted))
                )
                data_out = DataBlob()
                if windll.crypt32.CryptUnprotectData(
                    byref(data_in), None, None, None, None, 0, byref(data_out)
                ):
                    cbData = int(data_out.cbData)
                    pbData = data_out.pbData
                    buffer = c_buffer(cbData)
                    cdll.msvcrt.memcpy(buffer, pbData, cbData)
                    windll.kernel32.LocalFree(pbData)
                    pw = buffer.raw
                else:
                    secho("Failed to decrypt password", fg=colors.RED)
                    raise
            else:
                pw = bytearray.fromhex(password)

            # The encrypted key consists of the following parts:
            # 3 bytes header ('V' '1' '0')
            # 12 bytes nonce
            # 64 bytes encrypted data
            # 16 bytes MAC
            encryptedKey_struct = memoryview(bytearray.fromhex(encrypted_key))
            key = AES.new(
                pw, AES.MODE_GCM, nonce=encryptedKey_struct[3:15]
            ).decrypt_and_verify(encryptedKey_struct[15:79], encryptedKey_struct[79:])
            return key.decode("ascii")
        if sys.platform == "darwin":
            if password:
                return decrypt(password, encrypted_key, b"v10", 1003)
            pw = get_password(PASSWORD_CMD_DARWIN, "macOS")  # may raise error
            return decrypt(pw, encrypted_key, b"v10", 1003)
        else:  # linux
            if password:
                return decrypt(password, encrypted_key, b"v11", 1)
            elif "safeStorageBackend" in data:
                if data["safeStorageBackend"] == "gnome_libsecret":
                    pw = get_password(PASSWORD_CMD_GNOME, "gnome")  # may raise error
                    return decrypt(pw, encrypted_key, b"v11", 1)
                elif data["safeStorageBackend"] in [
                    "gnome_libsecret",
                    "kwallet",
                    "kwallet5",
                    "kwallet6",
                ]:
                    pw = get_password(PASSWORD_CMD_KDE, "KDE")  # may raise error
                    return decrypt(pw, encrypted_key, b"v11", 1)
                else:
                    secho("Your Signal data key is encrypted, and requires a password.")
                    secho(f"The safe storage backend is {data['safeStorageBackend']}")
                    secho(
                        "If you know some Python and know how to retrieve passwords "
                        "from this backend, please contribute a PR!"
                    )
            else:
                secho("Your Signal data key is encrypted, and requires a password.")
                secho("No safe storage backend is specified.")
                secho(
                    "On gnome, you can usually retrieve the password with the command"
                )
                secho(" ".join(PASSWORD_CMD_GNOME) + "\n", fg=colors.BLUE)
                secho("On KDE, you can usually retreive the password with the command")
                secho(" ".join(PASSWORD_CMD_KDE) + "\n", fg=colors.BLUE)
                secho(
                    "If you have found your password, please rerun sigexport as follows:"
                )
                secho("sigexport --password=PASSWORD_FROM_COMMAND ...", fg=colors.BLUE)
                secho("No Signal decryption key found", fg=colors.RED)
    else:
        secho("No Signal decryption key found", fg=colors.RED)


def get_password(cmd: list[str], system: str) -> str:
    """Call external tool to get key password.

    Args:
        cmd: shell command as list of words
        system: Name of the system we are on, for help message.
    Returns:
        password if found
    Raises:
        nondescript error: if no password was found
    """
    try:
        p = subprocess.run(  # NoQA: S603
            cmd, capture_output=True, text=True, encoding="utf-8"
        )
    except FileNotFoundError as e:
        secho(
            f"When trying to retrieve the password, '{e.filename}' was not found. "
            "You may need to install the respective package."
        )
        raise
    if p.returncode != 0:
        secho("Your Signal data key is encrypted, and requires a password.")
        secho(f"Usually on {system}, you can try to get it with this command:")
        secho(" ".join(cmd) + "\n", fg=colors.BLUE)
        secho(
            "But this failed with errorcode "
            f"{p.returncode} and error {p.stdout} {p.stderr}"
        )
        secho("If you have found your password, please rerun sigexport as follows:")
        secho("sigexport --password=PASSWORD_FROM_COMMAND ...", fg=colors.BLUE)
        secho("No Signal decryption key found", fg=colors.RED)
        raise
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
