# QE SCF k-point convergence

These calculations determine the smallest gamma-inclusive k-point mesh at which
the total energy of a structure is stable.

Published as two records, from one body of calculations:
[`52713-55d86`](https://data-collections.psdi.ac.uk/records/52713-55d86), the
converged mesh per structure, and
[`mcpnq-g1j55`](https://data-collections.psdi.ac.uk/records/mcpnq-g1j55), the
full per-calculation output behind the paper.

## What was calculated

| Setting | Value |
| --- | --- |
| Code | Quantum ESPRESSO `pw.x` |
| Task | No-spin SCF |
| Functional | PBEsol |
| Pseudopotentials | SSSP, for both published records |
| Schedule | The 1-based gamma-inclusive k-mesh ladder, floor `min_k_distance = 0.03` Å⁻¹ |
| Smearing | `degauss = 0.01` Ry |
| Criterion | Energy only, per atom, over a tail of at least three meshes |

## Reproduce it

Running these yourself means submitting one SCF per rung of a structure's
ladder and labelling the result. You need AiiDA with a configured
`pw.x` code and a pseudopotential family.

```bash
uv sync --extra aiida
```

### Submit the sweep

```python
from aiida import load_profile
from pymatgen.core import Structure

from goldilocks_data.aiida import AiidaScfConfig, submit_scf_sweeps
from goldilocks_data.kmesh import kindex_points
from goldilocks_data.sweeps import ScfSweepSpec

load_profile()

config = AiidaScfConfig(
    code_label="pw-7.5@your-computer",          # your AiiDA code
    pseudo_family_label="SSSP/1.3/PBEsol/efficiency",
    group_label="my-kpoint-sweep",              # every node lands in this group
    degauss_ry=0.01,
)

structure = Structure.from_file("100115.cif")

summary = submit_scf_sweeps(
    [
        ScfSweepSpec(
            source_db_id="100115",
            structure=structure,
            points=kindex_points(structure, 1, 12),   # rungs 1 to 12, 1-based
        )
    ],
    config,
)
print(summary.submitted)
```

`kindex_points` builds the rungs; each carries its mesh, `k_pra` and
`n_reduced_kpoints` as node extras, so a finished group can be analysed without
re-deriving anything. Submission is idempotent: a rung already in the group is
skipped, so re-running extends a sweep rather than duplicating it.

Rung 12 is an arbitrary stopping point. Extend until the tail converges, and
remember that the ladder is bounded by `min_k_distance`, not by a k-point count
— see [k-mesh quantities](../reference/kmesh.md).

### Label the convergence

Collect `kindex`, `energy` and `energy_per_atom` for each finished calculation
into a DataFrame, then:

```python
from goldilocks_data.analysis.convergence import ConvergenceThresholds, build_convergence_table

table = build_convergence_table(
    records,
    ConvergenceThresholds(medium_mev_per_atom=5.0, well_mev_per_atom=3.0, ultra_mev_per_atom=1.0),
)
```

The published records used 5 / 3 / 1 meV per atom; the class defaults are
10 / 5 / 1, so pass them explicitly. See
[convergence criteria](../reference/convergence.md).

!!! warning "The criterion is the whole tail, not three points"

    `52713-55d86`'s README describes the converged mesh as the first of *three
    consecutive* meshes agreeing within 1 meV per atom. The code is stricter
    than that wording: the oscillation is `max - min` over **every** rung from
    that point to the end of the sweep, with at least three rungs required. A
    reimplementation that stops after checking three will label some structures
    converged that these calculations did not.

    The record is not being amended. A published record keeps the wording it
    was published with, so that a citation stays fixed; this page is where the
    two are reconciled, and the labels in the record are the ones the code
    above produces.

### Clean up as you go

A k-mesh sweep leaves a lot of remote scratch behind. The CLI keeps the inputs,
outputs, XML and scheduler logs and deletes the rest:

```bash
goldilocks-data cleanup-qe-scf --group-label my-kpoint-sweep            # dry run
goldilocks-data cleanup-qe-scf --group-label my-kpoint-sweep --execute
```

## Explore the published data

Reproduction is not required to use the records. `k_index` is reproducible from
the structure alone, with no calculation at all, provided you use the same
floor:

```python
from pymatgen.core import Structure
from goldilocks_data.kmesh import build_gamma_kmesh_entries

entries = build_gamma_kmesh_entries(Structure.from_file("100115.cif"))
print([(e.kindex, e.mesh) for e in entries[:5]])
```

That is enough to turn a published `k_index` back into a mesh, or to check one.
A `k_index` computed under a different floor is comparable only where the two
ranges overlap.
