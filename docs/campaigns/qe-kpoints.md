# QE SCF k-point convergence

This campaign determines the smallest gamma-inclusive k-point mesh at which the
total energy of a structure is stable.

Published as two records, from one body of calculations:
[`52713-55d86`](https://data-collections.psdi.ac.uk/records/52713-55d86), the
converged mesh per structure, and
[`mcpnq-g1j55`](https://data-collections.psdi.ac.uk/records/mcpnq-g1j55), the
full per-calculation output behind the paper.

## Campaign definition

| Setting | Value |
| --- | --- |
| Code | Quantum ESPRESSO `pw.x` |
| Task | No-spin SCF |
| Functional | PBEsol |
| Pseudopotentials | SSSP, for both published records |
| Schedule | The 1-based gamma-inclusive k-mesh ladder, floor `min_k_distance = 0.03` Å⁻¹ |
| Criterion | Energy only, per atom, over a tail of at least three meshes |

The pseudopotential family is the one axis that moves between runs of this
campaign; everything else above defines it. The machine-readable settings of the
current run live in
[`campaign.yaml`](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/campaign.yaml),
so read the pseudopotential family from the record you are reproducing rather
than from that file.

## Reproducing it

1. **Take the structures from the record.** `CIF_files/<source_db_id>.cif`, and
   `source_db_id` is the join key to every table.

2. **Rebuild the ladder.** `k_index` is reproducible from the structure alone —
   no calculation needed — provided you use the same floor:

    ```python
    from pymatgen.core import Structure
    from goldilocks_data.kmesh import build_gamma_kmesh_entries

    entries = build_gamma_kmesh_entries(Structure.from_file("100115.cif"))
    print([(e.kindex, e.mesh) for e in entries[:5]])
    ```

    A `k_index` computed under a different floor is comparable only where the
    two ranges overlap. See [k-mesh quantities](../reference/kmesh.md).

3. **Run the sweep.** One SCF per rung, unshifted mesh, holding everything else
   fixed. The package submits these through AiiDA with the structure identifier
   and the sweep point recorded on each node — see the submit example in the
   [repository README](https://github.com/stfc/goldilocks-data#submit-example).

4. **Label convergence.** `goldilocks_data.analysis.convergence` takes the
   finished energies and returns the smallest rung whose remaining tail holds
   within the threshold. See [convergence criteria](../reference/convergence.md).

!!! warning "The criterion is the whole tail, not three points"

    `52713-55d86`'s README describes the converged mesh as the first of *three
    consecutive* meshes agreeing within 1 meV per atom. The code is stricter
    than that wording: the oscillation is `max - min` over **every** rung from
    that point to the end of the sweep, with at least three rungs required. A
    reimplementation that stops after checking three will label some structures
    converged that this campaign did not.

## Running it at scale

A full campaign is a loop: submit a bounded number of WorkChains, wait, query
AiiDA for what finished, extend the structures that have not converged yet.
`monitor.py` does that. Preview one cycle:

```bash
uv run --extra aiida --extra kmesh python \
  campaigns/qe/kpoints/scripts/monitor.py \
  --once \
  --cif-dir /path/to/CIF_files
```

Submit for real by replacing `--once` with `--execute`. Stop the loop with
`Ctrl-C`; it finishes the current cycle first.

Live AiiDA queries, not a local file, are what prevent duplicate submissions and
enforce the active-workchain limit.

!!! warning

    Always run a one-cycle dry run after changing the profile, group, pseudo
    family, or source structures.

## Source files

- [Task README](https://github.com/stfc/goldilocks-data/tree/main/campaigns/qe/kpoints)
- [Submission scripts](https://github.com/stfc/goldilocks-data/tree/main/campaigns/qe/kpoints/scripts)
