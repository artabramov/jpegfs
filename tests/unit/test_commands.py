import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jpegfs import commands, container, payload
from jpegfs.errors import ContainerNotFoundError


JPEG = b"\xff\xd8\xff\xd9"
PASSWORD = "secret"


def _make_carriers(directory: Path, count: int) -> None:
    for i in range(count):
        (directory / f"{i}.jpg").write_bytes(JPEG)


def _password_file(directory: Path, password: str = PASSWORD) -> Path:
    path = directory / "password.txt"
    path.write_text(f"{password}\n", encoding="utf-8")
    return path


def _args(directory: Path, **kwargs) -> argparse.Namespace:
    defaults = {
        "dir": str(directory),
        "password_file": str(_password_file(directory)),
        "as_name": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _run_cmd(func, args):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        func(args)
    return stdout.getvalue(), stderr.getvalue()


class TestFmtSize(unittest.TestCase):

    def test_formats_bytes(self):
        self.assertEqual(commands._fmt_size(0), "0 B")
        self.assertEqual(commands._fmt_size(512), "512 B")

    def test_formats_kilobytes(self):
        self.assertEqual(commands._fmt_size(1024), "1.0 KB")
        self.assertEqual(commands._fmt_size(1536), "1.5 KB")

    def test_formats_megabytes(self):
        self.assertEqual(commands._fmt_size(1024 ** 2), "1.0 MB")


class TestReadPassword(unittest.TestCase):

    def test_reads_password_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            password_file = _password_file(Path(tmp), "from-file")
            args = argparse.Namespace(password_file=str(password_file))
            self.assertEqual(commands._read_password(args), "from-file")

    def test_exits_when_password_file_unreadable(self):
        args = argparse.Namespace(password_file="/nonexistent/password.txt")
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stderr(io.StringIO()):
                commands._read_password(args)
        self.assertEqual(ctx.exception.code, 1)

    @patch("jpegfs.commands.getpass.getpass", side_effect=["secret", "other"])
    def test_exits_when_confirmation_does_not_match(self, _mock_getpass):
        args = argparse.Namespace(password_file=None)
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stderr(io.StringIO()):
                commands._read_password(args, confirm=True)
        self.assertEqual(ctx.exception.code, 1)


class TestCmdHelp(unittest.TestCase):

    def test_prints_help_text(self):
        stdout, _ = _run_cmd(commands.cmd_help, argparse.Namespace())
        self.assertIn("jpegfs — encrypted file container", stdout)
        self.assertIn("init --threshold K", stdout)


class TestCmdInit(unittest.TestCase):

    def test_initializes_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            stdout, stderr = _run_cmd(commands.cmd_init, _args(directory, threshold=2))
            self.assertEqual(stderr, "")
            self.assertIn("Container initialized", stdout)
            container.load(directory, PASSWORD)

    def test_exits_when_directory_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            password_file = _password_file(Path(tmp))
            missing = Path(tempfile.gettempdir()) / "jpegfs-missing-dir"
            args = argparse.Namespace(
                dir=str(missing),
                password_file=str(password_file),
                threshold=2,
            )
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(io.StringIO()):
                    commands.cmd_init(args)
            self.assertEqual(ctx.exception.code, 1)


class TestCmdLs(unittest.TestCase):

    def test_lists_empty_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            stdout, stderr = _run_cmd(commands.cmd_ls, _args(directory))
            self.assertEqual(stderr, "")
            self.assertIn("Generation: 1", stdout)
            self.assertIn("No files.", stdout)

    def test_lists_stored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            container.put_file(directory, PASSWORD, "hello.txt", b"hello")
            stdout, stderr = _run_cmd(commands.cmd_ls, _args(directory))
            self.assertEqual(stderr, "")
            self.assertIn("hello.txt", stdout)
            self.assertIn("5 B", stdout)


class TestCmdPut(unittest.TestCase):

    def test_puts_file_into_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            source = directory / "source.txt"
            source.write_text("payload", encoding="utf-8")
            stdout, stderr = _run_cmd(
                commands.cmd_put, _args(directory, file=str(source))
            )
            self.assertEqual(stderr, "")
            self.assertIn("'source.txt' added", stdout)
            self.assertEqual(
                container.get_file(directory, PASSWORD, "source.txt"),
                b"payload",
            )

    def test_exits_when_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            args = _args(directory, file=str(directory / "missing.txt"))
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(io.StringIO()):
                    commands.cmd_put(args)
            self.assertEqual(ctx.exception.code, 1)


class TestCmdWrite(unittest.TestCase):

    @patch("jpegfs.commands.sys.stdin")
    def test_writes_stdin_to_container(self, mock_stdin):
        mock_stdin.buffer = io.BytesIO(b"from stdin")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            stdout, stderr = _run_cmd(
                commands.cmd_write, _args(directory, as_name="stdin.txt")
            )
            self.assertEqual(stderr, "")
            self.assertIn("'stdin.txt' added", stdout)
            self.assertEqual(
                container.get_file(directory, PASSWORD, "stdin.txt"),
                b"from stdin",
            )


class TestCmdGet(unittest.TestCase):

    def test_extracts_file_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            container.put_file(directory, PASSWORD, "hello.txt", b"hello")
            output = directory / "out.txt"
            stdout, stderr = _run_cmd(
                commands.cmd_get,
                _args(directory, name="hello.txt", as_name=str(output)),
            )
            self.assertEqual(stderr, "")
            self.assertIn("extracted to", stdout)
            self.assertEqual(output.read_bytes(), b"hello")


class TestCmdRead(unittest.TestCase):

    @patch("jpegfs.commands.sys.stdout")
    def test_writes_file_to_stdout_buffer(self, mock_stdout):
        stdout_buf = io.BytesIO()
        mock_stdout.buffer = stdout_buf
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            container.put_file(directory, PASSWORD, "hello.txt", b"hello")
            commands.cmd_read(_args(directory, name="hello.txt"))
            self.assertEqual(stdout_buf.getvalue(), b"hello")


class TestCmdDel(unittest.TestCase):

    def test_deletes_file_from_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            container.put_file(directory, PASSWORD, "hello.txt", b"hello")
            stdout, stderr = _run_cmd(
                commands.cmd_del, _args(directory, name="hello.txt")
            )
            self.assertEqual(stderr, "")
            self.assertIn("'hello.txt' deleted", stdout)
            state = container.load(directory, PASSWORD)
            self.assertEqual(payload.zip_list_files(state.zip_data), [])


class TestCmdPasswd(unittest.TestCase):

    @patch("jpegfs.commands.getpass.getpass", side_effect=["old", "new", "new"])
    def test_changes_password(self, _mock_getpass):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, "old", 2)
            container.put_file(directory, "old", "hello.txt", b"hello")
            args = argparse.Namespace(dir=str(directory), password_file=None)
            stdout, stderr = _run_cmd(commands.cmd_passwd, args)
            self.assertEqual(stderr, "")
            self.assertIn("Password changed successfully.", stdout)
            self.assertEqual(
                container.get_file(directory, "new", "hello.txt"),
                b"hello",
            )


class TestCmdWipe(unittest.TestCase):

    def test_wipes_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            stdout, stderr = _run_cmd(commands.cmd_wipe, _args(directory, yes=True))
            self.assertEqual(stderr, "")
            self.assertIn("Container wiped: 3 file(s) cleared.", stdout)
            with self.assertRaises(ContainerNotFoundError):
                container.load(directory, PASSWORD)


class TestCmdRepair(unittest.TestCase):

    def test_reports_no_change_when_redundancy_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            stdout, stderr = _run_cmd(commands.cmd_repair, _args(directory))
            self.assertEqual(stderr, "")
            self.assertIn("(no change)", stdout)

    def test_reports_added_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _make_carriers(directory, 3)
            container.init(directory, PASSWORD, 2)
            (directory / "3.jpg").write_bytes(JPEG)
            stdout, stderr = _run_cmd(commands.cmd_repair, _args(directory))
            self.assertEqual(stderr, "")
            self.assertIn("3/3 → 4/4", stdout)


if __name__ == "__main__":
    unittest.main()
