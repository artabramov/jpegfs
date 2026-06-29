import os
from dataclasses import dataclass
from pathlib import Path

from . import crypto, jpeg, key_material, payload, shard_metadata
from .errors import (
    ContainerExistsError,
    ContainerNotFoundError,
    InsufficientShardsError,
    InvalidPasswordError,
    NoCarriersError,
    NotEnoughCarriersError,
)

_MASTER_KEY_SIZE = 32
_CONTAINER_UUID_SIZE = 16


@dataclass
class ContainerState:
    master_key: bytes          # 32 bytes
    container_uuid: bytes      # 16 bytes
    container_generation: int  # 4 bytes
    container_threshold: int   # 2 bytes
    shard_total: int           # 2 bytes
    carriers: list[tuple[Path, int]]  # (path, shard_index)
    zip_data: bytes


@dataclass
class _GenerationInfo:
    """
    Reconstructable shard set for one container generation.

    Stores shard payloads and their source carriers for a specific
    `(container_uuid, container_generation)` pair.
    """
    container_uuid: bytes
    container_generation: int
    container_threshold: int
    shard_total: int
    shards: dict[int, bytes]
    carrier_map: dict[int, Path]


@dataclass
class _LoadCandidate:
    """
    One password-verified decryption candidate.

    Holds the recovered master key and generations that were
    successfully parsed with that key.
    """
    master_key: bytes
    generations: dict[tuple[bytes, int], _GenerationInfo]


def scan_jpeg_files(directory: Path) -> list[Path]:
    """
    Find usable JPEG carrier files in a directory.

    Returns only regular files that start with a JPEG SOI marker,
    sorted for deterministic shard placement.
    """
    return sorted(
        p for p in directory.iterdir() if p.is_file() and jpeg.is_jpeg(p)
    )


def has_tail(path: Path) -> bool:
    """
    Check whether a JPEG file has any appended data after EOI.

    Returns True when bytes are present after the JPEG EOI marker,
    indicating the file may carry jpegfs container data.
    """
    return len(jpeg.read_tail(path)) > 0


def _two_phase_write(tmp_map: list[tuple[Path, Path]], directory: Path) -> None:
    """
    Replace prepared temporary files with their final paths.

    Performs the final atomic replacement phase for carrier updates
    and fsyncs the containing directory afterward.
    """
    for tmp, original in tmp_map:
        os.replace(tmp, original)
    jpeg._fsync_dir(directory)


def _cleanup_tmp_files(tmp_map: list[tuple[Path, Path]]) -> None:
    """
    Best-effort removal of temporary carrier files.

    Used during failed update phases to avoid leaving stale `.tmp`
    files near carrier JPEGs.
    """
    for tmp, _ in tmp_map:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _rewrite_carrier_tails(updates: list[tuple[Path, bytes]]) -> None:
    """
    Atomically rewrite tails for a set of carrier files.

    Writes all temporary files first and replaces originals only after
    every temporary write succeeds.
    """
    if not updates:
        return

    tmp_map: list[tuple[Path, Path]] = []
    try:
        for path, tail in updates:
            tmp = jpeg._write_tmp(path, tail)
            tmp_map.append((tmp, path))
    except BaseException:
        _cleanup_tmp_files(tmp_map)
        raise

    _two_phase_write(tmp_map, updates[0][0].parent)


def _build_tail(
    password: str,
    master_key: bytes,
    metadata: shard_metadata.ShardMetadata,
    shard_bytes: bytes,
) -> bytes:
    """
    Build one complete carrier tail.

    Combines key material, encrypted shard metadata, and shard payload
    in the on-disk jpegfs tail layout.
    """
    km = key_material.KeyMaterial.create(password, master_key)
    return km.to_bytes() + metadata.encrypt(master_key) + shard_bytes


def _latest_recoverable_generation(
    generations: dict[tuple[bytes, int], _GenerationInfo]
) -> _GenerationInfo | None:
    """
    Pick the newest generation with enough shards for decoding.
    """
    for key in sorted(generations, key=lambda x: x[1], reverse=True):
        info = generations[key]
        if len(info.shards) >= info.container_threshold:
            return info
    return None


