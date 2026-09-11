# goldilocks-data

Reusable data-side tooling for Goldilocks DFT sweeps.

User documentation: <https://stfc.github.io/goldilocks-data/>

`goldilocks-data` is the execution and analysis layer around AiiDA-backed DFT
calculations. It keeps reusable mechanics in a Python package while leaving
dataset-specific decisions in local scripts and notebooks outside the
repository.

## Repository map

AiiDA is the only execution engine. The extensible axes are:

- **code**: `qe`, `vasp`, `cp2k`, `castep`
- **intent**: `scf`, `nscf`, `relax`, `phonon`, `md`, `tddft`, `dft_u`
- **sweep axis**: `kindex`, `pp`, `code`, `spin_type`, `nspin`, `magneticity`,
  `soc`, `smearing`, `cutoff`

```text
src/               # reusable Python mechanics
tests/             # regression tests, no private data
docs/              # GitHub Pages site
```

The reusable package is organised around these boundaries:

```text
src/goldilocks_data/
  codes/          # DFT code identifiers
  intents/        # calculation intent identifiers
  sweeps/         # SweepPoint, AiidaJobSpec, kmesh/kindex helpers
  aiida/          # submit orchestration, registry, cleanup, builder adapters
  analysis/       # convergence and result analysis
```

Current builder support is QE `pw.x` SCF. The submit orchestration is already
generic: new codes or calculation intents should add an AiiDA builder adapter
and register it by `(DftCode, CalculationIntent)`.

## Boundary

The package owns reusable mechanics:

- gamma-inclusive kindex schedules
- explicit `source_db_id + structure + sweep points` AiiDA submission
- AiiDA group/extras de-duplication
- persistent failed-source records
- convergence labelling from finished energies
- finished remote-folder cleanup

Local notebooks or scripts own dataset-specific decisions:

- reading private CSV files
- reading local CIF directories
- deciding which `source_db_id` values belong in a batch
- translating historical convergence rows into a new `kindex_max`

## Submit Example

```python
from goldilocks_data.aiida import AiidaScfConfig, submit_scf_sweeps
from goldilocks_data.kmesh import kindex_points
from goldilocks_data.sweeps import ScfSweepSpec

config = AiidaScfConfig(
    code_label="pw-7.5@your-computer",
    pseudo_family_label="SSSP/1.3/PBEsol/efficiency",
    group_label="my-kpoint-sweep",
)

summary = submit_scf_sweeps(
    [
        ScfSweepSpec(
            source_db_id="100115",
            structure=structure,
            points=kindex_points(structure, 1, 22),  # rungs are 1-based
        )
    ],
    config,
)
```

For future non-QE or non-SCF workflows, use `AiidaJobSpec` directly with an
explicit `DftCode` and `CalculationIntent` once a matching builder adapter
exists.

## Cleanup

Dry-run cleanup:

```bash
goldilocks-data cleanup-qe-scf --group-label my-kpoint-sweep
```

Delete non-retained files:

```bash
goldilocks-data cleanup-qe-scf --group-label my-kpoint-sweep --execute
```

Cleanup keeps `aiida.in`, `aiida.out`, XML files, submit scripts, and scheduler
logs. Per-remote failures are collected and do not stop the whole cleanup run.

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check src tests
```

Build the documentation site:

```bash
uv sync --group docs
uv run mkdocs build --strict
```
