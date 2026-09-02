from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TASK_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = TASK_ROOT / "scripts/extend.py"
DEFAULT_SNAPSHOT_DIR = TASK_ROOT / "results"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the clean well-but-not-ultra PseudoDojo extension controller periodically. "
            "Cycles are synchronous, so controller invocations never overlap."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Submit WorkChains. Without this flag every cycle is a dry run.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one controller cycle and exit instead of monitoring continuously.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=positive_float,
        default=15.0,
        help="Minutes to wait after one cycle finishes before starting the next (default: 15).",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Exit if a controller cycle fails. By default the monitor retries next cycle.",
    )
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--cif-dir", type=Path)
    parser.add_argument("--source-db", default="Goldilocks_scf_K_mesh_convergence_nospin")
    parser.add_argument("--batch-size", type=positive_int, default=50)
    parser.add_argument("--points-per-source", type=positive_int, default=3)
    parser.add_argument("--max-new-workchains", type=positive_int, default=50)
    parser.add_argument("--max-active", type=positive_int, default=50)
    parser.add_argument("--cleanup-limit", type=non_negative_int, default=0)
    parser.add_argument("--code-label", default="qe-7.5-pw-admin@scarf")
    parser.add_argument("--pseudo-family-label", default="PseudoDojo/0.4/PBEsol/SR/standard/upf")
    parser.add_argument("--group-label", default="goldilocks/qe-scf/nospin/pseudodojo")
    parser.add_argument("--degauss-ry", type=float, default=0.01)
    parser.add_argument("--num-machines", type=positive_int, default=1)
    parser.add_argument("--num-mpiprocs-per-machine", type=positive_int, default=32)
    parser.add_argument("--max-wallclock-seconds", type=positive_int, default=7200)
    return parser.parse_args(argv)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_controller_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-u",
        str(CONTROLLER),
        "--snapshot-dir",
        str(args.snapshot_dir),
        "--source-db",
        args.source_db,
        "--batch-size",
        str(args.batch_size),
        "--points-per-source",
        str(args.points_per_source),
        "--max-new-workchains",
        str(args.max_new_workchains),
        "--max-active",
        str(args.max_active),
        "--cleanup-limit",
        str(args.cleanup_limit),
        "--code-label",
        args.code_label,
        "--pseudo-family-label",
        args.pseudo_family_label,
        "--group-label",
        args.group_label,
        "--degauss-ry",
        str(args.degauss_ry),
        "--num-machines",
        str(args.num_machines),
        "--num-mpiprocs-per-machine",
        str(args.num_mpiprocs_per_machine),
        "--max-wallclock-seconds",
        str(args.max_wallclock_seconds),
    ]
    if args.cif_dir is not None:
        command.extend(["--cif-dir", str(args.cif_dir)])
    if args.execute:
        command.append("--execute")
    return command


def run_monitor(
    args: argparse.Namespace,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = datetime.now,
) -> int:
    command = build_controller_command(args)
    cycle = 0

    while True:
        cycle += 1
        started = now()
        mode = "EXECUTE" if args.execute else "DRY RUN"
        print(f"\n[{started.astimezone().isoformat(timespec='seconds')}] cycle={cycle} mode={mode}", flush=True)
        completed = runner(command, cwd=REPO_ROOT, check=False)
        return_code = int(completed.returncode)
        finished = now()
        print(
            f"[{finished.astimezone().isoformat(timespec='seconds')}] cycle={cycle} controller_exit={return_code}",
            flush=True,
        )

        if args.once or (return_code != 0 and args.stop_on_error):
            return return_code

        next_check = finished + timedelta(minutes=args.interval_minutes)
        if return_code != 0:
            print("controller failed; retrying at the next scheduled cycle", flush=True)
        print(
            f"next check: {next_check.astimezone().isoformat(timespec='seconds')} "
            f"(in {args.interval_minutes:g} minutes; Ctrl-C to stop)",
            flush=True,
        )
        sleeper(args.interval_minutes * 60)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_monitor(args)
    except KeyboardInterrupt:
        print("\nmonitor stopped by user", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
