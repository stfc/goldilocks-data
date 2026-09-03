from __future__ import annotations

from pathlib import Path

import pytest

from goldilocks_data.cli import main


def test_publish_dry_run_validates_and_sends_nothing(tmp_path: Path, write_deposit, capsys) -> None:
    directory = write_deposit(tmp_path / "d")

    exit_code = main(["publish", "--deposit-dir", str(directory)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "goldilocks-mc3d-nospin-scf-kmesh v1  rows=2" in out
    assert "data-to-knowledge" in out
    assert "data.csv" in out
    assert "re-run with --token-file and --confirm-upload" in out


def test_publish_dry_run_reports_a_broken_deposit(tmp_path: Path, write_deposit) -> None:
    directory = write_deposit(tmp_path / "d")
    (directory / "data.csv").write_text("tampered\n")

    with pytest.raises(ValueError, match="data.csv has SHA-256"):
        main(["publish", "--deposit-dir", str(directory)])


def test_publish_requires_a_token_file_when_confirming(tmp_path: Path, write_deposit) -> None:
    directory = write_deposit(tmp_path / "d")

    with pytest.raises(SystemExit, match="requires --token-file"):
        main(["publish", "--deposit-dir", str(directory), "--confirm-upload"])
