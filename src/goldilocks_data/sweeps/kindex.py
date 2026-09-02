from __future__ import annotations

from goldilocks_data.sweeps.kmesh import build_gamma_kmesh_entries
from goldilocks_data.sweeps.models import SweepAxis, SweepPoint


def kindex_points(structure: object, kindex_min: int, kindex_max: int) -> tuple[SweepPoint, ...]:
    """Build explicit sweep points for a gamma-inclusive kindex range."""

    entries = build_gamma_kmesh_entries(structure)
    points: list[SweepPoint] = []
    for entry in entries[int(kindex_min) : int(kindex_max) + 1]:
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
