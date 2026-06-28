import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestRepair(unittest.TestCase):

    def test_repair_01_fails_without_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "repair",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: No jpegfs container found in the directory.\n",
            )

    def test_repair_02_fails_with_wrong_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            wrong_password_file = directory / "wrong.txt"
            password_file.write_text("secret\n", encoding="utf-8")
            wrong_password_file.write_text("wrong\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            init = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init.returncode, 0)

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "repair",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(wrong_password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: Invalid password or corrupted data.\n",
            )

            ls = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "ls",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(ls.returncode, 0)
            self.assertIn("Generation: 1", ls.stdout)

    def test_repair_03_reports_no_change_when_redundancy_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            init = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init.returncode, 0)

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "repair",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "Container repaired: 3/3 shards available (no change).\n",
            )
            self.assertEqual(result.stderr, "")

            ls = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "ls",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(ls.returncode, 0)
            self.assertIn("Generation: 2", ls.stdout)
            self.assertIn("Shards:     3/3 available", ls.stdout)

    def test_repair_04_adds_new_clean_jpeg_as_carrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            init = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init.returncode, 0)

            (directory / "3.jpg").write_bytes(JPEG)

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "repair",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "Container repaired: 3/3 → 4/4 shards available.\n",
            )
            self.assertEqual(result.stderr, "")

            ls = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "ls",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(ls.returncode, 0)
            self.assertIn("Generation: 2", ls.stdout)
            self.assertIn("Threshold:  2/4", ls.stdout)
            self.assertIn("Shards:     4/4 available", ls.stdout)

            for i in range(4):
                self.assertGreater((directory / f"{i}.jpg").stat().st_size, len(JPEG))

    def test_repair_05_recovers_after_lost_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            init = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init.returncode, 0)

            source = directory / "hello.txt"
            source.write_text("hello", encoding="utf-8")

            put = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "put",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    str(source),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(put.returncode, 0)

            (directory / "0.jpg").unlink()
            (directory / "3.jpg").write_bytes(JPEG)

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "repair",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "Container repaired: 2/3 → 3/3 shards available.\n",
            )
            self.assertEqual(result.stderr, "")

            read = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                ],
                capture_output=True,
            )

            self.assertEqual(read.returncode, 0)
            self.assertEqual(read.stdout, b"hello")
            self.assertEqual(read.stderr, b"")

            ls = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "ls",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(ls.returncode, 0)
            self.assertIn("Generation: 3", ls.stdout)
            self.assertIn("Shards:     3/3 available", ls.stdout)
            self.assertFalse((directory / "0.jpg").exists())
            self.assertGreater((directory / "3.jpg").stat().st_size, len(JPEG))

    def test_repair_06_fails_with_insufficient_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            init = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "2",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init.returncode, 0)

            (directory / "1.jpg").unlink()
            (directory / "2.jpg").unlink()

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "repair",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: Not enough shards to reconstruct the container.\n",
            )


if __name__ == "__main__":
    unittest.main()
