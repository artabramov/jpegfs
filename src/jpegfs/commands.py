import argparse
import getpass
import sys
from pathlib import Path

from . import container
from .errors import JpegFsError

_HELP_TEXT = """\
jpegfs — encrypted file container distributed across JPEG photos.

User files are encrypted with a randomly generated master key and split into
redundant shards using erasure coding. The shards are appended to ordinary
JPEG files after the EOI marker. The images themselves remain valid and
visually unchanged. With the correct password, files can be added, extracted,
or deleted from the container at any time.

The container remains operational even if some JPEG files are lost, as long as
the number of available shards meets the configured threshold. If redundancy
is reduced, it can be restored with the repair command.

All commands accept --dir (container directory, default: current directory)
and --password-file (read password from file instead of interactive prompt).

Commands:

  init --threshold K
      Create a new container. K is the minimum number of JPEG files required
      to reconstruct the container. Fails if the directory already contains
      a jpegfs container.

  check
      Display container information (UUID, generation, threshold, shard count,
      size) and verify integrity. Checks that enough shards are present, the
      container can be reconstructed and decrypted, and the ZIP archive is valid.

  repair
      Restore full shard redundancy. Reconstructs the container from available
      shards and redistributes it across all JPEG files, including any new
      files added to the directory. Fails if there are not enough clean JPEG
      files to fill the required number of shards.

  wipe --yes
      Permanently destroy the container by removing all appended data from
      every JPEG file. The --yes flag is mandatory.

  passwd
      Change the container password. Only the key material is re-encrypted;
      the payload is not rebuilt.

  ls, list
      List files stored in the container.

  put <file> [--as <name>]
  put --stdin --as <name>
      Add a file to the container. Use --as to store it under a different name.
      Use --stdin to read the file content from standard input.

  get <name> [--as <output>]
  get <name> --stdout
      Extract a file from the container. Use --as to save it under a different
      name. Use --stdout to write the content to standard output.

  del <name>
      Delete a file from the container.
"""


def cmd_help(args: argparse.Namespace) -> None:
    print(_HELP_TEXT, end="")


def _read_password(args: argparse.Namespace, confirm: bool = False) -> str:
    if getattr(args, "password_file", None):
        try:
            with open(args.password_file, encoding="utf-8") as f:
                return f.readline().rstrip("\r\n")
        except OSError as e:
            print(f"Error reading password file: {e}", file=sys.stderr)
            sys.exit(1)

    password = getpass.getpass("Password: ")
    if confirm:
        if getpass.getpass("Confirm password: ") != password:
            print("Error: passwords do not match.", file=sys.stderr)
            sys.exit(1)
    return password


def cmd_wipe(args: argparse.Namespace) -> None:
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    password = _read_password(args)

    try:
        count = container.wipe(directory, password)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Container wiped: {count} file(s) cleared.")


def cmd_init(args: argparse.Namespace) -> None:
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    password = _read_password(args, confirm=True)

    try:
        container.init(directory, password, args.threshold)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Container initialized in '{directory}'.")
