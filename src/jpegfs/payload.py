

import io
import struct
import zipfile

import zfec

from . import crypto

_NONCE_SIZE = 12
_LEN_HEADER = 4  # big-endian uint32 prefix storing original ciphertext length


def create_empty_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED):
        pass
    return buf.getvalue()


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
    return encoder.encode(framed)


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
