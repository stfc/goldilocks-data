from __future__ import annotations

import subprocess
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "campaigns/qe/kpoints/scripts/monitor.py"
SPEC = spec_from_file_location("extension_monitor", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
extension_monitor = module_from_spec(SPEC)
SPEC.loader.exec_module(extension_monitor)

build_controller_command = extension_monitor.build_controller_command
parse_args = extension_monitor.parse_args
run_monitor = extension_monitor.run_monitor


def test_safe_defaults_are_forwarded_to_controller() -> None:
    args = parse_args([])

    command = build_controller_command(args)

    assert command[1:8] == ["run", "--extra", "aiida", "--extra", "kmesh", "python", "-u"]
    assert command[8].endswith("campaigns/qe/kpoints/scripts/extend.py")
    assert command[command.index("--batch-size") + 1] == "50"
    assert command[command.index("--max-new-workchains") + 1] == "50"
    assert command[command.index("--max-active") + 1] == "50"
    assert command[command.index("--points-per-source") + 1] == "3"
    assert "--execute" not in command


def test_execute_flag_is_explicitly_forwarded() -> None:
    command = build_controller_command(parse_args(["--execute", "--cif-dir", "/data/cifs"]))

    assert command[-1] == "--execute"
    assert command[command.index("--cif-dir") + 1] == "/data/cifs"


def test_once_runs_exactly_one_cycle_without_sleeping() -> None:
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    return_code = run_monitor(
        parse_args(["--once"]),
        runner=runner,
        sleeper=sleeps.append,
        now=lambda: datetime(2026, 9, 2, 12, 0),
    )

    assert return_code == 0
    assert len(calls) == 1
    assert sleeps == []


def test_stop_on_error_exits_without_retrying() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess:
        calls.append(command)
        return subprocess.CompletedProcess(command, 7)

    return_code = run_monitor(
        parse_args(["--stop-on-error"]),
        runner=runner,
        sleeper=lambda _: None,
        now=lambda: datetime(2026, 9, 2, 12, 0),
    )

    assert return_code == 7
    assert len(calls) == 1
