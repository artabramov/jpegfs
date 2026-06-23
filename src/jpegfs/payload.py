

import io
import struct
import zipfile

import zfec

from . import crypto

_NONCE_SIZE = 12
_LEN_HEADER = 4  # big-endian uint32 prefix storing original ciphertext length
_NAME_MAX = 255


def validate_name(name: str) -> None:
    """
    Enforce flat-filesystem naming rules.  Raises ValueError on violations.
    Rules:
      - Non-empty
      - No path separators (/ or \\)
      - Not a dot-entry (. or ..)
      - No ASCII control characters (0x00-0x1F, 0x7F)
      - At most _NAME_MAX bytes when encoded as UTF-8
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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED):
        pass
    return buf.getvalue()


from dataclasses import dataclass


@dataclass
class FileInfo:
    name: str
    size: int       # uncompressed bytes
    modified: tuple # (year, month, day, hour, minute, second)


def zip_list_files(zip_data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        return zf.namelist()


def zip_list_files_info(zip_data: bytes) -> list[FileInfo]:
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        return [
            FileInfo(name=info.filename, size=info.file_size, modified=info.date_time)
            for info in zf.infolist()
        ]


def zip_get_file(zip_data: bytes, name: str) -> bytes:
    from .errors import ContainerFileNotFoundError
    validate_name(name)
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        if name not in zf.namelist():
            raise ContainerFileNotFoundError(f"'{name}' not found in the container.")
        return zf.read(name)


def zip_delete_file(zip_data: bytes, name: str) -> bytes:
    from .errors import ContainerFileNotFoundError
    validate_name(name)
    if name not in zip_list_files(zip_data):
        raise ContainerFileNotFoundError(f"'{name}' not found in the container.")
    new_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zin:
        with zipfile.ZipFile(new_buf, "w", compression=zipfile.ZIP_STORED) as zout:
            for info in zin.infolist():
                if info.filename != name:
                    zout.writestr(info, zin.read(info.filename))
    return new_buf.getvalue()


def zip_add_file(zip_data: bytes, name: str, content: bytes) -> bytes:
    from .errors import ContainerFileExistsError
    validate_name(name)
    if name in zip_list_files(zip_data):
        raise ContainerFileExistsError(
            f"'{name}' already exists in the container. Delete it first."
        )
    new_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zin:
        with zipfile.ZipFile(new_buf, "w", compression=zipfile.ZIP_STORED) as zout:
            for info in zin.infolist():
                zout.writestr(info, zin.read(info.filename))
            zout.writestr(name, content)
    return new_buf.getvalue()


def encode(zip_data: bytes, master_key: bytes, k: int, n: int) -> list[bytes]:
    """ZIP bytes -> list of n shards."""
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
    """At least k shards + their indices -> original ZIP bytes."""
    from .errors import InsufficientShardsError

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
