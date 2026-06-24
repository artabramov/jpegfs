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
    """
    Scan a directory for JPEG carrier files.

    Only regular files recognized as JPEG images are returned. The result
    is sorted to ensure deterministic carrier ordering during container
    creation and reconstruction.

    Args:
        directory: Directory to scan.

    Returns:
        A sorted list of JPEG file paths.
    """
    return sorted(
        p for p in directory.iterdir() if p.is_file() and jpeg.is_jpeg(p)
    )


def has_tail(path: Path) -> bool:
    """
    Check whether a JPEG file contains a jpegfs tail.

    The check is based solely on the size of the data located after the
    JPEG EOI marker. Tails smaller than the minimum jpegfs metadata size
    are ignored.

    Args:
        path: Path to a JPEG file.

    Returns:
        True if the file appears to contain a jpegfs tail, otherwise False.
    """
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
    """
    Initialize a new jpegfs container in a directory of JPEG files.

    The function scans the directory for JPEG files, verifies that none
    of them already contains a jpegfs tail, creates an empty encrypted
    payload, splits it into erasure-coded shards, and appends one shard
    plus the required key material and metadata to each carrier.

    Each carrier is first written to a temporary file. The original JPEG
    files are replaced only after all temporary files have been created
    successfully. A crash during the final replacement phase may still
    leave the directory with a partially initialized container; such a
    container should be wiped before running initialization again.

    Args:
        directory: Directory containing JPEG carrier files.
        password: Password used to protect the container master key.
        threshold: Minimum number of shards required to reconstruct.

    Raises:
        NoCarriersError: If the directory contains no JPEG files.
        ValueError: If threshold is less than 1.
        NotEnoughCarriersError: If threshold exceeds the number of JPEG files.
        ContainerExistsError: If any carrier already contains a jpegfs tail.
        OSError: If temporary files cannot be written or carrier files cannot
            be replaced.
    """
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

    tmp_map: list[tuple[Path, Path]] = []
    try:
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
            tmp = jpeg._write_tmp(path, tail)
            tmp_map.append((tmp, path))
    except BaseException:
        for tmp, _ in tmp_map:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    _two_phase_write(tmp_map, carriers[0].parent)


def load(directory: Path, password: str) -> ContainerState:
    """
    Reconstruct a jpegfs container from the JPEG files in a directory.

    All JPEG files containing jpegfs tails are scanned and grouped by
    container UUID and generation. The function attempts to derive the
    master key from available carriers using the supplied password and
    selects the newest recoverable container generation for which at
    least the required number of shards is available.

    Stale, foreign, corrupted, or incomplete container data present in
    the same directory is ignored.

    Args:
        directory: Directory containing carrier JPEG files.
        password: Container password.

    Returns:
        ContainerState describing the recovered container.

    Raises:
        ContainerNotFoundError: No jpegfs container data was found.
        InvalidPasswordError: The password does not match any recoverable
            container present in the directory.
        InsufficientShardsError: No recoverable container generation has
            enough shards to reconstruct the payload.
    """
    with_tails = [p for p in scan_jpeg_files(directory) if has_tail(p)]

    if not with_tails:
        raise ContainerNotFoundError("No jpegfs container found in the directory.")

    candidates: list[tuple[bytes, dict[tuple, dict]]] = []

    for key_path in with_tails:
        try:
            master_key = _verify_password(key_path, password)
        except Exception:
            continue

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

        candidates.append((master_key, shard_info))

    best = None
    best_master_key = None

    for master_key, shard_info in candidates:
        for gen_key in sorted(shard_info, key=lambda x: x[1], reverse=True):
            info = shard_info[gen_key]
            if len(info["shards"]) >= info["threshold"]:
                if best is None or info["generation"] > best["generation"]:
                    best = info
                    best_master_key = master_key
                break

    if best is None or best_master_key is None:
        raise InsufficientShardsError("Not enough shards to reconstruct the container.")

    k = best["threshold"]
    n = best["total"]
    available = sorted(best["shards"])[:k]

    zip_data = payload.decode(
        [best["shards"][i] for i in available], available, best_master_key, k, n
    )

    carriers = [(best["carrier_map"][i], i) for i in sorted(best["carrier_map"])]

    return ContainerState(
        master_key=best_master_key,
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
    """Re-encrypt key material on the carriers of the current generation."""
    state = load(directory, old_password)

    tmp_map: list[tuple[Path, Path]] = []
    try:
        for path, _ in state.carriers:
            tail = jpeg.read_tail(path)
            shard_meta_and_payload = tail[key_material.SIZE:]
            new_km = key_material.KeyMaterial.create(new_password, state.master_key)
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

    _two_phase_write(tmp_map, state.carriers[0][0].parent)


def repair(directory: Path, password: str) -> tuple[int, int, int]:
    """
    Rebuild the container across ALL JPEG files currently in the directory,
    incorporating any new clean files and recovering from lost shards.

    Returns (old_available, old_total, new_total) so the caller can report
    what changed.
    """
    state = load(directory, password)
    all_jpegs = scan_jpeg_files(directory)
    new_n = len(all_jpegs)

    if new_n < state.threshold:
        needed = state.threshold - new_n
        raise NotEnoughCarriersError(
            f"Not enough JPEG files. Add {needed} more JPEG file(s) to the directory."
        )

    new_generation = state.generation + 1
    new_shards = payload.encode(state.zip_data, state.master_key, state.threshold, new_n)

    tmp_map: list[tuple[Path, Path]] = []
    try:
        for i, path in enumerate(all_jpegs):
            km = key_material.KeyMaterial.create(password, state.master_key)
            sm = shard_metadata.ShardMetadata(
                container_uuid=state.container_uuid,
                container_generation=new_generation,
                container_threshold=state.threshold,
                shard_index=i,
                shard_total=new_n,
            )
            tail = km.to_bytes() + sm.encrypt(state.master_key) + new_shards[i]
            tmp = jpeg._write_tmp(path, tail)
            tmp_map.append((tmp, path))
    except BaseException:
        for tmp, _ in tmp_map:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    _two_phase_write(tmp_map, all_jpegs[0].parent)
    return len(state.carriers), state.shard_total, new_n


def wipe(directory: Path, password: str) -> int:
    """
    Remove jpegfs data from all carriers belonging to the current
    recoverable container generation.

    The function first loads the container using the supplied password and
    identifies the newest recoverable generation. Only carriers that belong
    to that generation are modified. Stale generations, foreign containers,
    and unrelated JPEG files present in the same directory are left untouched.

    Carrier files are updated atomically using the same two-phase write
    strategy as container updates: all temporary files are written and
    fsynced first, then atomically replace the originals, followed by a
    single directory fsync.

    Args:
        directory: Directory containing carrier JPEG files.
        password: Container password.

    Returns:
        Number of carrier files from which jpegfs data was removed.

    Raises:
        ContainerNotFoundError: No jpegfs container was found.
        InvalidPasswordError: The password is invalid.
        InsufficientShardsError: No recoverable container generation exists.
    """
    state = load(directory, password)
    carriers = [path for path, _ in state.carriers]

    tmp_map: list[tuple[Path, Path]] = []
    try:
        for path in carriers:
            tmp = jpeg._write_tmp(path, b"")
            tmp_map.append((tmp, path))
    except BaseException:
        for tmp, _ in tmp_map:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    _two_phase_write(tmp_map, carriers[0].parent)
    return len(carriers)
