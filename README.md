# jpegfs

The project is a file container that uses a collection of JPEG files as a distributed carrier for encrypted data. From the user's perspective, it provides the interface of a simple virtual filesystem with a flat structure.

The core idea is not to hide a single file inside a single image, but to create an encrypted container distributed across multiple images.

User files are encrypted with a randomly generated master key and split into redundant shards using erasure coding. A set of JPEG files is then selected, and additional data is appended to each file after the JPEG `EOI` (End of Image) marker. This data includes cryptographic material, encrypted shard metadata, and one of the data shards. With the correct password, files can be added to, extracted from, read from, and written to the container directly, including through standard input/output streams.

The system is designed to remain operational even if some of the JPEG files are lost. As long as a sufficient number of shards remain available, the entire container can be reconstructed and any lost redundancy can be regenerated.

The project is not a steganographic system in the traditional sense. The additional data can be easily detected by examining the contents of a file beyond the JPEG `EOI`. However, the images themselves remain unchanged, and the appended data appears as a cryptographically random sequence of bytes. It contains no plaintext information and does not reveal its purpose or contents without knowledge of the correct password. Even when such data is discovered, it is not possible to determine whether it represents meaningful information, an encrypted container, or simply an arbitrary sequence of bytes.


## Commands

All commands accept an optional `--dir` argument that specifies the directory containing the container JPEG files. If omitted, the current directory is used. All commands require a password.

`help` — display command-line help and usage information.

`init` — create a new container. Accepts `--threshold`. Generates a random `master_key`, creates a new `container_uuid`, sets `generation = 1`, and creates an empty ZIP archive. If the directory already contains at least one valid `jpegfs` shard, the command fails.

`list`, `ls` — display container information (`UUID`, `generation`, `threshold`, available shards) followed by a table of files stored in the container, including file name, uncompressed size, and last modified timestamp.

`repair` — restore full shard redundancy. Locates all JPEG files containing valid shards, reconstructs the latest recoverable generation, decrypts the container, finds unused JPEG files without appended data, increments the generation number, and rebuilds the container using a new set of JPEG files. If there are not enough clean JPEG files available, the command fails and reports how many additional JPEG files must be added.

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

Changing the password does not require rebuilding the ZIP archive or shard payloads. Only the `key material` block of each JPEG file is re-encrypted.


## Project structure

```sh
src/jpegfs/
├── __init__.py
├── __main__.py
├── errors.py           custom exceptions
├── crypto.py           KDF, AEAD, and random byte generation
├── jpeg.py             EOI detection and tail read/write operations
├── key_material.py     76-byte key material format
├── shard_metadata.py   54-byte encrypted shard metadata format
├── payload.py          ZIP, encryption, and zfec encoding/decoding
├── container.py        container assembly and reconstruction logic
├── commands.py         init/check/repair/passwd/ls/put/get/del/wipe commands
└── cli.py              command-line interface and argument parsing
```
