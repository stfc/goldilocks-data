from __future__ import annotations

import pandas as pd
import pytest

from goldilocks_data.analysis.convergence import (
    build_convergence_table,
    summarize_convergence,
)


def test_ultra_label_requires_less_than_one_mev_per_atom_tail_oscillation() -> None:
    records = pd.DataFrame(
        [
            {"pk": 1, "kindex": 0, "k_mesh": (1, 1, 1), "energy": -10.0000, "energy_per_atom": -5.0000},
            {"pk": 2, "kindex": 1, "k_mesh": (2, 2, 2), "energy": -10.0030, "energy_per_atom": -5.0015},
            {"pk": 3, "kindex": 2, "k_mesh": (3, 3, 3), "energy": -10.0018, "energy_per_atom": -5.0009},
            {"pk": 4, "kindex": 3, "k_mesh": (4, 4, 4), "energy": -10.0020, "energy_per_atom": -5.0010},
            {"pk": 5, "kindex": 4, "k_mesh": (5, 5, 5), "energy": -10.0022, "energy_per_atom": -5.0011},
        ]
    )

    table = build_convergence_table(records)

    assert table.loc[table["kindex"] == 1, "energy_oscillation_meV_per_atom"].item() == pytest.approx(0.6)
    assert table.loc[table["kindex"] == 1, "label"].item() == "ultra"
    assert table.loc[table["kindex"] == 2, "label"].item() == "overconverged"


def test_energy_oscillation_keeps_cell_and_atom_units() -> None:
    records = pd.DataFrame(
        [
            {"pk": 1, "kindex": 0, "k_mesh": (1, 1, 1), "energy": -20.000, "energy_per_atom": -10.000},
            {"pk": 2, "kindex": 1, "k_mesh": (2, 2, 2), "energy": -20.004, "energy_per_atom": -10.002},
            {"pk": 3, "kindex": 2, "k_mesh": (3, 3, 3), "energy": -20.002, "energy_per_atom": -10.001},
        ]
    )

    table = build_convergence_table(records)

    assert table.loc[0, "energy_oscillation_meV_per_cell"] == pytest.approx(4.0)
    assert table.loc[0, "energy_oscillation_meV_per_atom"] == pytest.approx(2.0)


def test_summary_reports_ultra_row_metadata() -> None:
    records = pd.DataFrame(
        [
            {"pk": 1, "kindex": 0, "k_mesh": (1, 1, 1), "energy": -1.0000, "energy_per_atom": -1.0000},
            {"pk": 2, "kindex": 1, "k_mesh": (2, 2, 2), "energy": -1.0008, "energy_per_atom": -1.0008},
            {"pk": 3, "kindex": 2, "k_mesh": (3, 3, 3), "energy": -1.0009, "energy_per_atom": -1.0009},
            {"pk": 4, "kindex": 3, "k_mesh": (4, 4, 4), "energy": -1.0010, "energy_per_atom": -1.0010},
        ]
    )

    summary = summarize_convergence(build_convergence_table(records))

    assert summary["ultra_converged"] is True
    assert summary["ultra_kindex"] == 0
    assert summary["ultra_k_mesh"] == (1, 1, 1)
    assert summary["ultra_pk"] == 1


def test_summary_reports_coincident_threshold_kindices() -> None:
    records = pd.DataFrame(
        [
            {"pk": 1, "kindex": 0, "k_mesh": (1, 1, 1), "energy": -10.000, "energy_per_atom": -5.000},
            {"pk": 2, "kindex": 1, "k_mesh": (2, 2, 2), "energy": -10.032, "energy_per_atom": -5.016},
            {"pk": 3, "kindex": 2, "k_mesh": (3, 3, 3), "energy": -10.028, "energy_per_atom": -5.014},
            {"pk": 4, "kindex": 3, "k_mesh": (4, 4, 4), "energy": -10.030, "energy_per_atom": -5.015},
        ]
    )

    summary = summarize_convergence(build_convergence_table(records))

    assert summary["medium_kindex"] == 1
    assert summary["well_kindex"] == 1
    assert summary["ultra_kindex"] is None
