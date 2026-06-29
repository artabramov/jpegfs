import unittest

from jpegfs import key_material
from jpegfs.errors import InvalidPasswordError


class TestKeyMaterial(unittest.TestCase):

    def test_create_roundtrip_through_bytes(self):
        master_key = b"\x11" * 32
        km = key_material.KeyMaterial.create("secret", master_key)
        raw = km.to_bytes()
        parsed = key_material.KeyMaterial.from_bytes(raw)

        self.assertEqual(len(raw), key_material.SIZE)
        self.assertEqual(parsed.salt, km.salt)
        self.assertEqual(parsed.key_nonce, km.key_nonce)
        self.assertEqual(parsed.encrypted_master_key, km.encrypted_master_key)

    def test_from_bytes_rejects_short_data(self):
        with self.assertRaisesRegex(ValueError, "Key material too short"):
            key_material.KeyMaterial.from_bytes(b"\x00" * 10)

    def test_decrypt_master_key_with_correct_password(self):
        master_key = b"\x22" * 32
        km = key_material.KeyMaterial.create("secret", master_key)
        self.assertEqual(km.decrypt_master_key("secret"), master_key)

    def test_decrypt_master_key_with_wrong_password(self):
        km = key_material.KeyMaterial.create("secret", b"\x33" * 32)
        with self.assertRaises(InvalidPasswordError):
            km.decrypt_master_key("wrong")


if __name__ == "__main__":
    unittest.main()