def _collect_generations_for_master_key(
    tails: dict[Path, bytes], master_key: bytes
) -> dict[tuple[bytes, int], _GenerationInfo]:
    """
    Parse all carrier tails using a candidate master key.

    Returns generations keyed by `(container_uuid, container_generation)`
    for tails whose shard metadata decrypts with the provided key.
    """
    generations: dict[tuple[bytes, int], _GenerationInfo] = {}

    for path, tail in tails.items():
        try:
            sm = shard_metadata.ShardMetadata.from_encrypted(
                tail[key_material.SIZE:], master_key
            )
        except Exception:
            continue

        shard_bytes = tail[key_material.SIZE + shard_metadata.SIZE:]
        generation_key = (sm.container_uuid, sm.container_generation)

        if generation_key not in generations:
            generations[generation_key] = _GenerationInfo(
                container_uuid=sm.container_uuid,
                container_generation=sm.container_generation,
                container_threshold=sm.container_threshold,
                shard_total=sm.shard_total,
                shards={},
                carrier_map={},
            )

        info = generations[generation_key]
        info.shards[sm.shard_index] = shard_bytes
        info.carrier_map[sm.shard_index] = path

    return generations


def _collect_load_candidates(tails: dict[Path, bytes], password: str) -> list[_LoadCandidate]:
    """
    Build decryption candidates from password-verifiable carriers.

    Each candidate is rooted at one tail whose key material decrypts
    with the user password.
    """
    candidates: list[_LoadCandidate] = []

    for key_tail in tails.values():
        try:
            km = key_material.KeyMaterial.from_bytes(key_tail)
            master_key = km.decrypt_master_key(password)
        except Exception:
            continue

        generations = _collect_generations_for_master_key(tails, master_key)
        candidates.append(_LoadCandidate(master_key=master_key, generations=generations))

    return candidates


def _select_best_generation_candidate(
    candidates: list[_LoadCandidate],
) -> tuple[_GenerationInfo, bytes] | None:
    """
    Select the newest recoverable generation across all candidates.
    """
    best_info: _GenerationInfo | None = None
    best_master_key: bytes | None = None

    for candidate in candidates:
        info = _latest_recoverable_generation(candidate.generations)
        if info is None:
            continue
        if best_info is None or info.container_generation > best_info.container_generation:
            best_info = info
            best_master_key = candidate.master_key

    if best_info is None or best_master_key is None:
        return None
    return best_info, best_master_key


def _build_state_from_generation(
    generation: _GenerationInfo, master_key: bytes
) -> ContainerState:
    """
    Decode one generation and convert it into runtime container state.
    """
    k = generation.container_threshold
    n = generation.shard_total
    available = sorted(generation.shards)[:k]

    zip_data = payload.decode(
        [generation.shards[i] for i in available], available, master_key, k, n
    )
    carriers = [
        (generation.carrier_map[i], i) for i in sorted(generation.carrier_map)
    ]

    return ContainerState(
        master_key=master_key,
        container_uuid=generation.container_uuid,
        container_generation=generation.container_generation,
        container_threshold=k,
        shard_total=n,
        carriers=carriers,
        zip_data=zip_data,
    )


def init(directory: Path, password: str, container_threshold: int) -> None:
    """
    Create a new encrypted container across JPEG carriers.

    Builds an empty ZIP payload, encrypts and splits it into shards,
    then appends key material, metadata, and shard data to each JPEG.
    """
    carriers = scan_jpeg_files(directory)

    if not carriers:
        raise NoCarriersError("No JPEG files found in the directory.")

    n = len(carriers)

    if container_threshold < 1:
        raise ValueError("Threshold must be at least 1.")

    if container_threshold > n:
        raise NotEnoughCarriersError(
            f"Threshold ({container_threshold}) exceeds the number of JPEG files ({n})."
        )

    for path in carriers:
        if has_tail(path):
            raise ContainerExistsError(
                f"'{path.name}' already has a jpegfs tail. "
                "Use 'wipe' to remove the existing container first."
            )

    master_key = crypto.random_bytes(_MASTER_KEY_SIZE)
    container_uuid = crypto.random_bytes(_CONTAINER_UUID_SIZE)
    container_generation = 1

    empty_zip = payload.create_empty_zip()
    shards = payload.encode(empty_zip, master_key, container_threshold, n)

    updates: list[tuple[Path, bytes]] = []
    for i, (path, shard) in enumerate(zip(carriers, shards)):
        sm = shard_metadata.ShardMetadata(
            container_uuid=container_uuid,
            container_generation=container_generation,
            container_threshold=container_threshold,
            shard_index=i,
            shard_total=n,
        )
        updates.append((path, _build_tail(password, master_key, sm, shard)))
    _rewrite_carrier_tails(updates)


