from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

from goldilocks_data.sweeps.models import SweepAxis, SweepPoint

# Resolution floor for the k-mesh ladder, in Angstrom^-1 on the solid-state
# (2*pi) reciprocal lattice -- the same convention as AiiDA-QuantumESPRESSO
# k-distance. Change points denser than this are not enumerated, and this value
# is part of every recorded ``kindex``: a rung means nothing without it.
MIN_K_DISTANCE = 0.03


@dataclass(frozen=True, slots=True)
class KMeshEntry:
    """One gamma-centered k-mesh entry in increasing kindex order."""

    kindex: int
    mesh: tuple[int, int, int]
    k_distance_interval: tuple[float, float]
    k_line_density_interval: tuple[float, float] | None
    k_pra: float
    n_reduced_kpoints: int


def _reciprocal_lengths(structure: Any, *, crystallographic: bool = False) -> tuple[float, float, float]:
    lattice = structure.lattice
    reciprocal = lattice.reciprocal_lattice_crystallographic if crystallographic else lattice.reciprocal_lattice
    return (float(reciprocal.a), float(reciprocal.b), float(reciprocal.c))


def k_distance_to_mesh(structure: Any, k_distance: float) -> tuple[int, int, int]:
    """Convert a solid-state reciprocal spacing in Angstrom^-1 to a mesh."""

    lengths = _reciprocal_lengths(structure)
    return tuple(max(1, math.ceil(round(length / k_distance, 5))) for length in lengths)


def generate_candidate_k_distances(structure: Any, min_k_distance: float = MIN_K_DISTANCE) -> list[float]:
    """Return every k-distance at which some axis changes its k-point count.

    ``mesh_i = ceil(|b_i| / k_distance)`` steps from ``n`` to ``n + 1`` exactly
    at ``k_distance = |b_i| / n``, so those quotients are the only distances
    where the mesh can change.

    ``min_k_distance`` is the resolution floor in Angstrom^-1 on the solid-state
    (2*pi) reciprocal lattice; quotients below it are not enumerated. The floor
    is identical for every axis, so all axes run out of change points together
    and the returned list is a complete set of change points over the whole
    ``[min_k_distance, inf)`` range -- there is no region where a reachable mesh
    is silently skipped.
    """

    lengths = _reciprocal_lengths(structure)
    return sorted(
        {
            round(length / index, 8)
            for length in lengths
            for index in range(1, max(1, math.floor(length / min_k_distance)) + 1)
        },
        reverse=True,
    )


def mesh_to_k_line_density_interval(structure: Any, mesh: tuple[int, int, int]) -> tuple[float, float]:
    """Return the scalar k-line-density interval that maps to ``mesh``."""

    lengths = _reciprocal_lengths(structure, crystallographic=True)
    lower = max(max(0.0, (nk - 0.5) / length) for nk, length in zip(mesh, lengths, strict=True))
    upper = min((nk + 0.5) / length for nk, length in zip(mesh, lengths, strict=True))
    if lower > upper:
        raise ValueError(f"No scalar k-line-density interval for mesh={mesh}")
    return (float(lower), float(upper))


def build_gamma_kmesh_entries(structure: Any, min_k_distance: float = MIN_K_DISTANCE) -> list[KMeshEntry]:
    """Build the unshifted, Gamma-inclusive k-mesh ladder for a structure.

    ``kindex`` is 1-based and rung 1 is the Gamma-only ``(1, 1, 1)`` mesh, which
    the first probe always yields because it sits above every ``|b_i|``.

    The rung is an ordinal position on this structure's ladder and counts
    nothing. It equals the densest axis count only where the axes step together,
    as in a cubic cell.

    The ladder is complete and non-repeating down to ``min_k_distance``: every
    change point above the floor is enumerated, so consecutive rungs differ by
    at most one k-point on each axis and no reachable mesh is skipped. A mesh
    already on the ladder is dropped -- axes with equal ``|b_i|`` share their
    change points, so two consecutive intervals can yield the same mesh, and
    without the skip two ``kindex`` values would name one mesh.

    ``structure`` must be a real pymatgen ``Structure``: every rung is reduced by
    symmetry, and a structure that cannot be analysed raises rather than yielding
    an unreduced count.
    """

    candidates = generate_candidate_k_distances(structure, min_k_distance)
    if not candidates:
        return []

    # One analyser for the whole ladder: it depends on the structure alone, and
    # the reduction is by far the most expensive part of building a deep ladder.
    #
    # It is deliberately not guarded. ``n_reduced_kpoints`` and the full mesh
    # size are both ordinary integers, so a caller cannot tell a fallback from a
    # real count -- and a cubic cell reduces by up to 48. goldilocks-core ports
    # this module to size memory and to choose ``npool``, where a silently wrong
    # value is far more dangerous than a raised error.
    symmetry = SpacegroupAnalyzer(structure)

    intervals = [(k_distance_to_mesh(structure, candidates[0] + 1.0), (candidates[0], math.inf))]
    for upper, lower in zip(candidates[:-1], candidates[1:], strict=True):
        intervals.append((k_distance_to_mesh(structure, 0.5 * (upper + lower)), (lower, upper)))

    entries: list[KMeshEntry] = []
    seen: set[tuple[int, int, int]] = set()
    for mesh, interval in intervals:
        if mesh in seen:
            continue
        seen.add(mesh)
        try:
            line_interval = mesh_to_k_line_density_interval(structure, mesh)
        except ValueError:
            line_interval = None
        entries.append(
            KMeshEntry(
                kindex=len(entries) + 1,
                mesh=mesh,
                k_distance_interval=interval,
                k_line_density_interval=line_interval,
                k_pra=float(len(structure) * mesh[0] * mesh[1] * mesh[2]),
                n_reduced_kpoints=len(symmetry.get_ir_reciprocal_mesh(mesh=mesh, is_shift=(0, 0, 0))),
            )
        )
    return entries


def entry_payload(entry: KMeshEntry) -> dict[str, Any]:
    """Serialize a k-mesh entry to notebook-friendly primitive values."""

    left, right = entry.k_distance_interval
    return {
        "kindex": entry.kindex,
        "k_mesh": entry.mesh,
        "k_pra": entry.k_pra,
        "n_reduced_kpoints": entry.n_reduced_kpoints,
        "k_dist_left": float(left),
        "k_dist_right": None if math.isinf(right) else float(right),
    }


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
