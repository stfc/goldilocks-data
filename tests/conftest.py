from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

COMMUNITY = "data-to-knowledge"

DATASET_RECORD = {
    "schema_version": 1,
    "dataset": "goldilocks-mc3d-nospin-scf-kmesh",
    "version": "v1",
    "rows": 2,
    "columns": [
        {"name": "source_db_id", "dtype": "str"},
        {"name": "k_index", "dtype": "int", "definition": "kmesh_ladder_rung"},
    ],
    "conventions": {"kmesh_ladder": {"base": 0, "max_kpoints_per_axis": 50}},
    "provenance": {"code": "quantum_espresso", "calculation": "scf", "spin": "none"},
}

PSDI_METADATA = {
    "access": {"record": "public", "files": "public"},
    "metadata": {"title": "test", "resource_type": {"id": "dataset"}},
}


@pytest.fixture
def dataset_record() -> dict:
    return dict(DATASET_RECORD)


@pytest.fixture
def community() -> str:
    return COMMUNITY


@pytest.fixture
def write_deposit() -> Callable[..., Path]:
    """Write a deposit directory whose SHA256SUMS matches its payload."""

    def build(directory: Path, *, payload: dict[str, str] | None = None, dataset_record: bool = True) -> Path:
        payload = payload if payload is not None else {"data.csv": "source_db_id,k_index\n1,0\n2,3\n"}
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "README.md").write_text("# test dataset\n")
        (directory / "metadata.json").write_text(json.dumps(PSDI_METADATA))
        listed = ["README.md"]
        if dataset_record:
            (directory / "dataset.json").write_text(json.dumps(DATASET_RECORD))
            listed.append("dataset.json")

        lines = []
        for name, text in payload.items():
            (directory / name).write_text(text)
            lines.append(f"{hashlib.sha256(text.encode()).hexdigest()}  {name}")
        for name in listed:
            digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}")
        (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n")
        return directory

    return build


@pytest.fixture
def psdi_metadata() -> dict:
    return dict(PSDI_METADATA)
