

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .errors import InvalidPasswordError

_SCRYPT_N = 2 ** 16
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 32


def random_bytes(n: int) -> bytes:
    return os.urandom(n)


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=_KEY_LENGTH, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    return ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    try:
        return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise InvalidPasswordError("Invalid password or corrupted data.")
