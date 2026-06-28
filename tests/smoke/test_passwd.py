import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestPasswd(unittest.TestCase):

    def test_passwd_01_fails_without_container(self):
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
                    "passwd",
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

    def test_passwd_02_fails_with_wrong_current_password(self):
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
                    "passwd",
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

    def test_passwd_03_succeeds_with_password_file(self):
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
                    "passwd",
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
                "Password changed successfully.\n",
            )
            self.assertEqual(result.stderr, "")

    def test_passwd_04_preserves_container_data(self):
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

            passwd = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "passwd",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(passwd.returncode, 0)

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

    def test_passwd_05_does_not_increment_generation(self):
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

            passwd = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "passwd",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(passwd.returncode, 0)

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
            self.assertIn("hello.txt", ls.stdout)

    def test_passwd_06_reencrypts_key_material_only(self):
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

            before = {
                path.name: path.read_bytes()
                for path in sorted(directory.glob("*.jpg"))
            }

            passwd = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "passwd",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(passwd.returncode, 0)

            after = {
                path.name: path.read_bytes()
                for path in sorted(directory.glob("*.jpg"))
            }

            self.assertEqual(set(before), set(after))
            for name in before:
                self.assertNotEqual(before[name], after[name])

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


if __name__ == "__main__":
    unittest.main()
