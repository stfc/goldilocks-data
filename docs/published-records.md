# Published records

Datasets exported from this repository and deposited in [PSDI Data
Collections](https://data-collections.psdi.ac.uk), where they have a permanent
identifier and can be cited.

These are snapshots. The AiiDA database remains the authoritative calculation
record; a published dataset is a documented view of it at one point in time.

## Quantum ESPRESSO no-spin SCF calculations (SSSP, k-index)

[`52713-55d86`](https://data-collections.psdi.ac.uk/records/52713-55d86) · v1.0 ·
CC BY 4.0

The current SSSP k-index dataset: the converged k-point mesh for 17,757 MC3D
structures, numbered on the **1-based** ladder (rung 1 the Γ-only `(1, 1, 1)`
mesh) and built with the resolution floor `min_k_distance = 0.03` Å⁻¹ rather
than a per-axis k-point cap. No spin polarisation, SSSP PBEsol pseudopotentials,
every mesh unshifted and therefore gamma-inclusive.

Convergence is the first of three consecutive ladder meshes whose total energies
agree within **1 meV per atom**. Energy only — no force criterion.

| File | Contents |
| --- | --- |
| `convergence_summary.csv` | 17,757 rows: `source_db_id`, `k_index`, `k_dist_interval`, `k_mesh` |
| `CIF_files.tar.gz` | 18,220 structures, `CIF_files/<source_db_id>.cif` |

The archive carries more structures than the table has rows: 463 structures were
calculated but never met the criterion within the range of meshes swept, so they
have a structure file and no converged answer.

`k_index` needs both its base and its floor to mean anything; the record's
`README.md` and `manifest.json` carry both, and a consumer reads them from there
rather than assuming.

See [convergence criteria](reference/convergence.md) for how labels are assigned,
and the record's own `README.md` for the full definition and reproduction code.

## Publishing another one

See [Publish a dataset](publishing.md).
