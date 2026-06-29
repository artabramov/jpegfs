import tempfile
import unittest
from pathlib import Path

from jpegfs import container, jpeg, payload
from jpegfs.errors import (
    ContainerExistsError,
    ContainerNotFoundError,
    InsufficientShardsError,
    InvalidPasswordError,
    NoCarriersError,
    NotEnoughCarriersError,
)


JPEG = b"\xff\xd8\xff\xd9"
PASSWORD = "secret"


def _make_carriers(directory: Path, count: int) -> None:
    for i in range(count):
        (directory / f"{i}.jpg").write_bytes(JPEG)


class TestContainerHelpers(unittest.TestCase):

    def test_scan_jpeg_files_ignores_non_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 2)
            (directory / "note.txt").write_text("hello")
            self.assertEqual(len(container.scan_jpeg_files(directory)), 2)

    def test_has_tail_false_for_clean_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "0.jpg"
            path.write_bytes(JPEG)
            self.assertFalse(container.has_tail(path))

    def test_has_tail_true_for_any_appended_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "0.jpg"
            path.write_bytes(JPEG)
            jpeg.write_tail(path, b"x")
            self.assertTrue(container.has_tail(path))


class TestContainerInit(unittest.TestCase):

    def test_init_raises_without_carriers(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NoCarriersError):
                container.init(Path(tmp), PASSWORD, 2)

    def test_init_raises_for_invalid_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)

            with self.assertRaisesRegex(ValueError, "at least 1"):
                container.init(directory, PASSWORD, 0)

            with self.assertRaises(NotEnoughCarriersError):
                container.init(directory, PASSWORD, 4)

    def test_init_raises_when_any_tail_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            jpeg.write_tail(directory / "0.jpg", b"x")

            with self.assertRaises(ContainerExistsError):
                container.init(directory, PASSWORD, 2)

    def test_init_raises_when_container_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)

            with self.assertRaises(ContainerExistsError):
                container.init(directory, PASSWORD, 2)

    def test_init_and_load_empty_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)

            state = container.load(directory, PASSWORD)
            self.assertEqual(state.container_generation, 1)
            self.assertEqual(state.container_threshold, 2)
            self.assertEqual(state.shard_total, 3)
            self.assertEqual(len(state.carriers), 3)
            self.assertEqual(payload.zip_list_files(state.zip_data), [])

    def test_load_raises_invalid_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)

            with self.assertRaises(InvalidPasswordError):
                container.load(directory, "wrong")


class TestContainerFileOps(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        _make_carriers(self.directory, 3)
        container.init(self.directory, PASSWORD, 2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_put_and_get_file(self):
        container.put_file(self.directory, PASSWORD, "hello.txt", b"hello")
        self.assertEqual(
            container.get_file(self.directory, PASSWORD, "hello.txt"),
            b"hello",
        )

    def test_del_file(self):
        container.put_file(self.directory, PASSWORD, "hello.txt", b"hello")
        container.del_file(self.directory, PASSWORD, "hello.txt")

        state = container.load(self.directory, PASSWORD)
        self.assertEqual(payload.zip_list_files(state.zip_data), [])

    def test_store_increments_container_generation(self):
        container.put_file(self.directory, PASSWORD, "a.txt", b"a")
        state = container.load(self.directory, PASSWORD)
        self.assertEqual(state.container_generation, 2)


class TestContainerPassword(unittest.TestCase):

    def test_change_password_allows_new_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, "old", 2)
            container.put_file(directory, "old", "hello.txt", b"hello")

            container.change_password(directory, "old", "new")

            self.assertEqual(
                container.get_file(directory, "new", "hello.txt"),
                b"hello",
            )
            state = container.load(directory, "new")
            self.assertEqual(state.container_generation, 2)


class TestContainerWipe(unittest.TestCase):

    def test_wipe_removes_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)

            count = container.wipe(directory, PASSWORD)

            self.assertEqual(count, 3)
            for path in directory.glob("*.jpg"):
                self.assertEqual(path.stat().st_size, len(JPEG))

            with self.assertRaises(ContainerNotFoundError):
                container.load(directory, PASSWORD)


class TestContainerRepair(unittest.TestCase):

    def test_repair_adds_new_carrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            container.put_file(directory, PASSWORD, "hello.txt", b"hello")
            (directory / "3.jpg").write_bytes(JPEG)

            old_available, old_total, new_total = container.repair(directory, PASSWORD)

            self.assertEqual((old_available, old_total, new_total), (3, 3, 4))
            state = container.load(directory, PASSWORD)
            self.assertEqual(state.shard_total, 4)
            self.assertEqual(
                container.get_file(directory, PASSWORD, "hello.txt"),
                b"hello",
            )

    def test_repair_raises_with_insufficient_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)

            (directory / "1.jpg").unlink()
            (directory / "2.jpg").unlink()

            with self.assertRaises(InsufficientShardsError):
                container.repair(directory, PASSWORD)


if __name__ == "__main__":
    unittest.main()
