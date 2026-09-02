# QE SCF k-point convergence

This task determines the smallest gamma-inclusive k-point mesh at which the
total energy is converged for each structure. It currently contains the
PseudoDojo PBEsol campaign and the SSSP comparison analysis.

## Layout

```text
kpoints/
  campaign.yaml       human-readable campaign configuration
  scripts/            initial submission, extension, and monitoring
  notebooks/          curated analysis and visualisation
  results/            snapshot, summary, and provenance manifest
```

## Install and configure

The repository uses `uv`. Install the package with its AiiDA and k-mesh
dependencies:

```bash
uv sync --group dev --extra aiida --extra kmesh
```

Configure an AiiDA profile, a Quantum ESPRESSO `pw.x` code, and the required
pseudopotential family. The campaign defaults are recorded in
[`campaign.yaml`](campaign.yaml); command-line options can override them.

## Submission strategy

The extension loop submits three new gamma-inclusive kindex points for each
eligible structure. It submits at most 50 WorkChains per cycle, waits 15
minutes after the cycle finishes, then re-evaluates the current AiiDA state.
Submission is always a dry run unless `--execute` is present.

Preview one cycle:

```bash
uv run --extra aiida --extra kmesh python codes/qe/kpoints/scripts/monitor.py \
  --once --cif-dir /path/to/CIF_files
```

Run the periodic submission loop:

```bash
uv run --extra aiida --extra kmesh python codes/qe/kpoints/scripts/monitor.py \
  --execute --cif-dir /path/to/CIF_files
```

The monitor calls `extend.py` in a fresh process. Stop it with `Ctrl-C`.
`submit_initial.py` is for the original seed campaign and additionally needs
the historical convergence summary files; run `--help` for its full interface.

## Convergence definition

Energy convergence is evaluated per atom over a tail of at least three points:

- medium: 5 meV/atom
- well: 3 meV/atom
- ultra: 1 meV/atom

Kindex numbering follows the current gamma-inclusive schedule. The selected
index maps deterministically to a mesh for a given structure.

## Analysis and data

Open [`notebooks/analysis.ipynb`](notebooks/analysis.ipynb) to rebuild the
tables, compare PseudoDojo with SSSP, and visualise the non-identical kindex
results. Snapshot files are described in [`results/README.md`](results/README.md).

The AiiDA database remains the authoritative calculation record. Exported
tables are analysis snapshots and carry their profile, group, thresholds, and
generation time in metadata.
