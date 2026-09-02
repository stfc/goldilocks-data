from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class ConvergenceThresholds:
    """Energy-oscillation thresholds used to assign kindex convergence labels."""

    medium_mev_per_atom: float = 10.0
    well_mev_per_atom: float = 5.0
    ultra_mev_per_atom: float = 1.0
    min_tail_points: int = 3


def build_convergence_table(records: pd.DataFrame, thresholds: ConvergenceThresholds | None = None) -> pd.DataFrame:
    """Return per-kindex energies, tail oscillations, and convergence labels."""

    limits = thresholds or ConvergenceThresholds()
    conv_df = records.copy()
    conv_df = conv_df[conv_df["energy"].notna() & conv_df["energy_per_atom"].notna()].copy()
    if conv_df.empty:
        return conv_df

    conv_df["energy_per_atom"] = conv_df["energy_per_atom"].astype(float)
    conv_df["kindex"] = conv_df["kindex"].astype(int)
    conv_df = conv_df.sort_values("kindex").reset_index(drop=True)

    oscillations_per_cell: list[float | None] = []
    oscillations_per_atom: list[float | None] = []
    for index in range(len(conv_df)):
        tail = conv_df.iloc[index:]
        if len(tail) >= limits.min_tail_points:
            oscillations_per_cell.append((tail["energy"].max() - tail["energy"].min()) * 1000.0)
            oscillations_per_atom.append((tail["energy_per_atom"].max() - tail["energy_per_atom"].min()) * 1000.0)
        else:
            oscillations_per_cell.append(None)
            oscillations_per_atom.append(None)
    conv_df["energy_oscillation_meV_per_cell"] = oscillations_per_cell
    conv_df["energy_oscillation_meV_per_atom"] = oscillations_per_atom

    medium_kindex = _first_kindex_below(conv_df, limits.medium_mev_per_atom)
    well_kindex = _first_kindex_below(conv_df, limits.well_mev_per_atom)
    ultra_kindex = _first_kindex_below(conv_df, limits.ultra_mev_per_atom)
    conv_df["label"] = [
        _label_for_kindex(int(row["kindex"]), medium_kindex, well_kindex, ultra_kindex) for _, row in conv_df.iterrows()
    ]
    return conv_df


def summarize_convergence(
    conv_df: pd.DataFrame,
    thresholds: ConvergenceThresholds | None = None,
) -> dict[str, Any]:
    """Return one summary row for a convergence table."""

    if conv_df.empty:
        return {
            "medium_kindex": None,
            "well_kindex": None,
            "ultra_kindex": None,
            "ultra_converged": False,
            "max_finished_kindex": None,
        }

    limits = thresholds or ConvergenceThresholds()
    medium_kindex = _first_kindex_below(conv_df, limits.medium_mev_per_atom)
    well_kindex = _first_kindex_below(conv_df, limits.well_mev_per_atom)
    ultra_kindex = _first_kindex_below(conv_df, limits.ultra_mev_per_atom)
    ultra_rows = conv_df[conv_df["kindex"].eq(ultra_kindex)] if ultra_kindex is not None else conv_df.iloc[0:0]
    ultra_row = None if ultra_rows.empty else ultra_rows.iloc[0]
    return {
        "medium_kindex": medium_kindex,
        "well_kindex": well_kindex,
        "ultra_kindex": ultra_kindex,
        "ultra_converged": not ultra_rows.empty,
        "max_finished_kindex": int(conv_df["kindex"].max()),
        "ultra_k_mesh": None if ultra_row is None else ultra_row.get("k_mesh"),
        "ultra_energy_per_atom": None if ultra_row is None else ultra_row.get("energy_per_atom"),
        "ultra_oscillation_meV_per_atom": None
        if ultra_row is None
        else ultra_row.get("energy_oscillation_meV_per_atom"),
        "ultra_pk": None if ultra_row is None else int(ultra_row.get("pk")),
    }


def _first_kindex_below(conv_df: pd.DataFrame, threshold_mev_per_atom: float) -> int | None:
    candidates = conv_df[
        conv_df["energy_oscillation_meV_per_atom"].notna()
        & (conv_df["energy_oscillation_meV_per_atom"] < threshold_mev_per_atom)
    ]
    return None if candidates.empty else int(candidates.iloc[0]["kindex"])


def _label_for_kindex(
    kindex: int,
    medium_kindex: int | None,
    well_kindex: int | None,
    ultra_kindex: int | None,
) -> str:
    if ultra_kindex is not None and kindex > ultra_kindex:
        return "overconverged"
    if ultra_kindex is not None and kindex == ultra_kindex:
        return "ultra"
    if well_kindex is not None and kindex == well_kindex:
        return "well"
    if medium_kindex is not None and kindex == medium_kindex:
        return "medium"
    if well_kindex is not None and ultra_kindex is not None and well_kindex < kindex < ultra_kindex:
        return "well-to-ultra"
    if medium_kindex is not None and well_kindex is not None and medium_kindex < kindex < well_kindex:
        return "medium-to-well"
    if (
        medium_kindex is not None
        and ultra_kindex is not None
        and well_kindex is None
        and medium_kindex < kindex < ultra_kindex
    ):
        return "medium-to-ultra"
    return "unconverged"
