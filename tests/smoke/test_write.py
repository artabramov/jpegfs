import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestWrite(unittest.TestCase):

    def test_write_01_fails_without_container(self):
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
                    "write",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--as",
                    "hello.txt",
                ],
                input=b"hello",
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(
                result.stderr,
                b"Error: No jpegfs container found in the directory.\n",
            )

    def test_write_02_requires_as_argument(self):
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
                    "write",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                input=b"hello",
                capture_output=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"the following arguments are required: --as", result.stderr)

    def test_write_03_writes_stdin_to_container(self):
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
                    "write",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--as",
                    "hello.txt",
                ],
                input=b"hello",
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout.decode(),
                "'hello.txt' added to the container.\n",
            )
            self.assertEqual(result.stderr.decode(), "")

    def test_write_04_fails_when_file_already_exists(self):
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

            first = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "write",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--as",
                    "hello.txt",
                ],
                input=b"hello",
                capture_output=True,
            )

            self.assertEqual(first.returncode, 0)
            self.assertEqual(first.stderr, b"")

            second = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "write",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--as",
                    "hello.txt",
                ],
                input=b"world!",
                capture_output=True,
            )

            self.assertEqual(second.returncode, 1)
            self.assertEqual(second.stdout, b"")
            self.assertEqual(
                second.stderr,
                b"Error: 'hello.txt' already exists in the container. Delete it first.\n",
            )

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


if __name__ == "__main__":
    unittest.main()
