# Published records

Datasets exported from this repository and deposited in [PSDI Data
Collections](https://data-collections.psdi.ac.uk), where they have a permanent
identifier and can be cited.

These are snapshots. The AiiDA database remains the authoritative calculation
record; a published dataset is a documented view of it at one point in time.

## Quantum ESPRESSO no-spin SCF k-point convergence

Two records, one body of calculations. Same structures, same settings, same
`pw.x` runs — they differ in what was extracted. Produced by the
[QE SCF k-point campaign](campaigns/qe-kpoints.md).

### `52713-55d86` — the converged mesh per structure

[`52713-55d86`](https://data-collections.psdi.ac.uk/records/52713-55d86) · v2.0 ·
CC BY 4.0

The converged k-point mesh for 17,757 MC3D structures, numbered on the **1-based** ladder (rung 1 the Γ-only `(1, 1, 1)`
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

### `mcpnq-g1j55` — the full per-calculation dump

[`mcpnq-g1j55`](https://data-collections.psdi.ac.uk/records/mcpnq-g1j55) ·
CC BY 4.0

The complete DFT data behind *Automatic generation of input files with optimised
k-point meshes for Quantum ESPRESSO self-consistent field total energy
calculations* — the training set for the paper's machine-learning models. The
same calculations as the record above, expressed as a k-distance, and a raw
per-calculation dump rather than a convergence-label table. Take this one when
you want the QE outputs themselves: cutoffs, Fermi level, symmetry counts, wall
time.

| File | Contents |
| --- | --- |
| `data.tar.gz` | Unpacks to the two entries below |
| `summary.csv` | Per-material k-point convergence: Goldilocks-optimised mesh, MC3D reference mesh, k-distance metrics, and medium / well / ultra levels |
| `structure_calc_details/` | One directory per structure: the `.cif` plus the full QE output (energies, cutoffs, Fermi level, symmetry counts, wall time, convergence notes) |

This record predates the k-mesh ladder convention and carries meshes and
k-distances directly, not a `k_index`.

## Quantum ESPRESSO nscf band structures

[`r3byg-xp284`](https://data-collections.psdi.ac.uk/records/r3byg-xp284) · v1 ·
CC BY 4.0

Produced by the [QE nscf band campaign](campaigns/qe-nscf-bands.md).

Non-self-consistent band-structure calculations for **19,405 MC3D structures**:
one summary row per material, the primitive cell the bands were computed on, and
the eigenvalues along the high-symmetry k-point path. Every structure has all
three — there is no row without a structure file and none without a band table.

Same settings and the same family of structures as the SCF records above.
Those answer *which mesh is dense enough*; this one answers *what the band
structure says about the material*.

| File | Contents |
| --- | --- |
| `nscf_band_summary.csv` | 19,405 rows: identifiers, Fermi energy, `metallicity`, `band_gap_ev` |
| `CIF_files.tar.gz` | 19,405 primitive cells, `CIF_files/<source_db_id>.cif` |
| `bands.tar.gz` | 19,405 eigenvalue tables, `bands/<source_db_id>.csv` |
| `example.py` | Loads all three from the tarballs and plots one band structure |

9,854 rows are `metal` and 9,551 `insulator`. `band_gap_ev` is populated for
exactly the insulators and empty for exactly the metals.

### `metallicity` is a zero threshold, not a physical one

A row is `insulator` when the band structure has a gap at the Fermi level, with
no tolerance at all: the smallest gap in the table is **0.0016 eV**, and nothing
was rounded down. A PBEsol gap of a few meV is well inside the error of the
method, and a practitioner would treat such a system as metallic.

No thresholded label is published. A threshold frozen into an immutable record
becomes a convention every consumer then has to discover and match — the same
failure that forced the first dataset's `k_index` column to be recomputed
wholesale. The gap is the fact; the cut belongs to the person using it, and
`band_gap_ev` is published raw so it can be made.

Anything downstream that trains on this column should name the threshold in
its own target name, so that a later dataset built on a different cut cannot be
mistaken for this one.

### The k-point coordinates were reconstructed, and checked

The eigenvalue tables as calculated carried no k-point coordinates. The path
came from SeeKpath through the standard `PwBandsWorkChain`, so it was
regenerated per structure — the campaign did not use a single sampling density,
so the density was determined structure by structure.

A reconstruction was accepted only when it matched the calculation's own record
of the labelled points on **all four** of: number of k-points, labels, label
positions in the table, and label coordinates. That makes the match a
verification rather than an assumption, and it doubles as a detector.

Two groups are excluded from the record entirely — structure, summary row and
bands alike:

| Excluded | Why |
| --- | --- |
| 104 structures | the regenerated path did not match, rather than publish coordinates that might not be theirs |
| 80 structures | their eigenvalue tables were not in the working archive |

The eigenvalues themselves are copied unchanged from the calculation output.

## Publishing another one

See [Publish a dataset](publishing.md).
