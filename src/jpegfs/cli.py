import argparse
import sys
from importlib.metadata import PackageNotFoundError, version

from .commands import cmd_help, cmd_init


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

    args = parser.parse_args()

    if args.help or not hasattr(args, "func"):
        cmd_help(args)
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
