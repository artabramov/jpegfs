import argparse

from importlib.metadata import version


def cmd_version(args):
    print(version("jpegfs"))


def cmd_init(args):
    print(f"Initializing storage: {args.path}")


def cmd_ls(args):
    print(f"Listing files in: {args.path}")


def cmd_put(args):
    print(f"Putting '{args.file}' into '{args.path}'")


def cmd_get(args):
    print(f"Getting '{args.name}' from '{args.path}'")


def main():
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
