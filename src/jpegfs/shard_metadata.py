

import struct
from dataclasses import dataclass

from . import crypto

_NONCE_SIZE = 12
_PLAINTEXT_SIZE = 26
_ENCRYPTED_SIZE = _PLAINTEXT_SIZE + 16  # + AEAD tag = 42

SIZE = _NONCE_SIZE + _ENCRYPTED_SIZE  # 54

_STRUCT = ">16sIHHH"


@dataclass(frozen=True)
class ShardMetadata:
    container_uuid: bytes      # 16 bytes
    container_generation: int  # uint32
    container_threshold: int   # uint16
    shard_index: int           # uint16
    shard_total: int           # uint16

    def encrypt(self, master_key: bytes) -> bytes:
        nonce = crypto.random_bytes(_NONCE_SIZE)
        plaintext = struct.pack(
            _STRUCT,
            self.container_uuid,
            self.container_generation,
            self.container_threshold,
            self.shard_index,
            self.shard_total,
        )
        return nonce + crypto.encrypt(master_key, nonce, plaintext)

    @classmethod
    def from_encrypted(cls, data: bytes, master_key: bytes) -> ShardMetadata:
        if len(data) < SIZE:
            raise ValueError(f"Shard metadata too short: {len(data)} < {SIZE}.")
        nonce = data[:_NONCE_SIZE]
        encrypted = data[_NONCE_SIZE:SIZE]
        plaintext = crypto.decrypt(master_key, nonce, encrypted)
        uuid_, generation, threshold, shard_index, shard_total = struct.unpack(
            _STRUCT, plaintext
        )
        return cls(
            container_uuid=uuid_,
            container_generation=generation,
            container_threshold=threshold,
            shard_index=shard_index,
            shard_total=shard_total,
        )
