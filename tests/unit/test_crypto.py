import unittest

from jpegfs import crypto
from jpegfs.errors import InvalidPasswordError


class TestCrypto(unittest.TestCase):

    def test_random_bytes_returns_requested_length(self):
        self.assertEqual(len(crypto.random_bytes(32)), 32)

    def test_derive_key_is_deterministic_for_same_inputs(self):
        salt = b"\x00" * 16
        self.assertEqual(
            crypto.derive_key("secret", salt),
            crypto.derive_key("secret", salt),
        )

    def test_derive_key_differs_for_different_salts(self):
        first = crypto.derive_key("secret", b"\x00" * 16)
        second = crypto.derive_key("secret", b"\x01" * 16)
        self.assertNotEqual(first, second)

    def test_encrypt_decrypt_roundtrip(self):
        key = crypto.random_bytes(32)
        nonce = crypto.random_bytes(12)
        plaintext = b"hello, jpegfs"

        ciphertext = crypto.encrypt(key, nonce, plaintext)
        self.assertEqual(crypto.decrypt(key, nonce, ciphertext), plaintext)

    def test_decrypt_with_wrong_key_raises_invalid_password(self):
        key = crypto.random_bytes(32)
        nonce = crypto.random_bytes(12)
        ciphertext = crypto.encrypt(key, nonce, b"secret")

        with self.assertRaises(InvalidPasswordError):
            crypto.decrypt(crypto.random_bytes(32), nonce, ciphertext)


if __name__ == "__main__":
    unittest.main()
