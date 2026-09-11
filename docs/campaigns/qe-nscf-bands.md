# QE nscf band structures

This campaign computes the band structure of each MC3D structure along its
high-symmetry k-point path, and reads the Fermi level, the metallicity and the
band gap off it.

Published as
[`r3byg-xp284`](https://data-collections.psdi.ac.uk/records/r3byg-xp284) —
19,405 structures, with the eigenvalues themselves, not only the derived
numbers.

## Campaign definition

| Setting | Value |
| --- | --- |
| Code | Quantum ESPRESSO `pw.x` |
| Task | nscf band structure, from the charge density of a self-consistent parent |
| Functional | PBEsol |
| Pseudopotentials | SSSP |
| Spin | None |
| Cell | Primitive, as SeeKpath standardises it |
| k-point path | SeeKpath, through `PwBandsWorkChain` |

Same settings and the same family of structures as the
[SCF k-point campaign](qe-kpoints.md), so a structure's two records describe the
same material computed the same way.

## Reproducing it

The record is self-contained: it carries the cell each calculation ran on, so
you do not have to re-derive the structure from MC3D to compare against it.

1. **Take the structure from the record.** `CIF_files/<source_db_id>.cif` is the
   primitive cell the bands were computed on, not a conventional cell that then
   needs standardising.

2. **Generate the path with SeeKpath.** The workflow is the standard
   [`PwBandsWorkChain`](https://aiida-quantumespresso.readthedocs.io/en/stable/howto/run_pwbands.html),
   which finds the primitive cell and builds the high-symmetry path. Its
   `bands_kpoints_distance` is what controls how densely the path is sampled:
   the built-in protocols use 0.1 (`fast`), 0.025 (`balanced`) and 0.015
   (`stringent`) Å⁻¹.

3. **Check the path before comparing eigenvalues.** The published
   `bands/<source_db_id>.csv` carries `kx, ky, kz` and the high-symmetry
   `label`, so a regenerated path can be compared point for point. Do that
   first — two paths that differ in sampling density are not comparable row by
   row even when both are correct.

4. **Run nscf on the parent charge density.** Eigenvalues are in eV in the
   published tables; QE writes them in eV as well, so no conversion is involved.

!!! note "The path density is not one number across the record"

    The archive was not produced with a single `bands_kpoints_distance`, so the
    density was determined per structure. Take it from the published k-point
    coordinates rather than assuming a protocol default. The
    [record page](../published-records.md#quantum-espresso-nscf-band-structures)
    explains how those coordinates were reconstructed and on what evidence each
    one was accepted.

## Deriving the labels yourself

`metallicity` and `band_gap_ev` are both derived from the eigenvalues and the
Fermi energy that the record publishes, so neither has to be taken on trust. The
threshold used for `metallicity` is a plain zero — see
[the record page](../published-records.md#metallicity-is-a-zero-threshold-not-a-physical-one)
for why no thresholded label is published, and pick your own cut on
`band_gap_ev` if your work needs one.

## Start here

`example.py` in the record loads the summary, the structures and the bands
straight out of the tarballs and plots one band structure:

```bash
python example.py                 # the summary, then a plotted band structure
python example.py 100115          # one structure by source_db_id
```
