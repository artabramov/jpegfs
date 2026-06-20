import argparse
import getpass
import sys
from pathlib import Path

from . import container
from .errors import JpegFsError


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
