

import os
from pathlib import Path

_SOI = b"\xff\xd8"
_EOI_MARKER = 0xD9
_SOS_MARKER = 0xDA
_TEM_MARKER = 0x01
_RST_START = 0xD0
_RST_END = 0xD7
_BYTE_STUFFED = 0x00


def is_jpeg(path: Path) -> bool:
    """
    Check whether a file begins with a JPEG SOI marker.

    Returns False when the file cannot be opened or does not
    start with the expected JPEG header bytes.
    """
    try:
        with open(path, "rb") as f:
            return f.read(2) == _SOI
    except OSError:
        return False


def _eoi_end(data: bytes) -> int:
    """
    Find the true end of the JPEG image data.

    Parses JPEG markers instead of searching backward, so random
    encrypted tail bytes cannot be mistaken for the EOI marker.
    """
    if len(data) < 2 or data[:2] != _SOI:
        raise ValueError("Not a valid JPEG file (missing SOI).")

    pos = 2  # skip SOI

    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            pos += 1
            continue

        marker = data[pos + 1]

        if marker == _EOI_MARKER:  # EOI
            return pos + 2

        # Standalone markers with no payload: RST0-RST7, SOI, TEM
        if marker in (_SOI[1], _TEM_MARKER) or (_RST_START <= marker <= _RST_END):
            pos += 2
            continue

        # All other markers carry a 2-byte length field (length includes itself)
        if pos + 3 >= len(data):
            break
        seg_len = int.from_bytes(data[pos + 2: pos + 4], "big")

        if marker == _SOS_MARKER:  # SOS — followed by entropy-coded scan data
            pos += 2 + seg_len
            # Scan entropy-coded data until we hit a real marker
            while pos < len(data) - 1:
                if data[pos] != 0xFF:
                    pos += 1
                elif data[pos + 1] == _BYTE_STUFFED:  # byte-stuffed 0xFF, not a marker
                    pos += 2
                elif _RST_START <= data[pos + 1] <= _RST_END:  # restart marker
                    pos += 2
                elif data[pos + 1] == _EOI_MARKER:  # EOI
                    return pos + 2
                else:
                    break  # start of next segment; fall through to outer loop
        else:
            pos += 2 + seg_len

    raise ValueError("JPEG EOI marker not found.")


def _read_file(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _split_jpeg_and_tail(path: Path) -> tuple[bytes, bytes]:
    """
    Split a JPEG file into body and appended tail.

    Returns the validated JPEG bytes through EOI and the remaining
    post-EOI bytes used by jpegfs as carrier storage.
    """
    data = _read_file(path)
    eoi = _eoi_end(data)
    return data[:eoi], data[eoi:]


def read_jpeg_body(path: Path) -> bytes:
    """
    Read the valid JPEG body without appended tail data.

    Returns bytes from the beginning of the file through the real
    JPEG EOI marker, excluding any jpegfs data after it.
    """
    jpeg_body, _ = _split_jpeg_and_tail(path)
    return jpeg_body


def read_tail(path: Path) -> bytes:
    """
    Read bytes appended after the JPEG EOI marker.

    Returns only the post-image tail area where jpegfs stores
    key material, shard metadata, and shard payload data.
    """
    _, tail = _split_jpeg_and_tail(path)
    return tail


def write_tail(path: Path, tail: bytes) -> None:
    """
    Atomically replace the appended tail of a JPEG file.

    Preserves the original JPEG body, writes the new tail through
    a temporary file, and fsyncs the directory after replacement.
    """
    tmp = _write_tmp(path, tail)
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _write_tmp(path: Path, tail: bytes) -> Path:
    """
    Write a temporary JPEG file with a replacement tail.

    Copies the valid JPEG body, appends the supplied tail bytes,
    fsyncs the file, and returns the temporary path.
    """
    jpeg_body = read_jpeg_body(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(jpeg_body + tail)
            f.flush()
            os.fsync(f.fileno())
        return tmp
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _fsync_dir(directory: Path) -> None:
    """
    Best-effort fsync for a directory path.

    Flushes directory metadata after file replacement and silently
    ignores platforms or filesystems where this operation fails.
    """
    try:
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
