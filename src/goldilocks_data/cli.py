from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Command line entry point for reusable Goldilocks data utilities."""

    parser = argparse.ArgumentParser(prog="goldilocks-data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cleanup = subparsers.add_parser("cleanup-qe-scf", help="Cleanup finished QE SCF remote folders.")
    cleanup.add_argument("--group-label", required=True)
    cleanup.add_argument("--limit", type=int)
    cleanup.add_argument("--execute", action="store_true", help="Actually delete files. Default is dry-run.")

    publish = subparsers.add_parser("publish", help="Validate a dataset deposit and create a PSDI draft.")
    publish.add_argument("--deposit-dir", type=Path, required=True)
    publish.add_argument("--community", default="data-to-knowledge")
    publish.add_argument("--token-file", type=Path, help="Token file with mode 600 or stricter.")
    publish.add_argument(
        "--confirm-upload",
        action="store_true",
        help="Create a real draft on PSDI. Without it the deposit is only validated.",
    )

    args = parser.parse_args(argv)
    if args.command == "cleanup-qe-scf":
        from goldilocks_data.aiida.cleanup import cleanup_finished

        failures = cleanup_finished(args.group_label, dry_run=not args.execute, limit=args.limit)
        print(f"cleanup failures: {len(failures)}")
        if not failures.empty:
            print(failures.to_string(index=False))
        return 0
    if args.command == "publish":
        return _publish(args)
    return 1


def _publish(args: argparse.Namespace) -> int:
    """Validate a deposit, and create a draft only when explicitly confirmed."""

    from goldilocks_data.publish import create_deposit, load_deposit, read_token

    deposit = load_deposit(args.deposit_dir, community=args.community)
    print(f"deposit:   {deposit.directory}")
    if deposit.record is None:
        print("dataset:   no dataset.json; schema is described in README.md only")
    else:
        record = deposit.record
        print(f"dataset:   {record['dataset']} {record['version']}  rows={record['rows']}")
    print(f"community: {deposit.community}")
    print("files:")
    for name in sorted(deposit.files):
        print(f"  {name}  ({deposit.files[name].stat().st_size} bytes)")

    if not args.confirm_upload:
        # Validation is the whole job without --confirm-upload; nothing is sent.
        print("\nvalidated. re-run with --token-file and --confirm-upload to create a PSDI draft.")
        return 0

    if args.token_file is None:
        raise SystemExit("--confirm-upload requires --token-file")

    draft_id = create_deposit(deposit, token=read_token(args.token_file))
    print(f"\ndraft created: {draft_id}")
    print("it is NOT submitted. review it on the PSDI website and submit it there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
