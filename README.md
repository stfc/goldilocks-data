# goldilocks-data

Reusable data-side tooling for Goldilocks DFT sweeps.

`goldilocks-data` is the execution and analysis layer around AiiDA-backed DFT
campaigns. It keeps reusable mechanics in a Python package while leaving
dataset-specific decisions in notebooks or local scripts.

## Repository map

AiiDA is the only execution engine. The extensible axes are:

- **code**: `qe`, `vasp`, `cp2k`, `castep`
- **intent**: `scf`, `nscf`, `relax`, `phonon`, `md`, `tddft`, `dft_u`
- **sweep axis**: `kindex`, `pp`, `code`, `spin_type`, `nspin`, `magneticity`,
  `soc`, `smearing`, `cutoff`

Campaign documentation is organised first by code and then by task:

```text
codes/
  qe/
    kpoints/       # setup, scripts, notebook, and result snapshot
src/               # reusable Python mechanics shared by campaigns
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
from goldilocks_data.sweeps import ScfSweepSpec
from goldilocks_data.sweeps.kindex import kindex_points

config = AiidaScfConfig(
    code_label="qe-7.5-pw-admin@scarf",
    pseudo_family_label="PseudoDojo/0.4/PBEsol/SR/standard/upf",
    group_label="goldilocks/qe-scf/nospin/pseudodojo",
)

summary = submit_scf_sweeps(
    [
        ScfSweepSpec(
            source_db_id="100115",
            structure=structure,
            points=kindex_points(structure, 0, 22),
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
goldilocks-data cleanup-qe-scf --group-label goldilocks/qe-scf/nospin/pseudodojo
```

Delete non-retained files:

```bash
goldilocks-data cleanup-qe-scf --group-label goldilocks/qe-scf/nospin/pseudodojo --execute
```

Cleanup keeps `aiida.in`, `aiida.out`, XML files, submit scripts, and scheduler
logs. Per-remote failures are collected and do not stop the whole cleanup run.

## Current campaign

This repository also contains a local controller script for the current
Goldilocks no-spin QE SCF kindex campaign. It deliberately keeps private CSV
and CIF paths outside the reusable package API.

Preview the next cycle:

```bash
uv run --extra aiida --extra kmesh python codes/qe/kpoints/scripts/monitor.py --once --cif-dir /path/to/CIF_files
```

Run one real cycle:

```bash
uv run --extra aiida --extra kmesh python codes/qe/kpoints/scripts/monitor.py --execute --cif-dir /path/to/CIF_files
```

Each cycle:

1. loads a fresh AiiDA profile in a fresh Python process
2. checks the number of active WorkChains
3. cleans finished remote folders up to `--cleanup-limit`
4. selects `source_db_id` values that are not permanently failed and do not yet have the
   full `kindex=0..kindex_max` range
5. submits only missing kindex points, using AiiDA extras for de-duplication

See [`codes/qe/kpoints/README.md`](codes/qe/kpoints/README.md) for plugin setup,
campaign settings, analysis, and the result snapshot.

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check src tests codes/qe/kpoints/scripts
```
