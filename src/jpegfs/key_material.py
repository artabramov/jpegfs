from dataclasses import dataclass

from . import crypto

_SALT_SIZE = 16
_ENCRYPTED_KEY_SIZE = 48  # 32-byte master_key + 16-byte AEAD tag

SIZE = _SALT_SIZE + crypto.NONCE_SIZE + _ENCRYPTED_KEY_SIZE  # 76


@dataclass(frozen=True)
class KeyMaterial:
    salt: bytes                  # 16 bytes
    key_nonce: bytes             # 12 bytes
    encrypted_master_key: bytes  # 48 bytes

    @classmethod
    def create(cls, password: str, master_key: bytes) -> "KeyMaterial":
        """
        Create password-protected key material for a master key.

        Generates a fresh salt and nonce, derives a password key,
        and encrypts the container master key for storage in a carrier.
        """
        salt = crypto.random_bytes(_SALT_SIZE)
        key_nonce = crypto.random_bytes(crypto.NONCE_SIZE)
        derived = crypto.derive_key(password, salt)
        encrypted = crypto.encrypt(derived, key_nonce, master_key)
        return cls(salt=salt, key_nonce=key_nonce, encrypted_master_key=encrypted)

    def to_bytes(self) -> bytes:
        """
        Serialize key material to its binary carrier format.

        Concatenates salt, nonce, and encrypted master key into
        the fixed-size block stored at the start of each jpegfs tail.
        """
        return self.salt + self.key_nonce + self.encrypted_master_key

    @classmethod
    def from_bytes(cls, data: bytes) -> "KeyMaterial":
        """
        Parse key material from raw tail bytes.

        Validates that enough data is present and extracts the salt,
        nonce, and encrypted master-key block.
        """
        if len(data) < SIZE:
            raise ValueError(f"Key material too short: {len(data)} < {SIZE}.")
        return cls(
            salt=data[:_SALT_SIZE],
            key_nonce=data[_SALT_SIZE:_SALT_SIZE + crypto.NONCE_SIZE],
            encrypted_master_key=data[_SALT_SIZE + crypto.NONCE_SIZE:SIZE],
        )

    def decrypt_master_key(self, password: str) -> bytes:
        """
        Decrypt the stored container master key.

        Derives the password key from the saved salt and decrypts
        the encrypted master-key block using its stored nonce.
        """
        derived = crypto.derive_key(password, self.salt)
        return crypto.decrypt(derived, self.key_nonce, self.encrypted_master_key)
