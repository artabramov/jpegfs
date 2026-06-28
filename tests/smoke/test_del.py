import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestDel(unittest.TestCase):

    def test_del_01_fails_without_container(self):
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
                    "del",
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

    def test_del_02_requires_name_argument(self):
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
                    "del",
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

    def test_del_03_fails_when_file_not_in_container(self):
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
                    "del",
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

    def test_del_04_deletes_file_from_container(self):
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
                    "del",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "'hello.txt' deleted from the container.\n",
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
                text=True,
            )

            self.assertEqual(read.returncode, 1)
            self.assertEqual(read.stdout, "")
            self.assertEqual(
                read.stderr,
                "Error: 'hello.txt' not found in the container.\n",
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
            self.assertIn("No files.", ls.stdout)

    def test_del_05_leaves_other_files_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            hello = directory / "hello.txt"
            world = directory / "world.txt"
            hello.write_text("hello", encoding="utf-8")
            world.write_text("world", encoding="utf-8")

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

            for source in (hello, world):
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
                    "del",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)

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
                    "world.txt",
                ],
                capture_output=True,
            )

            self.assertEqual(read.returncode, 0)
            self.assertEqual(read.stdout, b"world")
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
            self.assertNotIn("hello.txt", ls.stdout)
            self.assertIn("world.txt", ls.stdout)
            self.assertIn("1 file(s)", ls.stdout)

    def test_del_06_fails_on_invalid_name(self):
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
                    "del",
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

    def test_del_07_fails_with_wrong_password(self):
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
                    "del",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(wrong_password_file),
                    "hello.txt",
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

    def test_del_08_increments_generation(self):
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

            delete = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "del",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "hello.txt",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(delete.returncode, 0)

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
            self.assertIn("No files.", ls.stdout)


if __name__ == "__main__":
    unittest.main()
