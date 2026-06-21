import os
from dataclasses import dataclass
from pathlib import Path

from . import crypto, jpeg, key_material, payload, shard_metadata
from .errors import (
    ContainerExistsError,
    ContainerFileNotFoundError,
    ContainerNotFoundError,
    InsufficientShardsError,
    NoCarriersError,
    NotEnoughCarriersError,
)

_MASTER_KEY_SIZE = 32
_UUID_SIZE = 16
_TAIL_MIN_SIZE = key_material.SIZE + shard_metadata.SIZE  # 76 + 54 = 130


@dataclass
class ContainerState:
    master_key: bytes
    container_uuid: bytes
    generation: int
    threshold: int
    shard_total: int
    carriers: list[tuple[Path, int]]  # (path, shard_index)
    zip_data: bytes


def scan_jpeg_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.is_file() and jpeg.is_jpeg(p))


def has_tail(path: Path) -> bool:
    return len(jpeg.read_tail(path)) >= _TAIL_MIN_SIZE


def _verify_password(path: Path, password: str) -> bytes:
    """Decrypt master_key from a carrier to confirm the password is correct."""
    tail = jpeg.read_tail(path)
    km = key_material.KeyMaterial.from_bytes(tail)
    return km.decrypt_master_key(password)


def _two_phase_write(tmp_map: list[tuple[Path, Path]], directory: Path) -> None:
    """Phase 2 + 3: replace all originals, then fsync directory."""
    for tmp, original in tmp_map:
        os.replace(tmp, original)
    jpeg._fsync_dir(directory)


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


def load(directory: Path, password: str) -> ContainerState:
    """Reconstruct the container from available shards."""
    with_tails = [p for p in scan_jpeg_files(directory) if has_tail(p)]

    if not with_tails:
        raise ContainerNotFoundError("No jpegfs container found in the directory.")

    master_key = _verify_password(with_tails[0], password)

    shard_info: dict[tuple, dict] = {}

    for path in with_tails:
        tail = jpeg.read_tail(path)
        try:
            sm = shard_metadata.ShardMetadata.from_encrypted(
                tail[key_material.SIZE:], master_key
            )
        except Exception:
            continue

        shard_bytes = tail[key_material.SIZE + shard_metadata.SIZE:]
        gen_key = (sm.container_uuid, sm.container_generation)

        if gen_key not in shard_info:
            shard_info[gen_key] = {
                "uuid": sm.container_uuid,
                "generation": sm.container_generation,
                "threshold": sm.container_threshold,
                "total": sm.shard_total,
                "shards": {},
                "carrier_map": {},
            }

        info = shard_info[gen_key]
        info["shards"][sm.shard_index] = shard_bytes
        info["carrier_map"][sm.shard_index] = path

    best = None
    for gen_key in sorted(shard_info, key=lambda x: x[1], reverse=True):
        info = shard_info[gen_key]
        if len(info["shards"]) >= info["threshold"]:
            best = info
            break

    if best is None:
        raise InsufficientShardsError("Not enough shards to reconstruct the container.")

    k = best["threshold"]
    n = best["total"]
    available = sorted(best["shards"])[:k]

    zip_data = payload.decode(
        [best["shards"][i] for i in available], available, master_key, k, n
    )

    carriers = [(best["carrier_map"][i], i) for i in sorted(best["carrier_map"])]

    return ContainerState(
        master_key=master_key,
        container_uuid=best["uuid"],
        generation=best["generation"],
        threshold=k,
        shard_total=n,
        carriers=carriers,
        zip_data=zip_data,
    )


def store(state: ContainerState, new_zip_data: bytes, password: str) -> None:
    """Write updated container to all carriers with generation + 1."""
    new_generation = state.generation + 1
    new_shards = payload.encode(
        new_zip_data, state.master_key, state.threshold, state.shard_total
    )

    tmp_map: list[tuple[Path, Path]] = []
    try:
        for path, shard_index in state.carriers:
            km = key_material.KeyMaterial.create(password, state.master_key)
            sm = shard_metadata.ShardMetadata(
                container_uuid=state.container_uuid,
                container_generation=new_generation,
                container_threshold=state.threshold,
                shard_index=shard_index,
                shard_total=state.shard_total,
            )
            tail = km.to_bytes() + sm.encrypt(state.master_key) + new_shards[shard_index]
            tmp = jpeg._write_tmp(path, tail)
            tmp_map.append((tmp, path))
    except BaseException:
        for tmp, _ in tmp_map:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    _two_phase_write(tmp_map, state.carriers[0][0].parent)


def put_file(directory: Path, password: str, name: str, content: bytes) -> None:
    state = load(directory, password)
    new_zip = payload.zip_add_file(state.zip_data, name, content)
    store(state, new_zip, password)


def get_file(directory: Path, password: str, name: str) -> bytes:
    state = load(directory, password)
    return payload.zip_get_file(state.zip_data, name)


def del_file(directory: Path, password: str, name: str) -> None:
    state = load(directory, password)
    new_zip = payload.zip_delete_file(state.zip_data, name)
    store(state, new_zip, password)


def change_password(directory: Path, old_password: str, new_password: str) -> None:
    """Re-encrypt key material on every carrier with the new password."""
    carriers = [p for p in scan_jpeg_files(directory) if has_tail(p)]

    if not carriers:
        raise ContainerNotFoundError("No jpegfs container found in the directory.")

    master_key = _verify_password(carriers[0], old_password)

    tmp_map: list[tuple[Path, Path]] = []
    try:
        for path in carriers:
            tail = jpeg.read_tail(path)
            shard_meta_and_payload = tail[key_material.SIZE:]
            new_km = key_material.KeyMaterial.create(new_password, master_key)
            new_tail = new_km.to_bytes() + shard_meta_and_payload
            tmp = jpeg._write_tmp(path, new_tail)
            tmp_map.append((tmp, path))
    except BaseException:
        for tmp, _ in tmp_map:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    _two_phase_write(tmp_map, carriers[0].parent)


def wipe(directory: Path, password: str) -> int:
    """Remove jpegfs tails from all carrier JPEGs. Returns the number of wiped files."""
    carriers = [p for p in scan_jpeg_files(directory) if has_tail(p)]

    if not carriers:
        raise ContainerNotFoundError("No jpegfs container found in the directory.")

    _verify_password(carriers[0], password)

    for path in carriers:
        jpeg.write_tail(path, b"")

    return len(carriers)
