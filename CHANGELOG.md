# Changelog

## [0.1.20] - 2026-06-28

- Added comprehensive docstrings for public modules, functions, and methods across the project. Improved overall code documentation and developer experience.

## [0.1.19] - 2026-06-28

- Added `smoke tests` covering the complete container lifecycle, including initialization, file operations, password changes, recovery, and wipe.

## [0.1.18] - 2026-06-23

- Fixed `init` atomicity. Previously, carrier JPEG files were updated one at a time, leaving the container partially initialized if the process was interrupted. The operation now follows the same two-phase write strategy as `store()`: all temporary files are written and fsynced first, then atomically replace the originals, followed by a single directory fsync.
- Fixed `wipe` atomicity. Previously, carrier JPEG files were cleaned one at a time, leaving the container partially wiped if the process was interrupted. The operation now follows the same two-phase write strategy as `store()`.
- Fixed `change_password()` to operate only on carriers belonging to the current recoverable container generation. Previously, it could process stale, foreign, or corrupted container data present in the same directory.
- Added file-name validation in `payload.py`. ZIP operations now reject invalid file names, including empty names, path separators, `.` and `..`, ASCII control characters, and names whose UTF-8 encoding exceeds 255 bytes.

## [0.1.17] - 2026-06-21

- Fixed a critical data-corruption bug in `jpeg.py`. The previous `_eoi_end` implementation searched for the last `\xff\xd9` sequence, which could appear inside the encrypted tail and cause incorrect file splitting. Replaced it with a structured JPEG parser that reliably locates the actual EOI marker.
- Added the `repair` command. Reconstructs the container from available shards and redistributes it across all JPEG files in the directory. Each file receives exactly one shard, newly added files are included automatically, and the generation number is incremented. Fails if the number of JPEG files is below the configured threshold.


## [0.1.16] - 2026-06-21

- Split the `get` command into two: `get <name> [--as <output>]` extracts a file to the current directory, and `read <name>` writes the file content to stdout.
- Split the `put` command into two: `put <file> [--as <name>]` adds a file from disk, and `write --as <name>` reads content from stdin. The `--stdin` flag is removed.
- Added the `del <name>` command. Removes a file from the container and rewrites all carrier JPEG files with an incremented generation.
- Added the `passwd` command. Re-encrypts the key material block on every carrier JPEG using the new password. The shard payload and metadata are not rebuilt.

## [0.1.15] - 2026-06-21

- Fixed a bug in the `list` command where the last file row and the totals line were printed twice due to leftover code from a previous edit.

## [0.1.14] - 2026-06-21

- Removed the `check` command. Its functionality — container UUID, generation, threshold, and shard availability — is now displayed at the top of the `ls`/`list` output, along with the total container size.

## [0.1.13] - 2026-06-20

- Added the `ls` and `list` commands. Lists all files stored in the container in a formatted table showing the file name, uncompressed size, and last modified timestamp.

## [0.1.12] - 2026-06-20

- Added the `put` command. Supports importing files under their original name, a custom name (`--as`), or from `stdin` (`--stdin --as <name>`).
- Improved container update atomicity. Temporary files are now fully written and synchronized before any originals are replaced, preventing partially updated container generations if the process is interrupted.

## [0.1.11] - 2026-06-20

- Added the `wipe` command. Removes all appended data from every participating JPEG file in the directory, permanently destroying the container. Requires `--yes` to confirm and a valid password to authorize the operation.

## [0.1.10] - 2026-06-20

- Fixed a bug in the `init` command where the `zfec` encoder received a raw bytes object instead of a list of equally-sized input blocks, causing a precondition error when creating new containers.

## [0.1.9] - 2026-06-20

- Replaced the default argparse help output with a custom help text. Running `jpegfs`, `jpegfs -h`, or `jpegfs --help` now displays a full project description and a detailed list of all commands and their options. Removed the `help` subcommand.

## [0.1.8] - 2026-06-20

- Removed `from __future__ import annotations` from all modules. Since the project requires Python 3.12 or later, forward-reference annotations are supported natively. Replaced `TYPE_CHECKING` guards in `commands.py` with a direct `import argparse`.

## [0.1.7] - 2026-06-20

- Added the `help` command with a full project description and a detailed overview of all available commands and their options.

## [0.1.6] - 2026-06-20

- Created the initial project structure and module layout (`errors`, `crypto`, `jpeg`, `key_material`, `shard_metadata`, `payload`, `container`, `commands`, `cli`). Added the `init` command, which initializes a new encrypted container distributed across JPEG files in a directory. Added project overview, storage format specification, and container design documentation to the `README`.
