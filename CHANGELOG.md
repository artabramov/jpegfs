# Changelog

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
