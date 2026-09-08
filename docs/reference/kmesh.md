# k-mesh quantities

A structure's meshes form one ordered ladder, and each rung is a `KMeshEntry`
carrying six quantities. They describe the same mesh in different units, and two
of them use different reciprocal-lattice conventions, so mixing them silently is
easy. This page defines each one.

Built by `goldilocks_data.kmesh.build_gamma_kmesh_entries`.

## Two reciprocal conventions, both in use

pymatgen exposes a reciprocal lattice in two forms, and this module uses both:

- **solid-state**, `lattice.reciprocal_lattice`, which includes the 2π factor
- **crystallographic**, `lattice.reciprocal_lattice_crystallographic`, without it

They differ by exactly 2π. For MC3D `100115` (ZnBi, 4 atoms):

```text
|b| solid-state      = [1.6106, 1.6106, 0.8704]  A^-1
|b| crystallographic = [0.2563, 0.2563, 0.1385]  A^-1
ratio                = 6.2832
```

`mesh`, `k_distance_interval` and the ladder itself use the **solid-state**
lengths. `k_line_density_interval` uses the **crystallographic** ones. A
k-distance and a k-line density from the same entry are therefore not on the
same scale.

## `kindex`

The rung's position, **1-based**, with rung 1 the Γ-only `(1, 1, 1)` mesh. Each
step up is the next denser mesh the reciprocal lattice admits.

`kindex` only means something together with the resolution floor
`min_k_distance` that bounded the ladder — see [the ladder](#the-ladder) below.
Read the base and the floor from a record rather than assuming them.

## `mesh`

The Monkhorst–Pack subdivisions `(n1, n2, n3)`, unshifted. Because the shift is
always `(0, 0, 0)`, every mesh contains Γ.

Derived from a k-distance by the VASP `KSPACING` convention, on the solid-state
lengths:

```text
n_i = max(1, ceil(|b_i| / k_distance))
```

## `k_distance_interval`

The half-open range of k-distance that yields this mesh, as `(lower, upper)` in
Å⁻¹ on the solid-state lengths. Any k-distance in it gives the same mesh.

A mesh corresponds to an interval, never a single value. Rung 1's upper bound is
infinite: every k-distance above `max(|b_i|)` gives `(1, 1, 1)`.

```text
kindex  1  mesh (1, 1, 1)   k_distance_interval (1.61061, inf)
kindex  2  mesh (2, 2, 1)   k_distance_interval (0.87042, 1.61061)
kindex 21  mesh (14, 14, 8) k_distance_interval (0.11504, 0.12389)
```

If you reduce the interval to one number for training, record which end you
took. The two ends are different numbers for the same mesh.

!!! warning "`entry_payload` names the ends the other way round"

    `entry_payload` emits `k_dist_left` for the interval's **lower** bound and
    `k_dist_right` for its **upper** bound, so for `kindex 21` above it gives
    `k_dist_left = 0.11504` and `k_dist_right = 0.12389`.

    Published records write `k_dist_interval` the other way round — larger value
    first, `[0.12389, 0.11504)`, because a larger k-distance means a coarser
    mesh. Joining notebook output with a record without checking will swap the
    bounds: compare magnitudes, not column names. Tracked as
    [#30](https://github.com/stfc/goldilocks-data/issues/30).

## `k_line_density_interval`

The range of scalar k-line density that yields this mesh, on the
**crystallographic** lengths:

```text
lower = max_i (n_i - 0.5) / |b_i|
upper = min_i (n_i + 0.5) / |b_i|
```

`None` when no scalar density maps to the mesh — the per-axis constraints can
have an empty intersection, in which case that mesh is unreachable by a single
density even though it is reachable by a k-distance.

## `k_pra`

K-points per reciprocal atom: the full mesh size times the number of atoms.

```text
k_pra = n_atoms * n1 * n2 * n3
```

For `100115` at `kindex 21`: `4 * 14 * 14 * 8 = 6272`. It is a cost-like measure
that lets meshes be compared across cells of different sizes, and it uses the
**full** mesh, not the symmetry-reduced count.

## `n_reduced_kpoints`

How many k-points survive symmetry reduction of the unshifted mesh, via
pymatgen's `SpacegroupAnalyzer.get_ir_reciprocal_mesh`. This is what the
calculation actually costs. For `100115` at `kindex 21`: **120**, against a full
mesh of 1568.

!!! note "It falls back to the full mesh size"

    If pymatgen is not installed, or the structure does not expose the API, the
    value returned is `n1 * n2 * n3` — the unreduced count. No error is raised,
    so a value equal to the full mesh size may mean "no symmetry found" or "not
    computed". Install the `kmesh` extra before relying on it.

## The ladder {#the-ladder}

Change points are `|b_i| / n`, because `ceil(|b_i| / k_distance)` steps from `n`
to `n + 1` exactly there. Sorted descending, each interval between neighbours is
one rung, and probing its midpoint gives the mesh. The first probe sits above
`max(|b_i|)` and yields the Γ-only mesh.

`min_k_distance` (default **0.03 Å⁻¹**, on the solid-state 2π lengths — the
AiiDA-QuantumESPRESSO convention) is the resolution floor: change points denser
than it are not enumerated, so the ladder ends at a mesh of roughly
`ceil(|b_i| / min_k_distance)` per axis.

The floor is identical for every axis, so the axes run out of change points
together. Every change point on `[min_k_distance, ∞)` is therefore present and
consecutive rungs differ by at most one k-point on each axis — the ladder has no
region where a reachable mesh is silently skipped.

One rule still shapes it: **skip a repeat**. Axes with equal `|b_i|` share their
change points, and the two rounding precisions (`round(·, 8)` on the candidate
k-distances, `round(·, 5)` inside `k_distance_to_mesh`) can land two adjacent
intervals on one mesh; without the skip, that mesh would take two `kindex`
values.

Lowering `min_k_distance` only appends rungs and never renumbers an existing
one, so a recorded `kindex` stays valid under a smaller floor. A `kindex`
computed under a *different* floor is comparable only where the two ranges
overlap — so any published `kindex` column must state its floor.

This convention must stay in step with
[goldilocks-core](https://github.com/stfc/goldilocks-core) and goldilocks-ml.
Changing it invalidates every `kindex` already recorded or trained on.
