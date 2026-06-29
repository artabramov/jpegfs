

import io
import struct
import zipfile
from dataclasses import dataclass

import zfec

from . import crypto
from .errors import (
    ContainerFileExistsError,
    ContainerFileNotFoundError,
    InsufficientShardsError,
)

_NONCE_SIZE = 12
_LEN_HEADER = 4  # big-endian uint32 prefix storing original ciphertext length
_NAME_MAX = 255


def validate_name(name: str) -> None:
    """
    Validate a flat container file name.

    Rejects empty names, path separators, dot entries, control
    characters, and UTF-8 names longer than the allowed limit.
    """
    if not name:
        raise ValueError("File name must not be empty.")
    if "/" in name or "\\" in name:
        raise ValueError(f"File name must not contain path separators: '{name}'.")
    if name in (".", ".."):
        raise ValueError(f"File name must not be '.' or '..'.")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in name):
        raise ValueError(f"File name must not contain control characters: '{name}'.")
    if len(name.encode()) > _NAME_MAX:
        raise ValueError(
            f"File name too long ({len(name.encode())} bytes, max {_NAME_MAX}): '{name}'."
        )


def create_empty_zip() -> bytes:
    """
    Create an empty ZIP payload for a new container.

    Returns valid ZIP bytes using stored entries without compression,
    ready to be encrypted and split into shards.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED):
        pass
    return buf.getvalue()


@dataclass
class FileInfo:
    name: str
    size: int       # uncompressed bytes
    modified: tuple # (year, month, day, hour, minute, second)


def _copy_entries(
    zin: zipfile.ZipFile,
    zout: zipfile.ZipFile,
    *,
    exclude_name: str | None = None,
) -> None:
    """
    Copy ZIP entries from one archive into another.

    Preserves each original entry metadata while optionally skipping
    one entry by name.
    """
    for info in zin.infolist():
        if info.filename == exclude_name:
            continue
        zout.writestr(info, zin.read(info.filename))


def _rewrite_zip(
    zip_data: bytes,
    *,
    exclude_name: str | None = None,
    must_exist_name: str | None = None,
    must_not_exist_name: str | None = None,
    add_entry: tuple[str, bytes] | None = None,
) -> bytes:
    """
    Rewrite a ZIP payload through a read-and-write archive pair.

    Opens source and destination ZIP archives, validates optional
    preconditions, copies existing entries, and applies optional
    delete/add operations.
    """
    new_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zin:
        names = set(zin.namelist())
        if must_exist_name is not None and must_exist_name not in names:
            raise ContainerFileNotFoundError(
                f"'{must_exist_name}' not found in the container."
            )
        if must_not_exist_name is not None and must_not_exist_name in names:
            raise ContainerFileExistsError(
                f"'{must_not_exist_name}' already exists in the container. Delete it first."
            )

        with zipfile.ZipFile(new_buf, "w", compression=zipfile.ZIP_STORED) as zout:
            _copy_entries(zin, zout, exclude_name=exclude_name)
            if add_entry is not None:
                add_name, add_content = add_entry
                zout.writestr(add_name, add_content)
    return new_buf.getvalue()


def zip_list_files(zip_data: bytes) -> list[str]:
    """
    Return file names stored in a ZIP payload.

    Reads the decrypted payload as a ZIP archive and returns
    the archive entry names in ZIP order.
    """
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        return zf.namelist()


def zip_list_files_info(zip_data: bytes) -> list[FileInfo]:
    """
    Return metadata for files stored in a ZIP payload.

    Reads ZIP entry information and returns file name, size,
    and modification timestamp for each stored file.
    """
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        return [
            FileInfo(name=info.filename, size=info.file_size, modified=info.date_time)
            for info in zf.infolist()
        ]


def zip_get_file(zip_data: bytes, name: str) -> bytes:
    """
    Read one file from a ZIP payload.

    Validates the requested name, checks that the entry exists,
    and returns its stored bytes.
    """
    validate_name(name)
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        try:
            return zf.read(name)
        except KeyError:
            raise ContainerFileNotFoundError(f"'{name}' not found in the container.")


def zip_delete_file(zip_data: bytes, name: str) -> bytes:
    """
    Remove one file from a ZIP payload.

    Copies all entries except the requested one into a new
    stored-mode ZIP archive and returns the resulting bytes.
    """
    validate_name(name)
    return _rewrite_zip(
        zip_data,
        exclude_name=name,
        must_exist_name=name,
    )


def zip_add_file(zip_data: bytes, name: str, content: bytes) -> bytes:
    """
    Add a new file to a ZIP payload.

    Validates the name, rejects duplicates, copies existing entries,
    and writes the new file into a fresh stored-mode ZIP archive.
    """
    validate_name(name)
    return _rewrite_zip(
        zip_data,
        must_not_exist_name=name,
        add_entry=(name, content),
    )


def encode(zip_data: bytes, master_key: bytes, k: int, n: int) -> list[bytes]:
    """
    Encrypt ZIP payload bytes and split them into shards.

    Frames the ciphertext length, pads it for erasure coding,
    and returns the full set of encoded shard bytes.
    """
    nonce = crypto.random_bytes(_NONCE_SIZE)
    ciphertext = nonce + crypto.encrypt(master_key, nonce, zip_data)

    # Prepend original length so decode can strip padding after reassembly.
    framed = struct.pack(">I", len(ciphertext)) + ciphertext

    remainder = len(framed) % k
    if remainder:
        framed += b"\x00" * (k - remainder)

    encoder = zfec.Encoder(k, n)
    piece_size = len(framed) // k
    pieces = [framed[i * piece_size:(i + 1) * piece_size] for i in range(k)]
    return encoder.encode(pieces)


def decode(shards: list[bytes | None], indices: list[int], master_key: bytes, k: int, n: int) -> bytes:
    """
    Reconstruct and decrypt ZIP payload bytes from shards.

    Uses at least the threshold number of shards, removes framing
    and padding, then decrypts the recovered ciphertext.
    """
    available = [(s, i) for s, i in zip(shards, indices) if s is not None]
    if len(available) < k:
        raise InsufficientShardsError(f"Need {k} shards, got {len(available)}.")

    sel_shards, sel_indices = zip(*available[:k])
    decoder = zfec.Decoder(k, n)
    pieces = decoder.decode(list(sel_shards), list(sel_indices))
    framed = b"".join(pieces)

    original_len = struct.unpack(">I", framed[:_LEN_HEADER])[0]
    ciphertext = framed[_LEN_HEADER:_LEN_HEADER + original_len]

    nonce = ciphertext[:_NONCE_SIZE]
    encrypted = ciphertext[_NONCE_SIZE:]
    return crypto.decrypt(master_key, nonce, encrypted)
