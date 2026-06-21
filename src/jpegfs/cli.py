import argparse
import sys
from importlib.metadata import PackageNotFoundError, version

from .commands import (
    cmd_del, cmd_get, cmd_help, cmd_init, cmd_ls,
    cmd_passwd, cmd_put, cmd_read, cmd_repair, cmd_wipe, cmd_write,
)


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

    p_repair = subs.add_parser("repair", help="Restore full shard redundancy.")
    _add_common_args(p_repair)
    p_repair.set_defaults(func=cmd_repair)

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
    p_put.add_argument("file", metavar="FILE", help="Source file to add.")
    p_put.add_argument("--as", dest="as_name", metavar="NAME",
                       help="Store under a different name.")
    p_put.set_defaults(func=cmd_put)

    p_write = subs.add_parser("write", help="Add a file to the container from stdin.")
    _add_common_args(p_write)
    p_write.add_argument("--as", dest="as_name", metavar="NAME", required=True,
                         help="Name to store the file under.")
    p_write.set_defaults(func=cmd_write)

    for alias in ("ls", "list"):
        p_ls = subs.add_parser(alias, help="List files stored in the container.")
        _add_common_args(p_ls)
        p_ls.set_defaults(func=cmd_ls)

    p_get = subs.add_parser("get", help="Extract a file from the container.")
    _add_common_args(p_get)
    p_get.add_argument("name", metavar="NAME", help="Name of the file in the container.")
    p_get.add_argument("--as", dest="as_name", metavar="OUTPUT",
                       help="Save under a different name.")
    p_get.set_defaults(func=cmd_get)

    p_read = subs.add_parser("read", help="Extract a file from the container to stdout.")
    _add_common_args(p_read)
    p_read.add_argument("name", metavar="NAME", help="Name of the file in the container.")
    p_read.set_defaults(func=cmd_read)

    p_del = subs.add_parser("del", help="Delete a file from the container.")
    _add_common_args(p_del)
    p_del.add_argument("name", metavar="NAME", help="Name of the file to delete.")
    p_del.set_defaults(func=cmd_del)

    p_passwd = subs.add_parser("passwd", help="Change the container password.")
    _add_common_args(p_passwd)
    p_passwd.set_defaults(func=cmd_passwd)

    args = parser.parse_args()

    if args.help or not hasattr(args, "func"):
        cmd_help(args)
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
