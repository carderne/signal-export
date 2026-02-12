import base64
import filetype
import hashlib
import hmac
import json
import os
import shutil
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256
from sqlcipher3 import dbapi2
from typer import colors, secho

from sigexport import models
from sigexport.logging import log

CIPHER_KEY_SIZE = 32
IV_SIZE = AES.block_size
MAC_KEY_SIZE = 32
MAC_SIZE = hashlib.sha256().digest_size


def derive_key(pack_key):
    hkdf = HKDF(
        base64.b64decode(pack_key),
        512,
        None,
        SHA256,
        1,
        b"Sticker Pack"
    )

    aes_key = hkdf[0:32]
    hmac_key = hkdf[32:64]

    return aes_key, hmac_key

def decrypt_remote_sticker(pack_key: str, data: bytearray, dst_path: Path):
    cipher, mac = derive_key(pack_key)
    decrypt(cipher, mac, data, dst_path, None, True, False)

def decrypt_attachment(att: dict[str, str], src_path: Path, dst_path: Path, detect_file_type: bool = False, validate_size: bool = True) -> None:
    try:
        with open(src_path, "rb") as fp:
            data = fp.read()
    except Exception as e:
        raise ValueError(f"Failed to read file: {str(e)}")

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

    decrypt(cipher_key, mac_key, data, dst_path, int(att["size"]), detect_file_type, validate_size)

def decrypt(cipher_key, mac_key, data: bytearray, dst_path: Path, size: int = None, detect_file_type: bool = False, validate_size: bool = True) -> None:
    """Decrypt attachment and save to `dst_path`.

    Code adapted from:
        https://github.com/tbvdm/sigtop
    """

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

    if validate_size:
        if len(decrypted_data) < size:
            raise ValueError("Invalid attachment data length")

        decrypted_data = decrypted_data[: size]

    if detect_file_type:
        dst_path = str(dst_path)
        try:
            ext = filetype.guess_extension(decrypted_data)
        except TypeError:
            raise ValueError("Unsupported attachment file type")

        dst_path += "." + ext

    with open(dst_path, "wb") as fp:
        fp.write(decrypted_data)


def get_attachments_from_db(
    cursor: dbapi2.Cursor, message_id: str, edit_history_index: int = -1
) -> list[dict]:
    """Retrieve attachments from the message_attachments table
    for DB version >= 1360
    """
    query = """
    SELECT
        size,
        contentType,
        path,
        fileName,
        localKey,
        version,
        pending
    FROM message_attachments
    WHERE
        messageId = ?
        AND editHistoryIndex = ?
        AND attachmentType = 'attachment'
    ORDER BY orderInMessage
    """

    cursor.execute(query, (message_id, edit_history_index))
    attachments = []

    for row in cursor:
        att = {
            "size": row[0],
            "contentType": row[1],
            "path": row[2],
            "fileName": row[3],
            "localKey": row[4],
            "version": row[5] or 0,
            "pending": row[6],
        }
        attachments.append(att)

    return attachments


def copy_stickers(
    cursor: dbapi2.Cursor,
    src: Path,
    dest: Path,
) -> None:
    src_root = Path(src) / "stickers.noindex"
    dst_root = Path(dest) / "exported_stickers"
    dst_root.mkdir(exist_ok=True, parents=True)

    query = """
    SELECT * FROM sticker_packs;
    """

    cursor.execute(query)
    sticker_packs = {}

    for row in cursor:
        sticker_packs[row[0]] = {
            "id": row[0],
            "key": row[1],
            "author": row[2],
            "coverStickerId": row[3],
            "createdAt": row[4],
            "downloadAttempts": row[5],
            "installedAt": row[6],
            "lastUsed": row[7],
            "status": row[8],
            "stickerCount": row[9],
            "title": row[10],
            "attemptedStatus": row[11],
            "position": row[12],
            "storageID": row[13],
            "storageVersion": row[14],
            "storageUnknownFields": row[15],
            "storageNeedsSync": row[16],
            "stickers": [],
        }

    for pack_id in sticker_packs:
        query = """
        SELECT
            *
        FROM stickers
        WHERE
            packId=?
        ORDER BY id
        """

        cursor.execute(query, (pack_id,))

        pck_path = dst_root / pack_id
        pck_path.mkdir(exist_ok=True, parents=True)

        for row in cursor:
            sticker = {
                "id": row[0],
                "packId": row[1],
                "emoji": row[2],
                "height": row[3],
                "isCoverOnly": row[4],
                "lastUsed": row[5],
                "path": row[6],
                "width": row[7],
                "version": row[8],
                "localKey": row[9],
                "size": row[10],
            }

            try:
                sticker_path = str(sticker["path"]).replace("\\", "/")
            except KeyError:
                log(f"\t\tBroken sticker:\t{sticker}")
                continue

            src_path = src_root / sticker_path
            dst_path = pck_path / str(sticker["id"])
            decrypt_attachment(sticker, src_path, dst_path, True, True)

            sticker_packs[pack_id]["stickers"].append(sticker)
        js_path = pck_path / "data.json"
        js_f = js_path.open("a", encoding="utf-8")
        js_str = json.dumps(sticker_packs[pack_id])
        if js_f:
            print(js_str, file=js_f)

