import base64
import hashlib
import hmac
import shutil
from datetime import datetime
from pathlib import Path

from Crypto.Cipher import AES
from typer import colors, secho

from sigexport import models
from sigexport.signal_logging import log

CIPHER_KEY_SIZE = 32
IV_SIZE = AES.block_size
MAC_KEY_SIZE = 32
MAC_SIZE = hashlib.sha256().digest_size


def decrypt_attachment(att: dict[str, str], src_path: Path, dst_path: Path) -> None:
    """Decrypt attachment and save to `dst_path`.

    Code adapted from:
        https://github.com/tbvdm/sigtop
    """
    try:
        keys = base64.b64decode(att["localKey"])
    except KeyError:
        raise ValueError("No key in attachment")
    except Exception as e:
        raise ValueError(f"Cannot decode keys: {str(e)}")

    if len(keys) != CIPHER_KEY_SIZE + MAC_KEY_SIZE:
        raise ValueError("Invalid keys length")

    cipher_key = keys[:CIPHER_KEY_SIZE]
    mac_key = keys[CIPHER_KEY_SIZE:]

    try:
        with open(src_path, "rb") as fp:
            data = fp.read()
    except Exception as e:
        raise ValueError(f"Failed to read file: {str(e)}")

    if len(data) < IV_SIZE + MAC_SIZE:
        raise ValueError("Attachment data too short")

    iv = data[:IV_SIZE]
    their_mac = data[-MAC_SIZE:]
    data = data[IV_SIZE:-MAC_SIZE]

    if len(data) % AES.block_size != 0:
        raise ValueError("Invalid attachment data length")

    m = hmac.new(mac_key, iv + data, hashlib.sha256)
    our_mac = m.digest()

    if not hmac.compare_digest(our_mac, their_mac):
        raise ValueError("MAC mismatch")

    try:
        cipher = AES.new(cipher_key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(data)
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

    if len(decrypted_data) < int(att["size"]):
        raise ValueError("Invalid attachment data length")

    data_decrypted = decrypted_data[: att["size"]]
    with open(dst_path, "wb") as fp:
        fp.write(data_decrypted)


def copy_attachments(
    src: Path, dest: Path, convos: models.Convos, contacts: models.Contacts
) -> None:
    """Copy attachments and reorganise in destination directory."""
    src_root = Path(src) / "attachments.noindex"
    dest = Path(dest)

    for key, messages in convos.items():
        name = contacts[key].name
        log(f"\tCopying attachments for: {name}")
        # some contact names are None
        if not name:
            name = "None"
        dst_root = dest / name / "media"
        dst_root.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            if msg.attachments:
                attachments = msg.attachments
                date = (
                    datetime.fromtimestamp(msg.get_ts() / 1000)
                    .isoformat(timespec="milliseconds")
                    .replace(":", "-")
                )
                for i, att in enumerate(attachments):
                    # Account for no fileName key
                    file_name = str(att["fileName"]) if "fileName" in att else "None"
                    # Sometimes the key is there but it is None, needs extension
                    if "." not in file_name:
                        content_type = att.get("contentType", "").split("/")
                        if len(content_type) > 1:
                            ext = content_type[1]
                        else:
                            ext = content_type[0]
                        file_name += "." + ext
                    att["fileName"] = (
                        f"{date}_{i:02}_{file_name}".replace(" ", "_")
                        .replace("/", "-")
                        .replace(",", "")
                        .replace(":", "-")
                        .replace("|", "-")
                    )
                    # account for erroneous backslash in path
                    try:
                        att_path = str(att["path"]).replace("\\", "/")
                    except KeyError:
                        log(f"\t\tBroken attachment:\t{name}")
                        continue
                    src_path = src_root / att_path
                    dst_path = dst_root / att["fileName"]
                    if int(att.get("version", 0)) >= 2:
                        try:
                            decrypt_attachment(att, src_path, dst_path)
                        except ValueError as e:
                            secho(
                                f"Failed to decrypt {src_path} error {e}, skipping",
                                fg=colors.MAGENTA,
                            )
                    else:
                        try:
                            shutil.copy2(src_path, dst_path)
                        except FileNotFoundError:
                            secho(
                                f"No file to copy at {src_path}, skipping!",
                                fg=colors.MAGENTA,
                            )
                        except OSError as exc:
                            secho(
                                f"Error copying file {src_path}, skipping!\n{exc}",
                                fg=colors.MAGENTA,
                            )
            else:
                msg.attachments = []


def merge_attachments(media_new: Path, media_old: Path) -> None:
    """Merge new and old attachments directories."""
    for f in media_old.iterdir():
        if f.is_file():
            try:
                shutil.copy2(f, media_new)
            except shutil.SameFileError:
                log(
                    f"Skipped file {f} as duplicate found in new export directory!",
                    fg=colors.RED,
                )
