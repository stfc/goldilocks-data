# QE nscf band structures

These calculations give the band structure of each MC3D structure along its
high-symmetry k-point path, and the Fermi level, metallicity and band gap read
off it.

Published as
[`r3byg-xp284`](https://data-collections.psdi.ac.uk/records/r3byg-xp284) —
19,405 structures, with the eigenvalues themselves, not only the derived
numbers.

## What was calculated

| Setting | Value |
| --- | --- |
| Code | Quantum ESPRESSO `pw.x` |
| Task | nscf band structure, from the charge density of a self-consistent parent |
| Functional | PBEsol |
| Pseudopotentials | SSSP |
| Spin | None |
| Cell | Primitive, as SeeKpath standardises it |
| k-point path | SeeKpath, through `PwBandsWorkChain` |

Same settings and the same structures as the
[SCF k-point sweeps](qe-kpoints.md), so a material's two records describe the
same system computed the same way.

## Reproduce it

The workflow is the standard
[`PwBandsWorkChain`](https://aiida-quantumespresso.readthedocs.io/en/stable/howto/run_pwbands.html),
which standardises the cell, builds the SeeKpath path, runs the self-consistent
parent, and then the nscf calculation on its charge density. You need AiiDA with
a configured `pw.x` code and an installed pseudopotential family.

```bash
uv sync --extra aiida
```

```python
from aiida import load_profile, orm
from aiida.engine import submit
from aiida.plugins import WorkflowFactory
from ase.io import read

load_profile()

PwBandsWorkChain = WorkflowFactory("quantumespresso.pw.bands")
pseudo_family = "SSSP/1.3/PBEsol/efficiency"

builder = PwBandsWorkChain.get_builder_from_protocol(
    code=orm.load_code("pw-7.5@your-computer"),
    structure=orm.StructureData(ase=read("100115.cif")),
    protocol="balanced",
    overrides={
        "bands_kpoints_distance": 0.1,
        "scf": {"pseudo_family": pseudo_family},
        "bands": {"pseudo_family": pseudo_family},
    },
)
node = submit(builder)
print(node.pk)
```

`bands_kpoints_distance` is what controls how densely the path is sampled. The
built-in protocols use 0.1 (`fast`), 0.025 (`balanced`) and 0.015 (`stringent`)
Å⁻¹, and the override above pins it rather than inheriting it, which matters —
see the note below.

When the workchain finishes, `node.outputs.band_structure` carries the
eigenvalues and the labelled k-points, and `node.outputs.band_parameters` the
Fermi energy.

!!! warning "Pin the path density, and compare paths before eigenvalues"

    The published record was not produced with a single
    `bands_kpoints_distance`, so its density varies from structure to structure.
    Take it from the published k-point coordinates rather than assuming a
    protocol default.

    Two paths that differ in sampling density are not comparable row by row even
    when both are correct. Compare `kx, ky, kz` and the high-symmetry `label`
    first; only then compare eigenvalues.

## Explore the published data

The record is self-contained — it carries the cell each calculation ran on, so
you never have to re-derive a structure from MC3D to work with it.

`example.py` in the record loads the summary, the structures and the bands
straight out of the tarballs and plots one band structure:

```bash
python example.py                 # the summary, then a plotted band structure
python example.py 100115          # one structure by source_db_id
```

`CIF_files/<source_db_id>.cif` is the primitive cell the bands were computed on,
not a conventional cell that then needs standardising.
`bands/<source_db_id>.csv` carries `kx, ky, kz` and `label` alongside the
eigenvalues, so a regenerated path can be checked point for point against the
published one.

`metallicity` and `band_gap_ev` are both derived from the published eigenvalues
and Fermi energy, so neither has to be taken on trust. The threshold used for
`metallicity` is a plain zero — see
[the record page](../published-records.md#metallicity-is-a-zero-threshold-not-a-physical-one)
for why no thresholded label is published, and pick your own cut on
`band_gap_ev` if your work needs one. The
[record page](../published-records.md#quantum-espresso-nscf-band-structures)
also explains how the k-point coordinates were reconstructed and on what
evidence each one was accepted.