def copy_attachments(
    src: Path,
    dest: Path,
    export_stickers: bool,
    convos: models.Convos,
    contacts: models.Contacts,
    cursor: dbapi2.Cursor,
) -> None:
    """Copy attachments and reorganise in destination directory."""
    src_root = Path(src) / "attachments.noindex"
    dest = Path(dest)
    
    cursor.execute("PRAGMA user_version")
    for row in cursor:
        db_version = row[0]

    for key, messages in convos.items():
        name = contacts[key].name
        log(f"\tCopying attachments for: {name}")
        # some contact names are None
        if not name:
            name = "None"
        dst_root = dest / name / "media"
        dst_root.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            if cursor.connection and db_version and db_version >= 1360:
                # Get attachments from database table
                attachments = get_attachments_from_db(cursor, msg.id)
                msg.attachments = attachments
            elif not hasattr(msg, "attachments") or msg.attachments is None:
                msg.attachments = []

            if export_stickers and msg.sticker:
                m_sticker = models.Sticker(
                    str(msg.sticker["stickerId"]),
                    msg.sticker["packId"],
                    msg.sticker["packKey"],
                    msg.sticker["emoji"],
                )
                if m_sticker.get_path(dest):
                    msg.sticker["extension"] = m_sticker.extension
                else:
                    # try to download missing stickers
                    downloaded = download_sticker(m_sticker.id, m_sticker.packId, m_sticker.packKey, dest)

                    if downloaded and (sticker_path := m_sticker.get_path(dest)):
                        msg.sticker["extension"] = m_sticker.extension
                        log(f"\t\tDownloaded missing sticker: {sticker_path}", fg=colors.GREEN)
                    else:
                        secho(
                            f"Not found: sticker {m_sticker.id} from pack '{m_sticker.packId}' used in conversation '{name}' at {date} {time}, skipping",
                            fg=colors.MAGENTA,
                        )

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
                    # Limit file_name to 200 characters to account for 255-character file name limit on most platforms
                    overlength = len(file_name) > 200
                    if overlength:
                        file_name = file_name[:200]

                    # Sometimes the key is there but it is None, needs extension
                    if "." not in file_name or overlength:
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
                        .replace("*", "_")
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

def download_sticker(sticker_id: str, pack_id: str, pack_key: str, dest: Path) -> None:
    sticker_url = f"https://cdn.signal.org/stickers/{pack_id}/full/{sticker_id}"

    # NOTE: monitor 'cdn.signal.org' for cert updates - their certs usually last 13 months
    context = ssl.create_default_context(cafile='sigexport/cdn-signal-org-chain.pem');

    sticker_request = urllib.request.urlopen(sticker_url, context=context)
    status_response = int(sticker_request.status)

    if status_response == 403: # CDN returns 403 instead of 404
        secho(f"Sticker '{sticker_id}' from pack '{pack_id}' no longer exists on Signal CDN", fg=colors.RED)
        return False
    if status_response not in range(200, 300):
        secho(f"Failed downloading sticker '{sticker_id}' from pack '{pack_id}': {sticker_request.status} {sticker_request.reason}", fg=colors.RED)
        return False

    sticker_encrypted = sticker_request.read()

    sticker_dest = Path(dest) / "exported_stickers" / pack_id
    sticker_dest.mkdir(exist_ok=True, parents=True)
    sticker_dest = Path(sticker_dest) / sticker_id

    try:
        decrypt_remote_sticker(pack_key, sticker_encrypted, sticker_dest)
    except ValueError as e:
        secho(f"Failed downloading sticker '{sticker_id}' from pack '{pack_id}': {e}", fg=colors.RED)
        return False

    return True

