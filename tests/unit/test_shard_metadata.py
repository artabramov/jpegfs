import unittest

from jpegfs import shard_metadata
from jpegfs.errors import InvalidPasswordError


class TestShardMetadata(unittest.TestCase):

    def setUp(self):
        self.master_key = b"\x44" * 32
        self.meta = shard_metadata.ShardMetadata(
            container_uuid=b"\x55" * 16,
            container_generation=7,
            container_threshold=2,
            shard_index=1,
            shard_total=3,
        )

    def test_encrypt_roundtrip(self):
        encrypted = self.meta.encrypt(self.master_key)
        self.assertEqual(len(encrypted), shard_metadata.SIZE)

        parsed = shard_metadata.ShardMetadata.from_encrypted(
            encrypted, self.master_key
        )

        self.assertEqual(parsed.container_uuid, self.meta.container_uuid)
        self.assertEqual(parsed.container_generation, self.meta.container_generation)
        self.assertEqual(parsed.container_threshold, self.meta.container_threshold)
        self.assertEqual(parsed.shard_index, self.meta.shard_index)
        self.assertEqual(parsed.shard_total, self.meta.shard_total)

    def test_from_encrypted_rejects_short_data(self):
        with self.assertRaisesRegex(ValueError, "Shard metadata too short"):
            shard_metadata.ShardMetadata.from_encrypted(b"\x00" * 10, self.master_key)

    def test_from_encrypted_with_wrong_master_key(self):
        encrypted = self.meta.encrypt(self.master_key)
        with self.assertRaises(InvalidPasswordError):
            shard_metadata.ShardMetadata.from_encrypted(encrypted, b"\x66" * 32)


if __name__ == "__main__":
    unittest.main()
