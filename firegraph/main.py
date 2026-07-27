"""
Main entry: runs firegraph workflow.
Source: sys.argv[1] (path or --text "code"), else project dir.
"""
import os
import sys

from run_firegraph import run_workflow


def _parse_input() -> tuple[str, bool, str]:
    """Parse argv: (source, is_path, output_dir). No argparse."""
    args = sys.argv[1:]
    source = None
    is_path = True
    output_dir = "firegraph-output"

    i = 0
    while i < len(args):
        if args[i] == "--text" and i + 1 < len(args):
            source = args[i + 1]
            is_path = False
            i += 2
        elif args[i] in ("-o", "--output") and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif not args[i].startswith("-"):
            source = args[i]
            i += 1
        else:
            i += 1

    # When installed via pip: default source = cwd (user's project), not package dir
    if source is None:
        source = os.getcwd()
    return source, is_path, output_dir


def main() -> None:
    """CLI entry point for firegraph."""
    source, is_path, output_dir = _parse_input()
    try:
        run_workflow(source, is_path=is_path, output_dir=output_dir)
    except (ValueError, FileNotFoundError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
