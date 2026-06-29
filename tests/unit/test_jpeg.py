import tempfile
import unittest
from pathlib import Path

from jpegfs import jpeg


JPEG_BODY = b"\xff\xd8\xff\xd9"
JPEG_WITH_TAIL = JPEG_BODY + b"tail-data"


class TestJpeg(unittest.TestCase):
    def test_is_jpeg_returns_true_for_jpeg_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.jpg"
            path.write_bytes(JPEG_BODY)

            self.assertTrue(jpeg.is_jpeg(path))

    def test_is_jpeg_returns_false_for_non_jpeg_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "file.txt"
            path.write_bytes(b"not jpeg")

            self.assertFalse(jpeg.is_jpeg(path))

    def test_is_jpeg_returns_false_for_missing_file(self):
        path = Path("missing.jpg")

        self.assertFalse(jpeg.is_jpeg(path))

    def test_read_jpeg_body_returns_data_up_to_eoi(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.jpg"
            path.write_bytes(JPEG_WITH_TAIL)

            self.assertEqual(jpeg.read_jpeg_body(path), JPEG_BODY)

    def test_read_tail_returns_data_after_eoi(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.jpg"
            path.write_bytes(JPEG_WITH_TAIL)

            self.assertEqual(jpeg.read_tail(path), b"tail-data")

    def test_write_tail_replaces_existing_tail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.jpg"
            path.write_bytes(JPEG_WITH_TAIL)

            jpeg.write_tail(path, b"new-tail")

            self.assertEqual(path.read_bytes(), JPEG_BODY + b"new-tail")

    def test_read_tail_ignores_false_eoi_in_tail(self):
        fake_eoi_tail = b"\xff\xd9" + b"real-tail"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.jpg"
            path.write_bytes(JPEG_BODY + fake_eoi_tail)

            self.assertEqual(jpeg.read_jpeg_body(path), JPEG_BODY)
            self.assertEqual(jpeg.read_tail(path), fake_eoi_tail)


if __name__ == "__main__":
    unittest.main()
