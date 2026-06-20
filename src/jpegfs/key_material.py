

from dataclasses import dataclass

from . import crypto

_SALT_SIZE = 16
_NONCE_SIZE = 12
_ENCRYPTED_KEY_SIZE = 48  # 32-byte master_key + 16-byte AEAD tag

SIZE = _SALT_SIZE + _NONCE_SIZE + _ENCRYPTED_KEY_SIZE  # 76


@dataclass(frozen=True)
class KeyMaterial:
    salt: bytes               # 16 bytes
    key_nonce: bytes          # 12 bytes
    encrypted_master_key: bytes  # 48 bytes

    @classmethod
    def create(cls, password: str, master_key: bytes) -> KeyMaterial:
        salt = crypto.random_bytes(_SALT_SIZE)
        key_nonce = crypto.random_bytes(_NONCE_SIZE)
        derived = crypto.derive_key(password, salt)
        encrypted = crypto.encrypt(derived, key_nonce, master_key)
        return cls(salt=salt, key_nonce=key_nonce, encrypted_master_key=encrypted)

    def to_bytes(self) -> bytes:
        return self.salt + self.key_nonce + self.encrypted_master_key

    @classmethod
    def from_bytes(cls, data: bytes) -> KeyMaterial:
        if len(data) < SIZE:
            raise ValueError(f"Key material too short: {len(data)} < {SIZE}.")
        return cls(
            salt=data[:_SALT_SIZE],
            key_nonce=data[_SALT_SIZE:_SALT_SIZE + _NONCE_SIZE],
            encrypted_master_key=data[_SALT_SIZE + _NONCE_SIZE:SIZE],
        )

    def decrypt_master_key(self, password: str) -> bytes:
        derived = crypto.derive_key(password, self.salt)
        return crypto.decrypt(derived, self.key_nonce, self.encrypted_master_key)
