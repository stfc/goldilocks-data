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

    entries = build_gamma_kmesh_entries(structure, max_kpoints_per_axis=4)

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

    payload = entry_payload(build_gamma_kmesh_entries(structure, max_kpoints_per_axis=2)[0])

    assert payload["kindex"] == 0
    assert payload["k_mesh"] == (1, 1, 1)
    assert payload["k_dist_right"] is None


def _structure(a: float, b: float, c: float, natoms: int = 1) -> Structure:
    return Structure(
        lattice=Lattice(
            reciprocal_lattice=Reciprocal(a, b, c),
            reciprocal_lattice_crystallographic=Reciprocal(a / 5, b / 5, c / 5),
        ),
        natoms=natoms,
    )


def test_ladder_never_skips_a_reachable_mesh() -> None:
    # An anisotropic cell: the long axes exhaust their change points while the
    # short one is still stepping, which is where an unbounded ladder starts
    # jumping several meshes at once.
    entries = build_gamma_kmesh_entries(_structure(2.5547, 2.5547, 0.6485), max_kpoints_per_axis=30)
    meshes = [entry.mesh for entry in entries]

    assert len(meshes) > 1
    for before, after in zip(meshes[:-1], meshes[1:], strict=True):
        steps = [now - previous for previous, now in zip(before, after, strict=True)]
        assert max(steps) == 1, f"{before} -> {after} skips a mesh"
        assert min(steps) >= 0, f"{before} -> {after} is not monotonic"


def test_ladder_never_repeats_a_mesh_for_degenerate_axes() -> None:
    # MC3D 170541 (SiO2): |b_1| and |b_3| are exactly equal, so their change
    # points coincide and two consecutive intervals yield the same mesh. Without
    # the skip, two kindex values would name one mesh.
    meshes = [entry.mesh for entry in build_gamma_kmesh_entries(_structure(0.701, 0.7816, 0.701))]

    assert len(meshes) == len(set(meshes))
    assert meshes[:4] == [(1, 1, 1), (1, 2, 1), (2, 2, 2), (2, 3, 2)]


def test_raising_the_axis_bound_only_extends_the_ladder() -> None:
    # kindex is recorded in campaign snapshots and published records, so a
    # larger enumeration must never renumber a rung that already existed.
    structure = _structure(2.5547, 2.5547, 0.6485)
    short = [entry.mesh for entry in build_gamma_kmesh_entries(structure, max_kpoints_per_axis=20)]
    long = [entry.mesh for entry in build_gamma_kmesh_entries(structure, max_kpoints_per_axis=60)]

    assert len(long) > len(short)
    assert long[: len(short)] == short


def test_kindex_is_contiguous_and_zero_based() -> None:
    entries = build_gamma_kmesh_entries(_structure(0.701, 0.7816, 0.701))

    assert [entry.kindex for entry in entries] == list(range(len(entries)))
