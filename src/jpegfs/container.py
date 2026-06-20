

from pathlib import Path

from . import crypto, jpeg, key_material, payload, shard_metadata
from .errors import ContainerExistsError, NoCarriersError, NotEnoughCarriersError

_MASTER_KEY_SIZE = 32
_UUID_SIZE = 16
_TAIL_MIN_SIZE = key_material.SIZE + shard_metadata.SIZE  # 76 + 54 = 130


def scan_jpeg_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.is_file() and jpeg.is_jpeg(p))


def has_tail(path: Path) -> bool:
    return len(jpeg.read_tail(path)) >= _TAIL_MIN_SIZE


def init(directory: Path, password: str, threshold: int) -> None:
    carriers = scan_jpeg_files(directory)

    if not carriers:
        raise NoCarriersError("No JPEG files found in the directory.")

    n = len(carriers)

    if threshold < 1:
        raise ValueError("Threshold must be at least 1.")

    if threshold > n:
        raise NotEnoughCarriersError(
            f"Threshold ({threshold}) exceeds the number of JPEG files ({n})."
        )

    for path in carriers:
        if has_tail(path):
            raise ContainerExistsError(
                f"'{path.name}' already has a jpegfs tail. "
                "Use 'wipe' to remove the existing container first."
            )

    master_key = crypto.random_bytes(_MASTER_KEY_SIZE)
    container_uuid = crypto.random_bytes(_UUID_SIZE)
    generation = 1

    empty_zip = payload.create_empty_zip()
    shards = payload.encode(empty_zip, master_key, threshold, n)

    for i, (path, shard) in enumerate(zip(carriers, shards)):
        km = key_material.KeyMaterial.create(password, master_key)
        sm = shard_metadata.ShardMetadata(
            container_uuid=container_uuid,
            container_generation=generation,
            container_threshold=threshold,
            shard_index=i,
            shard_total=n,
        )
        tail = km.to_bytes() + sm.encrypt(master_key) + shard
        jpeg.write_tail(path, tail)
