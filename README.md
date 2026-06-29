# jpegfs — encrypted file container distributed across JPEG images

The project is a file container that uses a collection of JPEG files as a distributed carrier for encrypted data. From the user's perspective, it provides the interface of a simple virtual filesystem with a flat structure. The core idea is not to hide a single file inside a single image, but to **create an encrypted container distributed across multiple images.**

User files are encrypted with a randomly generated master key and split into redundant shards using erasure coding. A set of JPEG files is then selected, and additional data is appended to each file after the JPEG `EOI` (End of Image) marker. This data includes cryptographic material, encrypted shard metadata, and one of the data shards. With the correct password, files can be added to, extracted from, read from, and written to the container directly, including through standard input/output streams.

**The container remains recoverable even if some of the JPEG files are lost.** As long as a sufficient number of shards remain available, the container payload can be reconstructed and any lost redundancy can be regenerated.

The project is **not a steganographic system in the traditional sense.** The additional data can be easily detected by examining the contents of a file beyond the JPEG `EOI`. However, the images themselves remain unchanged, and the appended data appears as a cryptographically random sequence of bytes. It contains no plaintext information and does not reveal its purpose or contents without knowledge of the correct password. Even when such data is discovered, the data appears indistinguishable from random noise.

[![PyPI](https://img.shields.io/pypi/v/jpegfs)](https://pypi.org/project/jpegfs/) [![tests](https://github.com/artabramov/jpegfs/actions/workflows/tests.yml/badge.svg)](https://github.com/artabramov/jpegfs/actions/workflows/tests.yml) [![license](https://img.shields.io/badge/license-GPL--3.0-2f81f7)](./LICENSE)


## Threat model

The primary goal of jpegfs is to protect data at rest and provide
recoverability in the event of carrier file loss.

What is protected:

- **Loss of some carrier JPEG files.** As long as at least the required
  number of shards remains available, the container can be reconstructed
  and missing redundancy can be regenerated.

- **Unauthorized access to carrier files.** Without the correct password,
  an attacker cannot recover the master key, decrypt the container
  contents, or determine whether the appended data represents a valid
  jpegfs container or arbitrary encrypted bytes.

- **Disclosure of individual carrier files.** A single JPEG file contains
  only one shard of the encrypted payload and does not provide access to
  the stored data on its own.

- **Disclosure of all carrier files.** An attacker may recover the
  encrypted container payload but cannot decrypt it without the password.

What is not protected:

- **Compromised host system.** An attacker with access to the running
  process, process memory, keyboard input, or decrypted data can obtain
  information regardless of the container format.

- **Weak passwords.** The security of the encrypted master key ultimately
  depends on the strength of the password supplied by the user.

- **JPEG processing software.** Many image editors, optimizers,
  converters, cloud services, and social media platforms rewrite JPEG
  files and may remove any data appended after the JPEG EOI marker,
  permanently destroying container data stored in those files.

- **Memory disclosure.** During container operations, decrypted data,
  encryption keys, and shard material exist in process memory and may be
  exposed through swap files, hibernation files, crash dumps, or memory
  inspection.

- **jpegfs is not a steganographic system.** Additional data is appended
  after the JPEG EOI marker and can be detected by anyone inspecting the
  file structure. The project does not attempt to hide the presence of
  container data. This data is encrypted and appears indistinguishable
  from random bytes, preventing recovery of the container contents without
  the correct password.


## Quick start

Install jpegfs from PyPI:

```sh
pip install jpegfs
```

Display the command-line help:

```sh
jpegfs --help
```

Create a new container using JPEG files as carriers:

```sh
jpegfs init --threshold 3
```

Add a file to the container:

```sh
jpegfs put secret.pdf
```

List files stored in the container:

```sh
jpegfs list
```

Extract a file from the container:

```sh
jpegfs get secret.pdf
```


## Commands

All commands accept an optional `--dir` argument that specifies the directory containing the container JPEG files. If omitted, the current directory is used. All commands require a password.

`-h`, `--help` — display command-line help and usage information.

`init` — create a new container. Accepts `--threshold`. Generates a random `master_key`, creates a new `container_uuid`, sets `generation = 1`, and creates an empty ZIP archive. If the directory already contains at least one valid `jpegfs` shard, the command fails.

`list`, `ls` — display container information (`UUID`, `generation`, `threshold`, available shards) followed by a table of files stored in the container, including file name, uncompressed size, and last modified timestamp.

`repair` — restore full shard redundancy. Reconstructs the latest recoverable generation, increments the generation number, and redistributes the container across all JPEG files currently present in the directory (one shard per JPEG). If there are fewer JPEG files than the configured threshold, the command fails and reports how many additional JPEG files must be added.

`wipe --yes` — permanently destroy the container by removing all appended data from participating JPEG files (truncate files after the JPEG `EOI` marker `FF D9`). The `--yes` flag is mandatory.

`passwd` — change the container password. Only the `key material` blocks are re-encrypted. The ZIP archive and shard payloads are not rebuilt.

`put` — add a file to the container. The original filename is used by default (`jpegfs put file1.pdf`). A different name can be specified with `--as` (`jpegfs put file1.pdf --as secret.pdf`).

`write` — read file content from `stdin` and store it in the container under the specified name (`jpegfs write --as secret.pdf`).

`get <name> [--as <output>]` — extract a file from the container to the current directory. Use `--as` to save it under a different name.

`read <name>` — extract a file from the container and write its content to `stdout`.

`del` — delete a file from the container.


## Storage format

A JPEG file participating in the distributed container has the following structure:

```sh
 JPEG data   EOI     Key material   Shard metadata   Shard payload
 N bytes     FF D9   76 bytes       54 bytes         M bytes
 │           │       │              │                │
░░░░░░░░░░░░▓▓▓▓▓▓▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
```

All numeric fields are encoded using `big-endian` byte order. For example, the metadata structure can be serialized as:

```python
struct.pack(">16sIHHH", ...)
struct.unpack(">16sIHHH", data)
```

**JPEG data** — the original JPEG image data. The project does not modify this portion of the file, allowing the image to remain valid and visually unchanged.

**JPEG EOI** — marks the end of the JPEG image data. Any bytes appended after this marker are not part of the image itself and are ignored by standard JPEG decoders. As a result, additional data can be stored after the `EOI` marker without affecting the visual appearance of the image.

**Key material** — contains the encrypted container `master_key` and the parameters required to recover it from the user password. The `master_key` itself is generated randomly during container creation. Each JPEG file uses a unique `salt` and `key_nonce`, resulting in a different encrypted key block while still protecting the same `master_key`. This block always has a fixed size of 76 bytes:

```sh
salt                  16 bytes - random salt for password-based key derivation
key_nonce             12 bytes - random nonce used to encrypt the master key
encrypted_master_key  48 bytes - encrypted container master key
```

The 48-byte `encrypted_master_key` consists of a 32-byte encrypted `master_key` and a 16-byte `AEAD` authentication tag.

**Shard metadata** — contains the metadata required to reconstruct the container. Each JPEG file uses a unique `metadata_nonce`, causing the `encrypted_metadata` stored in different files to differ even when they belong to the same container. This block always has a fixed size of 54 bytes:

```sh
metadata_nonce      12 bytes - random nonce used to encrypt the metadata
encrypted_metadata  42 bytes - encrypted container metadata
```

The 42-byte `encrypted_metadata` consists of a 26-byte metadata structure and a 16-byte `AEAD` authentication tag. After decryption, the metadata structure contains the container identifier, generation number, and shard information required to reconstruct the container:

```sh
container_uuid       16 bytes - identifies the container (UUID)
container_generation  4 bytes - container generation number (uint32)
container_threshold   2 bytes - number of shards required for reconstruction
shard_index           2 bytes - index of the current shard
shard_total           2 bytes - total number of shards in the container
```

**Shard payload** — contains a single shard generated from the container contents. Internally, the container is represented as an uncompressed ZIP archive. The archive is encrypted with `master_key`, encoded into redundant shards using `zfec`, and stored as shard payloads. The ZIP format is chosen because it already stores file names and file metadata, eliminating the need for a separate file manifest inside the encrypted payload. The size of each shard payload is variable and depends on the size of the container and the selected erasure coding parameters.


## Container updates

When reading container data, shards are grouped by `container_uuid` and `container_generation`. The latest generation with at least `container_threshold` valid shards is selected for reconstruction.

Any operation that modifies files stored in the container requires rebuilding the container payload and rewriting the appended data in every participating JPEG file. Updates are performed by creating a new container generation and atomically replacing the original files rather than modifying them in place:

1. Read the current container.
2. Build a new container with `generation = old_generation + 1`.
3. Create a temporary file alongside each JPEG file (`image.jpg.tmp`).
4. Write the updated container data to each temporary file.
5. Call `fsync(tmp)` for each temporary file.
6. After all temporary files have been written successfully, replace the original files using `os.replace(tmp, original)`.
7. Call `fsync(directory)`.

Each container update creates a new `container_generation`. During reconstruction jpegfs selects the newest generation for which at least the required number of shards is available. Older generations may remain present in carrier files but are ignored.

Changing the password does not require rebuilding the ZIP archive or shard payloads. Only the `key material` block of each JPEG file is re-encrypted.


## Project structure

```sh
src/jpegfs/
├── __init__.py
├── __main__.py
├── cli.py             command-line interface and argument parsing
├── commands.py        console commands
├── container.py       container assembly and reconstruction logic
├── crypto.py          KDF, AEAD, and random byte generation
├── errors.py          custom exceptions
├── jpeg.py            EOI detection and tail read/write operations
├── key_material.py    76-byte key material format
├── payload.py         ZIP, encryption, and zfec encoding/decoding
└── shard_metadata.py  54-byte encrypted shard metadata format
```


## License

This project is licensed under the **GNU General Public License v3.0** (GPL-3.0). You are free to use, study, modify, and redistribute the software under the terms of the license.
