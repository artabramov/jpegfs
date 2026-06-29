import io
import unittest
import zipfile

from jpegfs import crypto, payload
from jpegfs.errors import (
    ContainerFileExistsError,
    ContainerFileNotFoundError,
    InsufficientShardsError,
)


class TestValidateName(unittest.TestCase):

    def test_accepts_valid_name(self):
        payload.validate_name("hello.txt")

    def test_rejects_empty_name(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            payload.validate_name("")

    def test_rejects_path_separators(self):
        with self.assertRaisesRegex(ValueError, "path separators"):
            payload.validate_name("../x")
        with self.assertRaisesRegex(ValueError, "path separators"):
            payload.validate_name("dir\\file")

    def test_rejects_dot_entries(self):
        with self.assertRaisesRegex(ValueError, "must not be '.' or '..'"):
            payload.validate_name(".")

    def test_rejects_control_characters(self):
        with self.assertRaisesRegex(ValueError, "control characters"):
            payload.validate_name("bad\x01name")

    def test_rejects_long_name(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            payload.validate_name("a" * 256)


class TestZipPayload(unittest.TestCase):

    def test_create_empty_zip_is_valid(self):
        zip_data = payload.create_empty_zip()
        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
            self.assertEqual(zf.namelist(), [])

    def test_add_get_list_delete_file(self):
        zip_data = payload.create_empty_zip()
        zip_data = payload.zip_add_file(zip_data, "a.txt", b"aaa")
        zip_data = payload.zip_add_file(zip_data, "b.txt", b"bbb")

        self.assertEqual(payload.zip_list_files(zip_data), ["a.txt", "b.txt"])
        self.assertEqual(payload.zip_get_file(zip_data, "a.txt"), b"aaa")

        info = payload.zip_list_files_info(zip_data)
        self.assertEqual(len(info), 2)
        self.assertEqual(info[0].name, "a.txt")
        self.assertEqual(info[0].size, 3)

        zip_data = payload.zip_delete_file(zip_data, "a.txt")
        self.assertEqual(payload.zip_list_files(zip_data), ["b.txt"])

    def test_add_duplicate_raises(self):
        zip_data = payload.zip_add_file(payload.create_empty_zip(), "a.txt", b"a")
        with self.assertRaises(ContainerFileExistsError):
            payload.zip_add_file(zip_data, "a.txt", b"b")

    def test_get_missing_raises(self):
        with self.assertRaises(ContainerFileNotFoundError):
            payload.zip_get_file(payload.create_empty_zip(), "missing.txt")

    def test_delete_missing_raises(self):
        with self.assertRaises(ContainerFileNotFoundError):
            payload.zip_delete_file(payload.create_empty_zip(), "missing.txt")


class TestEncodeDecode(unittest.TestCase):

    def setUp(self):
        self.master_key = crypto.random_bytes(32)
        self.zip_data = payload.zip_add_file(
            payload.create_empty_zip(), "hello.txt", b"hello"
        )

    def test_encode_decode_roundtrip(self):
        k, n = 2, 3
        shards = payload.encode(self.zip_data, self.master_key, k, n)
        self.assertEqual(len(shards), n)

        recovered = payload.decode(shards, list(range(n)), self.master_key, k, n)
        self.assertEqual(recovered, self.zip_data)

    def test_decode_with_threshold_subset(self):
        k, n = 2, 4
        shards = payload.encode(self.zip_data, self.master_key, k, n)
        recovered = payload.decode(
            [shards[0], shards[2], None, None], [0, 2], self.master_key, k, n
        )
        self.assertEqual(recovered, self.zip_data)

    def test_decode_with_insufficient_shards_raises(self):
        k, n = 2, 3
        shards = payload.encode(self.zip_data, self.master_key, k, n)
        with self.assertRaises(InsufficientShardsError):
            payload.decode([shards[0], None, None], [0, 1, 2], self.master_key, k, n)


if __name__ == "__main__":
    unittest.main()
