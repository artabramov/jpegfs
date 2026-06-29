

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .errors import InvalidPasswordError

_SCRYPT_N = 2 ** 16
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 32
NONCE_SIZE = 12


def random_bytes(n: int) -> bytes:
    """
    Return cryptographically secure random bytes.

    Uses the operating system random source for salts, nonces,
    master keys, and other security-sensitive values.
    """
    return os.urandom(n)


def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive an encryption key from a password and salt.

    Uses scrypt with the project parameters and returns
    a fixed-length key suitable for ChaCha20-Poly1305.
    """
    kdf = Scrypt(salt=salt, length=_KEY_LENGTH, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt plaintext using ChaCha20-Poly1305.

    Uses the supplied key and nonce with no associated data
    and returns ciphertext including the authentication tag.
    """
    return ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)


def encrypt_prefixed(key: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt plaintext and prefix the generated nonce.

    Produces `nonce || ciphertext_with_tag` using the project
    nonce size, so callers can store one contiguous blob.
    """
    nonce = random_bytes(NONCE_SIZE)
    return nonce + encrypt(key, nonce, plaintext)


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """
    Decrypt ChaCha20-Poly1305 ciphertext.

    Returns plaintext when authentication succeeds and raises
    InvalidPasswordError for invalid keys, passwords, or corrupted data.
    """
    try:
        return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise InvalidPasswordError("Invalid password or corrupted data.")


def decrypt_prefixed(key: bytes, blob: bytes) -> bytes:
    """
    Decrypt data stored as `nonce || ciphertext_with_tag`.
    """
    nonce = blob[:NONCE_SIZE]
    ciphertext = blob[NONCE_SIZE:]
    return decrypt(key, nonce, ciphertext)
