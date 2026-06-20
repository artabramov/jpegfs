import argparse
import sys
from importlib.metadata import PackageNotFoundError, version

from .commands import cmd_help, cmd_init, cmd_put, cmd_wipe


def _version() -> str:
    try:
        return version("jpegfs")
    except PackageNotFoundError:
        return "unknown"


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        default=".",
        metavar="DIR",
        help="Directory with JPEG carrier files (default: current directory).",
    )
    parser.add_argument(
        "--password-file",
        metavar="FILE",
        help="Read password from file (first line, UTF-8).",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jpegfs",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help",
        action="store_true",
        default=False,
        help="Show this help message and exit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"jpegfs {_version()}",
    )

    subs = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_init = subs.add_parser("init", help="Create a new container.")
    _add_common_args(p_init)
    p_init.add_argument(
        "--threshold",
        type=int,
        required=True,
        metavar="K",
        help="Minimum number of JPEG files required to reconstruct the container.",
    )
    p_init.set_defaults(func=cmd_init)

    p_wipe = subs.add_parser("wipe", help="Permanently destroy the container.")
    _add_common_args(p_wipe)
    p_wipe.add_argument(
        "--yes",
        action="store_true",
        required=True,
        help="Confirm permanent destruction of the container.",
    )
    p_wipe.set_defaults(func=cmd_wipe)

    p_put = subs.add_parser("put", help="Add a file to the container.")
    _add_common_args(p_put)
    p_put.add_argument("file", nargs="?", metavar="FILE", help="Source file to add.")
    p_put.add_argument("--as", dest="as_name", metavar="NAME",
                       help="Store under a different name.")
    p_put.add_argument("--stdin", action="store_true",
                       help="Read file content from stdin.")
    p_put.set_defaults(func=cmd_put)

    args = parser.parse_args()

    if args.help or not hasattr(args, "func"):
        cmd_help(args)
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
