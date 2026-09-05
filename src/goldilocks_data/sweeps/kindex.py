from __future__ import annotations

from goldilocks_data.sweeps.kmesh import build_gamma_kmesh_entries
from goldilocks_data.sweeps.models import SweepAxis, SweepPoint


def kindex_points(structure: object, kindex_min: int, kindex_max: int) -> tuple[SweepPoint, ...]:
    """Build explicit sweep points for a gamma-inclusive kindex range.

    ``kindex_min`` and ``kindex_max`` are rungs, not list positions: rung 1 is
    the Gamma-only mesh and lives at index 0.
    """

    entries = build_gamma_kmesh_entries(structure)
    selected = [entry for entry in entries if int(kindex_min) <= entry.kindex <= int(kindex_max)]
    points: list[SweepPoint] = []
    for entry in selected:
        points.append(
            SweepPoint(
                axis_values={SweepAxis.KINDEX.value: int(entry.kindex)},
                k_mesh=entry.mesh,
                extras={
                    "kindex": int(entry.kindex),
                    "k_mesh": list(entry.mesh),
                    "k_pra": entry.k_pra,
                    "n_reduced_kpoints": entry.n_reduced_kpoints,
                },
            )
        )
    return tuple(points)
