

import os
from pathlib import Path

_SOI = b"\xff\xd8"
_EOI = b"\xff\xd9"


def is_jpeg(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == _SOI
    except OSError:
        return False


def _eoi_end(data: bytes) -> int:
    """Return the index of the first byte after the last JPEG EOI marker."""
    pos = data.rfind(_EOI)
    if pos == -1:
        raise ValueError(f"JPEG EOI marker not found in file data.")
    return pos + len(_EOI)


def read_jpeg_body(path: Path) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    return data[:_eoi_end(data)]


def read_tail(path: Path) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    return data[_eoi_end(data):]


def write_tail(path: Path, tail: bytes) -> None:
    """Atomically replace the tail after JPEG EOI."""
    jpeg_body = read_jpeg_body(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(jpeg_body + tail)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
