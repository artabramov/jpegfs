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
      Restore full shard redundancy. Reconstructs the container from the
      available shards and redistributes it across every JPEG file in the
      directory, including any new files added since the last write. After
      repair, every JPEG file in the directory carries exactly one shard.
      Fails if there are not enough JPEG files to satisfy the threshold.

  wipe --yes
      Permanently destroy the container by removing all appended data from
      every JPEG file. The --yes flag is mandatory.

  passwd
      Change the container password. Only the key material is re-encrypted;
      the payload is not rebuilt.

  put <file> [--as <name>]
      Add a file to the container. Use --as to store it under a different name.

  write --as <name>
      Read file content from stdin and store it in the container under <name>.

  get <name> [--as <output>]
      Extract a file from the container to the current directory. Use --as to
      save it under a different name.

  read <name>
      Extract a file from the container and write its content to stdout.

  del <name>
      Delete a file from the container.
"""


def cmd_help(args: argparse.Namespace) -> None:
    """
    Print the built-in jpegfs help text.

    Outputs the full command overview directly to stdout
    without invoking argparse's generated help formatter.
    """
    print(_HELP_TEXT, end="")


def _read_password(args: argparse.Namespace, confirm: bool = False,
                   prompt: str = "Password: ") -> str:
    """
    Read a password from a file or from the terminal.

    When confirmation is requested, prompts twice and exits
    if the entered passwords do not match.
    """
    if getattr(args, "password_file", None):
        try:
            with open(args.password_file, encoding="utf-8") as f:
                return f.readline().rstrip("\r\n")
        except OSError as e:
            print(f"Error reading password file: {e}", file=sys.stderr)
            sys.exit(1)

    password = getpass.getpass(prompt)
    if confirm:
        if getpass.getpass(f"Confirm {prompt.lower()}") != password:
            print("Error: passwords do not match.", file=sys.stderr)
            sys.exit(1)
    return password


def cmd_ls(args: argparse.Namespace) -> None:
    """
    List files stored in an encrypted jpegfs container.

    Loads the container, prints container metadata, and displays
    stored file names, sizes, modification times, and total size.
    """
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


def _fmt_size(n: int) -> str:
    """
    Format a byte count as a readable size string.

    Uses binary scaling through KB, MB, GB, and TB,
    while keeping plain bytes unrounded.
    """
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def cmd_put(args: argparse.Namespace) -> None:
    """
    Add a local file to the encrypted container.

    Reads the source file from disk, optionally stores it under
    a different name, and persists the updated container state.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
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


def cmd_write(args: argparse.Namespace) -> None:
    """
    Store stdin data as a file in the encrypted container.

    Reads raw bytes from standard input and writes them under
    the required container file name.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    name = args.as_name
    content = sys.stdin.buffer.read()
    password = _read_password(args)

    try:
        container.put_file(directory, password, name, content)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"'{name}' added to the container.")


def cmd_get(args: argparse.Namespace) -> None:
    """
    Extract a container file to the local filesystem.

    Loads the requested file from the encrypted container
    and writes it to the selected output path.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    output_name = args.as_name if args.as_name else args.name
    output_path = Path(output_name)
    password = _read_password(args)

    try:
        content = container.get_file(directory, password, args.name)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        output_path.write_bytes(content)
    except OSError as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"'{args.name}' extracted to '{output_path}'.")


def cmd_read(args: argparse.Namespace) -> None:
    """
    Write a stored container file to stdout.

    Retrieves the requested file from the encrypted container
    and streams its raw bytes to standard output.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    password = _read_password(args)

    try:
        content = container.get_file(directory, password, args.name)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.buffer.write(content)


def cmd_del(args: argparse.Namespace) -> None:
    """
    Delete a file from the encrypted container.

    Loads the current container state, removes the requested entry,
    and saves the updated payload back to the carriers.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    password = _read_password(args)

    try:
        container.del_file(directory, password, args.name)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"'{args.name}' deleted from the container.")


def cmd_passwd(args: argparse.Namespace) -> None:
    """
    Change the password for an existing container.

    Verifies the current password and re-encrypts carrier key
    material with the newly entered password.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    old_password = _read_password(args, prompt="Current password: ")
    new_password = _read_password(args, confirm=True, prompt="New password: ")

    try:
        container.change_password(directory, old_password, new_password)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Password changed successfully.")


def cmd_wipe(args: argparse.Namespace) -> None:
    """
    Remove jpegfs data from the current container generation.

    Loads the recoverable container and clears appended jpegfs tails
    from the carrier files that belong to it.
    """
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


def cmd_repair(args: argparse.Namespace) -> None:
    """
    Restore full shard redundancy for the container.

    Rebuilds the current payload across all JPEG files in the directory
    and reports how the available shard set changed.
    """
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    password = _read_password(args)

    try:
        old_available, old_total, new_total = container.repair(directory, password)
    except (JpegFsError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if new_total != old_total or old_available < old_total:
        print(
            f"Container repaired: {old_available}/{old_total} → "
            f"{new_total}/{new_total} shards available."
        )
    else:
        print(f"Container repaired: {new_total}/{new_total} shards available (no change).")


def cmd_init(args: argparse.Namespace) -> None:
    """
    Initialize a new jpegfs container in a JPEG directory.

    Reads and confirms the password, validates the target directory,
    and creates encrypted shards across the available carrier files.
    """
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
