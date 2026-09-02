from __future__ import annotations

from dataclasses import dataclass

from goldilocks_data.sweeps.kmesh import (
    build_gamma_kmesh_entries,
    entry_payload,
    k_distance_to_mesh,
)


@dataclass(frozen=True, slots=True)
class Reciprocal:
    a: float
    b: float
    c: float


@dataclass(frozen=True, slots=True)
class Lattice:
    reciprocal_lattice: Reciprocal
    reciprocal_lattice_crystallographic: Reciprocal


@dataclass(frozen=True, slots=True)
class Structure:
    lattice: Lattice
    natoms: int

    def __len__(self) -> int:
        return self.natoms


def test_gamma_kmesh_entries_start_with_gamma_mesh() -> None:
    structure = Structure(
        lattice=Lattice(
            reciprocal_lattice=Reciprocal(1.0, 1.0, 0.5),
            reciprocal_lattice_crystallographic=Reciprocal(0.2, 0.2, 0.1),
        ),
        natoms=4,
    )

    entries = build_gamma_kmesh_entries(structure, max_candidate_index=4)

    assert entries[0].kindex == 0
    assert entries[0].mesh == (1, 1, 1)
    assert entries[1].kindex == 1
    assert entries[0].k_pra == 4.0


def test_k_distance_to_mesh_uses_solid_state_reciprocal_lengths() -> None:
    structure = Structure(
        lattice=Lattice(
            reciprocal_lattice=Reciprocal(1.0, 2.0, 0.5),
            reciprocal_lattice_crystallographic=Reciprocal(0.2, 0.4, 0.1),
        ),
        natoms=1,
    )

    assert k_distance_to_mesh(structure, 0.51) == (2, 4, 1)


def test_entry_payload_serializes_infinite_right_bound_as_none() -> None:
    structure = Structure(
        lattice=Lattice(
            reciprocal_lattice=Reciprocal(1.0, 1.0, 1.0),
            reciprocal_lattice_crystallographic=Reciprocal(0.2, 0.2, 0.2),
        ),
        natoms=2,
    )

    payload = entry_payload(build_gamma_kmesh_entries(structure, max_candidate_index=2)[0])

    assert payload["kindex"] == 0
    assert payload["k_mesh"] == (1, 1, 1)
    assert payload["k_dist_right"] is None
