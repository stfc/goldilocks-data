from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


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


def generate_candidate_k_distances(structure: Any, max_kpoints_per_axis: int = 50) -> list[float]:
    """Return the k-distances at which any axis changes its k-point count.

    ``mesh_i = ceil(|b_i| / k_distance)`` steps from ``n`` to ``n + 1`` exactly at
    ``k_distance = |b_i| / n``, so those quotients are the only distances where
    the mesh can change.

    ``max_kpoints_per_axis`` bounds ``n`` — how many k-points per axis are
    enumerated. It is *not* a bound on the number of rungs, which is roughly the
    number of distinct axis lengths times the bound. Because the bound applies
    per axis and the axes have different ``|b_i|``, they exhaust their quotients
    at different distances: the returned list is a complete set of change points
    only down to ``max(|b_i|) / max_kpoints_per_axis``. See
    ``build_gamma_kmesh_entries`` for what that implies.
    """

    lengths = _reciprocal_lengths(structure)
    return sorted(
        {round(length / index, 8) for length in lengths for index in range(1, max_kpoints_per_axis + 1)},
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


def _n_reduced_kpoints(structure: Any, mesh: tuple[int, int, int]) -> int:
    full_mesh_size = int(mesh[0] * mesh[1] * mesh[2])
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    except ImportError:
        return full_mesh_size
    try:
        return len(SpacegroupAnalyzer(structure).get_ir_reciprocal_mesh(mesh=mesh, is_shift=(0, 0, 0)))
    except AttributeError:
        return full_mesh_size


def build_gamma_kmesh_entries(structure: Any, max_kpoints_per_axis: int = 50) -> list[KMeshEntry]:
    """Build the unshifted, Gamma-inclusive k-mesh ladder for a structure.

    ``kindex`` is 1-based and rung 1 is the Gamma-only ``(1, 1, 1)`` mesh, which
    the first probe always yields because it sits above every ``|b_i|``. The
    rung therefore counts k-points on the densest axis of the coarsest mesh it
    could be: rung n is reached when some axis first needs n k-points.

    The ladder is complete and non-repeating:

    * It stops at the first rung where an axis count would rise by more than one.
      Once the longest axis has used up its enumerated quotients its count keeps
      rising with no candidate marking the change, so adjacent candidates span
      several meshes and probing the midpoint keeps only one of them. A jump
      greater than one is exactly that condition.
    * It skips a mesh already on the ladder. Axes with equal ``|b_i|`` share
      their change points, so two consecutive intervals can yield the same mesh;
      without this, two ``kindex`` values would name one mesh.
    """

    candidates = generate_candidate_k_distances(structure, max_kpoints_per_axis)
    if not candidates:
        return []

    intervals = [(k_distance_to_mesh(structure, candidates[0] + 1.0), (candidates[0], math.inf))]
    for upper, lower in zip(candidates[:-1], candidates[1:], strict=True):
        intervals.append((k_distance_to_mesh(structure, 0.5 * (upper + lower)), (lower, upper)))

    entries: list[KMeshEntry] = []
    seen: set[tuple[int, int, int]] = set()
    previous: tuple[int, int, int] | None = None
    for mesh, interval in intervals:
        if previous is not None and any(now - before > 1 for before, now in zip(previous, mesh, strict=True)):
            break
        previous = mesh
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
                n_reduced_kpoints=_n_reduced_kpoints(structure, mesh),
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
