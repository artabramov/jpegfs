import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestGet(unittest.TestCase):

    def test_get_01_fails_without_container(self):
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
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: No jpegfs container found in the directory.\n",
            )

    def test_get_02_requires_name_argument(self):
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
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("the following arguments are required: NAME", result.stderr)

    def test_get_03_fails_when_file_not_in_container(self):
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
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "missing.txt",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: 'missing.txt' not found in the container.\n",
            )
            self.assertFalse((directory / "missing.txt").exists())

    def test_get_04_extracts_file_with_original_name(self):
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

            source.unlink()

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "'hello.txt' extracted to 'hello.txt'.\n",
            )
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                (directory / "hello.txt").read_text(encoding="utf-8"),
                "hello",
            )

    def test_get_05_extracts_file_with_custom_name(self):
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
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                    "--as",
                    "copy.txt",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "'hello.txt' extracted to 'copy.txt'.\n",
            )
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                (directory / "copy.txt").read_text(encoding="utf-8"),
                "hello",
            )
            self.assertTrue((directory / "hello.txt").exists())

    def test_get_06_fails_on_invalid_name(self):
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
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "../x",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: File name must not contain path separators: '../x'.\n",
            )

    def test_get_07_fails_with_wrong_password(self):
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

            source.unlink()

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "get",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(wrong_password_file),
                    "hello.txt",
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr,
                "Error: Invalid password or corrupted data.\n",
            )
            self.assertFalse((directory / "hello.txt").exists())


if __name__ == "__main__":
    unittest.main()
