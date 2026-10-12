"""Command-line entry point. Reports stay local and may contain private save IDs."""

import argparse
import json
import sys
from pathlib import Path

from .errors import ValidationError
from .refresh import describe, read_tree, refresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Validate and inspect one game save")
    inspect.add_argument("file", type=Path)
    inspect.add_argument(
        "--account-id",
        type=int,
        required=True,
        help="Steam userdata folder number or SteamID64; low 32 bits are used",
    )
    generate = sub.add_parser("refresh", help="Generate candidate slot-2 files without installing")
    generate.add_argument("--snapshot", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--account-id", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = describe(read_tree(args.file, args.account_id))
        else:
            result = refresh(args.snapshot, args.output, args.account_id)
        print(json.dumps(result, indent=2))
    except (ValidationError, OSError, KeyError, StopIteration, RecursionError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