def load(directory: Path, password: str) -> ContainerState:
    """
    Load the newest recoverable container from a directory.

    Scans carrier tails, groups valid shards by UUID and generation,
    and reconstructs the latest generation that has enough shards.
    """
    with_tails = [p for p in scan_jpeg_files(directory) if has_tail(p)]

    if not with_tails:
        raise ContainerNotFoundError("No jpegfs container found in the directory.")

    tails = {path: jpeg.read_tail(path) for path in with_tails}
    candidates = _collect_load_candidates(tails, password)
    if not candidates:
        raise InvalidPasswordError("Invalid password or corrupted data.")

    selected = _select_best_generation_candidate(candidates)
    if selected is None:
        raise InsufficientShardsError("Not enough shards to reconstruct the container.")

    best_generation, best_master_key = selected
    return _build_state_from_generation(best_generation, best_master_key)


def store(state: ContainerState, new_zip_data: bytes, password: str) -> None:
    """
    Persist updated ZIP data as a new container generation.

    Encrypts the payload, creates fresh shards and metadata,
    then rewrites all current carrier tails atomically.
    """
    new_generation = state.container_generation + 1
    new_shards = payload.encode(
        new_zip_data, state.master_key, state.container_threshold, state.shard_total
    )

    updates: list[tuple[Path, bytes]] = []
    for path, shard_index in state.carriers:
        sm = shard_metadata.ShardMetadata(
            container_uuid=state.container_uuid,
            container_generation=new_generation,
            container_threshold=state.container_threshold,
            shard_index=shard_index,
            shard_total=state.shard_total,
        )
        updates.append(
            (path, _build_tail(password, state.master_key, sm, new_shards[shard_index]))
        )
    _rewrite_carrier_tails(updates)


def put_file(directory: Path, password: str, name: str, content: bytes) -> None:
    """
    Add a new file to an existing container.

    Loads the current container, inserts the file into the ZIP payload,
    and stores the resulting payload as the next generation.
    """
    state = load(directory, password)
    new_zip = payload.zip_add_file(state.zip_data, name, content)
    store(state, new_zip, password)


def get_file(directory: Path, password: str, name: str) -> bytes:
    """
    Read one file from an existing container.

    Loads and decrypts the container, validates the requested name,
    and returns the stored file contents as bytes.
    """
    state = load(directory, password)
    return payload.zip_get_file(state.zip_data, name)


def del_file(directory: Path, password: str, name: str) -> None:
    """
    Remove one file from an existing container.

    Loads the current payload, deletes the named ZIP entry,
    and writes the updated payload back to the carriers.
    """
    state = load(directory, password)
    new_zip = payload.zip_delete_file(state.zip_data, name)
    store(state, new_zip, password)


def change_password(directory: Path, old_password: str, new_password: str) -> None:
    """
    Change the password protecting carrier key material.

    Loads the container with the old password and rewrites only
    the encrypted master-key blocks using the new password.
    """
    state = load(directory, old_password)

    updates: list[tuple[Path, bytes]] = []
    for path, _ in state.carriers:
        tail = jpeg.read_tail(path)
        shard_meta_and_payload = tail[key_material.SIZE:]
        new_km = key_material.KeyMaterial.create(new_password, state.master_key)
        updates.append((path, new_km.to_bytes() + shard_meta_and_payload))
    _rewrite_carrier_tails(updates)


def repair(directory: Path, password: str) -> tuple[int, int, int]:
    """
    Rebuild the container across all JPEG files in the directory.

    Uses the current recoverable payload to create a fresh generation,
    including new clean carriers and restoring missing redundancy.
    """
    state = load(directory, password)
    all_jpegs = scan_jpeg_files(directory)
    new_n = len(all_jpegs)

    if new_n < state.container_threshold:
        needed = state.container_threshold - new_n
        raise NotEnoughCarriersError(
            f"Not enough JPEG files. Add {needed} more JPEG file(s) to the directory."
        )

    new_generation = state.container_generation + 1
    new_shards = payload.encode(state.zip_data, state.master_key, state.container_threshold, new_n)

    updates: list[tuple[Path, bytes]] = []
    for i, path in enumerate(all_jpegs):
        sm = shard_metadata.ShardMetadata(
            container_uuid=state.container_uuid,
            container_generation=new_generation,
            container_threshold=state.container_threshold,
            shard_index=i,
            shard_total=new_n,
        )
        updates.append((path, _build_tail(password, state.master_key, sm, new_shards[i])))
    _rewrite_carrier_tails(updates)
    return len(state.carriers), state.shard_total, new_n


def wipe(directory: Path, password: str) -> int:
    """
    Remove jpegfs tails from the current recoverable generation.

    Clears appended container data only from carriers that belong
    to the loaded generation, leaving unrelated JPEG files untouched.
    """
    state = load(directory, password)
    carriers = [path for path, _ in state.carriers]

    _rewrite_carrier_tails([(path, b"") for path in carriers])
    return len(carriers)
