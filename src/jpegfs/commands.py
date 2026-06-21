import argparse
import getpass
import sys
import uuid as _uuid
from pathlib import Path

from . import container, payload
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

  list, ls
      Display container information (UUID, generation, threshold, available
      shards) followed by a table of files stored in the container.      

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


def cmd_ls(args: argparse.Namespace) -> None:
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    password = _read_password(args)

    try:
        state = container.load(directory, password)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    files = payload.zip_list_files_info(state.zip_data)

    uuid_str = str(_uuid.UUID(bytes=state.container_uuid))
    total_size = sum(f.size for f in files)

    print(f"UUID:       {uuid_str}")
    print(f"Generation: {state.generation}")
    print(f"Threshold:  {state.threshold}/{state.shard_total}")
    print(f"Shards:     {len(state.carriers)}/{state.shard_total} available")
    print(f"Size:       {_fmt_size(total_size)}")
    print()

    if not files:
        print("No files.")
        return

    name_w = max((len(f.name) for f in files), default=4)
    name_w = max(name_w, 4)
    print(f"{'name':<{name_w}}  {'size':>10}  modified")
    print(f"{'-' * name_w}  {'-' * 10}  -------------------")
    for f in files:
        y, mo, d, h, mi, s = f.modified
        modified = f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}"
        print(f"{f.name:<{name_w}}  {_fmt_size(f.size):>10}  {modified}")

    print()
    print(f"{len(files)} file(s)  {_fmt_size(total_size)} total")
    modified = f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}"
    print(f"{f.name:<{name_w}}  {_fmt_size(f.size):>10}  {modified}")

    print()
    print(f"{len(files)} file(s)  {_fmt_size(total_size)} total")


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def cmd_put(args: argparse.Namespace) -> None:
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    if args.stdin:
        if not args.as_name:
            print("Error: --as is required when using --stdin.", file=sys.stderr)
            sys.exit(1)
        name = args.as_name
        content = sys.stdin.buffer.read()
    else:
        if not args.file:
            print("Error: specify a source file or use --stdin.", file=sys.stderr)
            sys.exit(1)
        source = Path(args.file)
        if not source.is_file():
            print(f"Error: '{source}' is not a file.", file=sys.stderr)
            sys.exit(1)
        name = args.as_name if args.as_name else source.name
        try:
            content = source.read_bytes()
        except OSError as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)

    password = _read_password(args)

    try:
        container.put_file(directory, password, name, content)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"'{name}' added to the container.")


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
