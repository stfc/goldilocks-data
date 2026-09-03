# QE SCF k-point convergence

This campaign determines the smallest gamma-inclusive k-point mesh at which
the total energy is stable for each structure.

## Campaign definition

| Setting | Value |
| --- | --- |
| Code | Quantum ESPRESSO `pw.x` |
| Task | No-spin SCF |
| Pseudopotentials | PseudoDojo 0.4 PBEsol SR standard |
| Schedule | Distinct gamma-inclusive meshes indexed by kindex |
| Extension | Three new kindex points per structure |
| Capacity | At most 50 active or newly submitted WorkChains |
| Check interval | 15 minutes |

The machine-readable settings live in
[`campaign.yaml`](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/campaign.yaml).

## How one cycle works

1. load the saved analysis snapshot;
2. query AiiDA for active and already-existing WorkChains;
3. select clean structures that reached `well` but not `ultra`;
4. allocate complete groups of three new kindex points within the capacity;
5. submit only when `--execute` is present;
6. wait 15 minutes and query AiiDA again.

The snapshot selects the candidate cohort. Live AiiDA queries prevent duplicate
submissions and enforce the active-workchain limit.

## Preview one cycle

```bash
uv run --extra aiida --extra kmesh python \
  campaigns/qe/kpoints/scripts/monitor.py \
  --once \
  --cif-dir /path/to/CIF_files
```

## Run the controller

```bash
uv run --extra aiida --extra kmesh python \
  campaigns/qe/kpoints/scripts/monitor.py \
  --execute \
  --cif-dir /path/to/CIF_files
```

Stop the loop with `Ctrl-C`. The controller finishes the current synchronous
cycle before waiting for the next one.

!!! warning

    Always run a one-cycle dry run after changing the profile, group, pseudo
    family, snapshot, or source structures.

## Source files

- [Task README](https://github.com/stfc/goldilocks-data/tree/main/campaigns/qe/kpoints)
- [Submission scripts](https://github.com/stfc/goldilocks-data/tree/main/campaigns/qe/kpoints/scripts)
- [Analysis notebook](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/notebooks/analysis.ipynb)
- [Result manifest](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/results/manifest.json)

Continue with [Results](../results.md).
