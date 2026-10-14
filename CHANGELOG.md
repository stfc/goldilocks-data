# Changelog

## [Unreleased]

## [0.1.0](https://github.com/stfc/goldilocks-data/releases/tag/v0.1.0) — 2026-10-14

First release. The package is not on PyPI; install it from the tag:

```bash
uv add "goldilocks-data @ git+https://github.com/stfc/goldilocks-data@v0.1.0"
```

### Generate

- `goldilocks_data.kmesh` builds the Γ-inclusive k-mesh ladder for a structure.
  `k_index` is 1-based, rung 1 is the Γ-only `(1, 1, 1)` mesh, and enumeration
  stops at the resolution floor `min_k_distance` (default 0.03 Å⁻¹). Every rung
  is reduced by symmetry; the reduction fails rather than fall back to an
  unreduced count.
- `submit_scf_sweeps` submits Quantum ESPRESSO `pw.x` SCF sweeps through AiiDA
  from an explicit `source_db_id`, structure and list of sweep points. Points
  already in the AiiDA group are skipped, and a source that fails to build or
  submit is recorded in the group so a later batch can exclude it
  (`failed_source_ids`).
- Submission is keyed by `(DftCode, CalculationIntent)`, so another code or
  intent adds a builder adapter rather than a new submit path (`AiidaJobSpec`,
  `submit_jobs`). QE SCF is the only adapter in this release.
- `goldilocks-data cleanup-qe-scf` deletes non-retained files from finished
  remote folders, keeping inputs, outputs, XML, submit scripts and scheduler
  logs. It is a dry run unless given `--execute`.

### Analyse

- `build_convergence_table` and `summarize_convergence` label each structure's
  k-index convergence from finished total energies: medium, well and ultra at
  10, 5 and 1 meV/atom of energy oscillation over a tail of at least three
  points.
- `plan_well_not_ultra_extensions` plans the next k-index rungs for structures
  that reached well but not ultra.

### Publish

- `goldilocks-data publish` validates a dataset deposit offline — file
  checksums and a `dataset.json` that declares every column — then creates a
  PSDI Data Collections draft and stops. Submission for review stays a human
  decision, and a failed upload deletes its partial draft.

### Documentation

- The site at <https://stfc.github.io/goldilocks-data/> documents three records
  published on PSDI Data Collections — `52713-55d86` (converged k-mesh per
  structure), `mcpnq-g1j55` (full per-calculation output) and `r3byg-xp284`
  (nscf band structures) — with the settings and a reproduction script for
  each set of calculations.
