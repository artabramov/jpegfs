import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestRead(unittest.TestCase):

    def test_read_01_fails_without_container(self):
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
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
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

    def test_read_02_requires_name_argument(self):
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
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("the following arguments are required: NAME", result.stderr)

    def test_read_03_fails_when_file_not_in_container(self):
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
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "missing.txt",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: 'missing.txt' not found in the container.\n",
            )

    def test_read_04_reads_file_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            source = directory / "hello.txt"
            source.write_text("hello", encoding="utf-8")

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

            result = subprocess.run(
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

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"hello")
            self.assertEqual(result.stderr, b"")

    def test_read_05_reads_binary_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            source = directory / "data.bin"
            content = b"hello\x00world\xff\xfe"
            source.write_bytes(content)

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

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "data.bin",
                ],
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, content)
            self.assertEqual(result.stderr, b"")

    def test_read_06_fails_on_invalid_name(self):
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
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "../x",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: File name must not contain path separators: '../x'.\n",
            )

    def test_read_07_fails_with_wrong_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            wrong_password_file = directory / "wrong.txt"
            password_file.write_text("secret\n", encoding="utf-8")
            wrong_password_file.write_text("wrong\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            source = directory / "hello.txt"
            source.write_text("hello", encoding="utf-8")

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

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "read",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(wrong_password_file),
                    "hello.txt",
                ],
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(
                result.stderr,
                b"Error: Invalid password or corrupted data.\n",
            )


if __name__ == "__main__":
    unittest.main()
