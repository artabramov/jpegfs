import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestInit(unittest.TestCase):

    def test_01_init_fails_without_carriers(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            result = subprocess.run(
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

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No JPEG files found", result.stderr)

    def test_02_init_fails_with_zero_threshold(self):
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
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "0",
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Threshold must be at least 1", result.stderr)

    def test_03_init_fails_when_threshold_exceeds_carriers(self):
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
                    "init",
                    "--dir",
                    str(directory),
                    "--password-file",
                    str(password_file),
                    "--threshold",
                    "4",
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds the number of JPEG files", result.stderr)

    def test_04_init_creates_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            result = subprocess.run(
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

            self.assertEqual(result.returncode, 0)

            for path in directory.glob("*.jpg"):
                self.assertGreater(path.stat().st_size, len(JPEG))


    def test_05_init_fails_when_container_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            command = [
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
            ]

            first = subprocess.run(command, capture_output=True, text=True)

            self.assertEqual(
                first.returncode,
                0,
                msg=f"stdout:\n{first.stdout}\n\nstderr:\n{first.stderr}",
            )

            second = subprocess.run(command, capture_output=True, text=True)

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already has a jpegfs tail", second.stderr)


if __name__ == "__main__":
    unittest.main()
