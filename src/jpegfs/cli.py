import argparse

from importlib.metadata import version


def cmd_version(args):
    """Print the installed jpegfs package version."""
    print(version("jpegfs"))


def cmd_init(args):
    """
    Initialize a jpegfs storage directory.
    - Treat the given path as a directory containing ordinary JPEG photo files.
    - Validate that the directory exists or create it if the final CLI design allows that.
    - Scan JPEG carriers and create an internal jpegfs manifest.
    - The manifest should describe available carriers, stored files, chunk placement,
      checksums, encryption parameters, and format version.
    - Do not modify image pixels at this stage unless initialization requires reserving
      metadata space.
    - The command should be safe to run more than once.
    """
    print(f"Initializing storage: {args.path}")


def cmd_ls(args):
    """
    List files stored inside a jpegfs storage directory.
    - Load and validate the jpegfs manifest from the given storage directory.
    - Display logical files stored in the JPEG collection, not the carrier JPEG files.
    - Include at least file name, size, stored size, chunk count, and modification time.
    - Later versions may support JSON output for scripts.
    - The command must not extract or decrypt file contents unless required for metadata.
    """
    print(f"Listing files in: {args.path}")


def cmd_put(args):
    """
    Store a regular file inside a jpegfs storage directory.
    - Read the input file from disk.
    - Encrypt the file before embedding it into JPEG carriers.
    - Split encrypted data into chunks.
    - Select suitable JPEG carrier files and embed chunks into them.
    - Update the jpegfs manifest atomically after successful embedding.
    - Store enough metadata to reconstruct the file later: original name, size,
      checksum, chunk order, carrier mapping, encryption parameters, and timestamps.
    - Avoid overwriting an existing logical file unless an explicit overwrite flag exists.
    """
    print(f"Putting '{args.file}' into '{args.path}'")


def cmd_get(args):
    """
    Extract a stored logical file from a jpegfs storage directory.
    - Load the jpegfs manifest.
    - Locate all chunks belonging to the requested logical file.
    - Read chunks from JPEG carriers in the correct order.
    - Reassemble encrypted data.
    - Decrypt and verify the file checksum before writing output.
    - Write the file to the selected output path.
    - Refuse partial or corrupted extraction unless a future recovery mode is added.
    """
    print(f"Getting '{args.name}' from '{args.path}'")


def main():
    """Main CLI entry point for jpegfs."""
    parser = argparse.ArgumentParser(
        prog="jpegfs",
        description="Steganographic filesystem for JPEG photo collections.",
    )

    subparsers = parser.add_subparsers(dest="command")

    version_parser = subparsers.add_parser(
        "version",
        help="Show version",
    )
    version_parser.set_defaults(func=cmd_version)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize storage",
    )
    init_parser.add_argument("path")
    init_parser.set_defaults(func=cmd_init)

    ls_parser = subparsers.add_parser(
        "ls",
        help="List stored files",
    )
    ls_parser.add_argument("path")
    ls_parser.set_defaults(func=cmd_ls)

    put_parser = subparsers.add_parser(
        "put",
        help="Store file",
    )
    put_parser.add_argument("path")
    put_parser.add_argument("file")
    put_parser.set_defaults(func=cmd_put)

    get_parser = subparsers.add_parser(
        "get",
        help="Extract file",
    )
    get_parser.add_argument("path")
    get_parser.add_argument("name")
    get_parser.set_defaults(func=cmd_get)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)
