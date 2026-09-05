# goldilocks-data

The execution and analysis layer around AiiDA-backed DFT campaigns.

## What goldilocks-data Does

Three jobs, in order:

1. **Generate** — submit parameter sweeps through AiiDA with stable structure
   identifiers and calculation provenance.
2. **Analyse** — apply explicit convergence criteria and find the smallest
   acceptable input for each structure.
3. **Publish** — export documented snapshots for research and model training.

AiiDA is the only execution engine. The extensible axes are:

- **code**: `qe`, `vasp`, `cp2k`, `castep`
- **intent**: `scf`, `nscf`, `relax`, `phonon`, `md`, `tddft`, `dft_u`
- **sweep axis**: `kindex`, `pp`, `code`, `spin_type`, `nspin`, `magneticity`,
  `soc`, `smearing`, `cutoff`

Current builder support is QE `pw.x` SCF. Submit orchestration is already
generic: a new code or intent adds an AiiDA builder adapter and registers it by
`(DftCode, CalculationIntent)`.

## Ecosystem Position

`goldilocks-data` → `goldilocks-ml` → `goldilocks-core`

- **goldilocks-data** produces convergence records from real calculations
- **goldilocks-ml** trains models on those records and publishes versioned artefacts
- **goldilocks-core** loads those artefacts and recommends inputs to end users

Model training does not belong here. End-user input generation does not belong
here.

## The Boundary That Matters

The package owns **reusable mechanics**:

- gamma-inclusive kindex schedules
- explicit `source_db_id + structure + sweep points` AiiDA submission
- AiiDA group/extras de-duplication
- persistent failed-source records
- convergence labelling from finished energies
- finished remote-folder cleanup

Notebooks and campaign scripts own **dataset-specific decisions**:

- reading private CSV files
- reading local CIF directories
- deciding which `source_db_id` values belong in a batch
- translating historical convergence rows into a new `kindex_max`

A private path must never reach the package API.

## Layout

```text
campaigns/<code>/<task>/   setup, scripts, notebook, result snapshot
src/goldilocks_data/
  codes/                   DFT code identifiers
  intents/                 calculation intent identifiers
  sweeps/                  SweepPoint, AiidaJobSpec, kmesh/kindex helpers
  aiida/                   submit orchestration, registry, cleanup, builders
  analysis/                convergence and result analysis
  cli.py                   thin command wrappers
docs/                      the published MkDocs site
```

## The k-index Convention

`k_index` is **1-based**, and rung 1 is the Γ-only `(1, 1, 1)` mesh. Each step up
is the next denser mesh the reciprocal lattice admits.

Record `d5ds2-64f16` was published before this and is 0-based. A published
record keeps the convention it was published with, so a consumer must read the
base from the record rather than assume it.

The ladder is built from the k-distances at which `ceil(|b_i| / k_distance)`
changes on any axis — that is, from `|b_i| / n`. The enumeration cap on `n` is
applied per axis, so axes with different `|b_i|` exhaust their breakpoints at
different k-distances: the ladder is a complete set of meshes only for
`k_distance >= max(|b_i|) / n_max`, and below that it silently skips reachable
meshes. Any recomputation or published `k_index` column must state the cap it
used.

This convention is shared with `goldilocks-core`. Changing it invalidates every
`k_index` value already recorded or trained on.

## Commands

```bash
uv sync --group dev                                        # install with dev deps
uv run pytest                                              # run tests
uv run ruff check src tests campaigns/qe/kpoints/scripts   # lint
uv run ruff format src tests campaigns/qe/kpoints/scripts  # format

uv sync --group docs && uv run mkdocs build --strict       # build the docs site
```

Campaign scripts need the optional extras explicitly:

```bash
uv run --extra aiida --extra kmesh python campaigns/qe/kpoints/scripts/monitor.py --once --cif-dir /path/to/CIF_files
```

Use `uv`, not `pip`.

## Code Style

- Ruff with `E`, `F`, `I` rules. Target Python 3.12.
- `from __future__ import annotations` at the top of every module.
- Dataclasses use `slots=True`. Frozen for immutable value objects.
- Domain modules, not generic buckets: no `helpers/`, no `utils/`, no `processing/`.
- Prefer one clear API over compatibility shims. Do not add legacy aliases,
  duplicate import paths, or wrapper modules unless the user explicitly asks
  for backward compatibility.
- `snake_case` for everything. No `CamelCase` except in string literals matching
  external formats.
- Type hints on public API surfaces. Internal functions can be looser.
- Docstrings: factual — what it does, what it returns, what it assumes.

## Tests

Tests live flat in `tests/`, one module per boundary. Prioritise scientific
behaviour over line coverage: a test that pins a convergence label or a kindex
schedule is worth more than one that exercises a wrapper.

## What Doesn't Belong Here

- Model training — that is goldilocks-ml.
- End-user input recommendation — that is goldilocks-core.
- AiiDA workflows for other people's campaigns, scheduler scripts.
- Jupyter notebooks — `notebooks/` is gitignored. Convert insights into tests.
- Large data or pseudo libraries. Private CSV and CIF paths stay outside the repo.

## Rules

- **Never push or merge directly to `main`.** All changes arrive through PRs.
- **A human opens every pull request and writes its body.** An agent prepares the
  branch and commits, then hands over the branch name, commit log, diff stat, and
  the issue number to close. An agent never authors or drafts a PR body and never
  runs `gh pr create` — the one exception is posting a body file the human wrote
  themselves. This rule lives here, not only in `make-a-pr`, because a rule kept
  in one repository's skill file is a rule that drifts.
- Every PR must close an issue (`Closes #N`).
- Track work status in GitHub Issues/PRs.
- Any GitHub issue, issue comment, or review comment written by an agent must
  explicitly say so and name the human it represents:
  `Written by an agent on behalf of <user>.` PR bodies are not on that list
  because an agent does not write them.

## Agent Workflow

Skills are in `.agents/skills/`, and `.claude/skills/` symlinks to them so Claude
Code and Codex read the same files: `catchup`, `plan`, `triage`, `review`,
`report`, `make-a-pr`, `write-a-test`, `write-docs`, `use-uv`, `dft-basics`,
`github-cli`, `skill-creator`.

- Start sustained work with `catchup`.
- Use `plan` for multi-step changes; keep the issue body as the current plan.
- Use `triage` when the issue board has drifted.
- Use `review` before PRs or after substantial changes.
- Use `report` for handoff/progress comments.
- Use `make-a-pr` only after implementation, tests, and review are ready.
