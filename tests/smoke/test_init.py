import subprocess
import tempfile
import unittest
from pathlib import Path


JPEG = b"\xff\xd8\xff\xd9"


class TestInit(unittest.TestCase):

    def test_init_01_fails_without_carriers(self):
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

    def test_init_02_fails_with_zero_threshold(self):
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

    def test_init_03_fails_when_threshold_exceeds_carriers(self):
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

    def test_init_04_accepts_threshold_equal_to_one(self):
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
                    "1",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)

            for path in directory.glob("*.jpg"):
                if path.name == "password.txt":
                    continue

                self.assertGreater(path.stat().st_size, len(JPEG))

    def test_init_05_accepts_threshold_equal_to_carriers(self):
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
                    "3",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)

            for path in directory.glob("*.jpg"):
                if path.name == "password.txt":
                    continue

                self.assertGreater(path.stat().st_size, len(JPEG))

    def test_init_06_ignores_non_jpeg_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            (directory / "file.txt").write_text("hello")
            (directory / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (directory / "data.bin").write_bytes(b"\x00\x01\x02")

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

            self.assertEqual((directory / "file.txt").read_text(), "hello")
            self.assertEqual(
                (directory / "image.png").read_bytes(),
                b"\x89PNG\r\n\x1a\n",
            )
            self.assertEqual(
                (directory / "data.bin").read_bytes(),
                b"\x00\x01\x02",
            )

    def test_init_07_fails_when_any_carrier_already_contains_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            password_file = directory / "password.txt"
            password_file.write_text("secret\n", encoding="utf-8")

            for i in range(3):
                (directory / f"{i}.jpg").write_bytes(JPEG)

            first = subprocess.run(
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

            self.assertEqual(first.returncode, 0)

            (directory / "3.jpg").write_bytes(JPEG)

            second = subprocess.run(
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

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already has a jpegfs tail", second.stderr)

            self.assertEqual((directory / "3.jpg").stat().st_size, len(JPEG))

    def test_init_08_creates_container(self):
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
            self.assertEqual(
                result.stdout,
                f"Container initialized in '{directory}'.\n",
            )
            self.assertEqual(result.stderr, "")

            for path in directory.glob("*.jpg"):
                self.assertGreater(path.stat().st_size, len(JPEG))

            list_result = subprocess.run(
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

            self.assertEqual(list_result.returncode, 0)

            self.assertRegex(
                list_result.stdout,
                r"UUID:\s+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            )

            self.assertIn("Generation: 1", list_result.stdout)
            self.assertIn("Threshold:  2/3", list_result.stdout)
            self.assertIn("Shards:     3/3 available", list_result.stdout)
            self.assertIn("Size:       0 B", list_result.stdout)
            self.assertIn("No files.", list_result.stdout)

    def test_init_09_fails_when_container_already_exists(self):
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
