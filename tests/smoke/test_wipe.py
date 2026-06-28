import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestWipe(unittest.TestCase):

    def test_wipe_01_fails_without_container(self):
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
                    "wipe",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--yes",
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

    def test_wipe_02_requires_yes_flag(self):
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
                    "wipe",
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
            self.assertIn("the following arguments are required: --yes", result.stderr)

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

    def test_wipe_03_fails_with_wrong_password(self):
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
                    "wipe",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(wrong_password_file),
                    "--yes",
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

            for path in directory.glob("*.jpg"):
                self.assertGreater(path.stat().st_size, len(JPEG))

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

    def test_wipe_04_destroys_container(self):
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

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "wipe",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--yes",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "Container wiped: 3 file(s) cleared.\n",
            )
            self.assertEqual(result.stderr, "")

            for path in directory.glob("*.jpg"):
                self.assertEqual(path.stat().st_size, len(JPEG))

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

            self.assertEqual(ls.returncode, 1)
            self.assertEqual(ls.stdout, "")
            self.assertEqual(
                ls.stderr,
                "Error: No jpegfs container found in the directory.\n",
            )

    def test_wipe_05_allows_reinit_after_wipe(self):
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

            wipe = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "wipe",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--yes",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(wipe.returncode, 0)

            reinit = subprocess.run(
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

            self.assertEqual(reinit.returncode, 0)
            self.assertEqual(
                reinit.stdout,
                f"Container initialized in '{directory}'.\n",
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
            self.assertIn("No files.", ls.stdout)

    def test_wipe_06_leaves_clean_jpeg_files_untouched(self):
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

            clean = directory / "3.jpg"
            clean.write_bytes(JPEG)

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "jpegfs",
                    "wipe",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--yes",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "Container wiped: 3 file(s) cleared.\n",
            )

            for i in range(3):
                self.assertEqual((directory / f"{i}.jpg").stat().st_size, len(JPEG))

            self.assertEqual(clean.stat().st_size, len(JPEG))


if __name__ == "__main__":
    unittest.main()
