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


def generate_candidate_k_distances(structure: Any, max_index: int = 30) -> list[float]:
    """Generate spacing boundaries that can change at least one mesh axis."""

    lengths = _reciprocal_lengths(structure)
    return sorted({round(length / index, 8) for length in lengths for index in range(1, max_index + 1)}, reverse=True)


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


def build_gamma_kmesh_entries(structure: Any, max_candidate_index: int = 30) -> list[KMeshEntry]:
    """Build distinct unshifted, Gamma-inclusive k-mesh entries for a structure."""

    candidates = generate_candidate_k_distances(structure, max_candidate_index)
    if not candidates:
        return []

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
                kindex=len(entries),
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
