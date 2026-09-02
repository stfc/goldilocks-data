from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    """Command line entry point for reusable Goldilocks data utilities."""

    parser = argparse.ArgumentParser(prog="goldilocks-data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cleanup = subparsers.add_parser("cleanup-qe-scf", help="Cleanup finished QE SCF remote folders.")
    cleanup.add_argument("--group-label", required=True)
    cleanup.add_argument("--limit", type=int)
    cleanup.add_argument("--execute", action="store_true", help="Actually delete files. Default is dry-run.")

    args = parser.parse_args(argv)
    if args.command == "cleanup-qe-scf":
        from goldilocks_data.aiida.cleanup import cleanup_finished

        failures = cleanup_finished(args.group_label, dry_run=not args.execute, limit=args.limit)
        print(f"cleanup failures: {len(failures)}")
        if not failures.empty:
            print(failures.to_string(index=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
