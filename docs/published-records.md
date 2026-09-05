# Published records

Datasets exported from this repository and deposited in [PSDI Data
Collections](https://data-collections.psdi.ac.uk), where they have a permanent
identifier and can be cited.

These are snapshots. The AiiDA database remains the authoritative calculation
record; a published dataset is a documented view of it at one point in time.

## Quantum ESPRESSO no-spin SCF calculations (SSSP, K-index)

[`d5ds2-64f16`](https://data-collections.psdi.ac.uk/records/d5ds2-64f16) · v1 ·
CC BY 4.0

The converged k-point mesh for 17,757 MC3D structures. No spin polarisation,
SSSP PBEsol pseudopotentials, every mesh unshifted and therefore
gamma-inclusive.

Convergence is the first of three consecutive k-distances whose total energies
agree within **1 meV per atom**. Energy only — no force criterion.

| File | Contents |
| --- | --- |
| `convergence_summary.csv` | 17,757 rows: `source_db_id`, `k_index`, `k_dist_interval`, `k_mesh` |
| `CIF_files.tar.gz` | 18,220 structures, `CIF_files/<source_db_id>.cif` |

The archive carries more structures than the table has rows: 463 structures were
calculated but never met the criterion within the range of meshes swept, so they
have a structure file and no converged answer.

### The k_index in this record

`k_index` in this record is **0-based, with rung 0 the gamma-only `(1, 1, 1)`
mesh**, and was computed with a per-axis enumeration bound of **50**, the ladder
truncated at the first rung where an axis count would rise by more than one.

!!! warning "This record is 0-based; the convention since is 1-based"

    Everything produced after this record numbers the same ladder from 1, so
    rung *n* here is rung *n + 1* under the current convention. The published
    record is not rewritten: it keeps the convention it was published with, and
    a consumer reads the base from the record rather than assuming it.

That bound is part of the definition, not an implementation detail. The change
points of the ladder are `|b_i| / n`, the bound applies per axis, and axes with
different `|b_i|` exhaust their change points at different k-distances — so the
ladder is a complete set of meshes only down to `max(|b_i|) / 50`. Below that a
reachable mesh can be skipped. Any recomputation must state the bound it used or
its `k_index` values are not comparable with these.

Raising the bound only appends rungs and never renumbers an existing one, so
these values stay valid under a larger enumeration.

See [convergence criteria](reference/convergence.md) for how labels are assigned,
and the record's own `README.md` for the full definition and reproduction code.

## Publishing another one

See [Publish a dataset](publishing.md).
