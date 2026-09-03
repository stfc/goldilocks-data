---
name: write-docs
description: Write or update goldilocks-data documentation. Use when changing README.md, the MkDocs site under docs/, campaign READMEs, or the mkdocs.yml nav.
---

# Write Docs

Use this skill for project documentation changes.

## Goals

- Keep docs current with the branch.
- Prefer terse, direct wording.
- Document actual behaviour only. Do not describe a planned CLI or API as implemented.
- Keep one canonical API path. Do not add compatibility notes unless backward compatibility was explicitly requested.

## Files

- `README.md` — repository map, the package/campaign boundary, submit and cleanup examples, development commands.
- `docs/` — the published MkDocs site, at <https://stfc.github.io/goldilocks-data/>:

  ```text
  docs/index.md                    what the repository does, where to go
  docs/installation/               environment setup (AiiDA on macOS, QE on SCARF)
  docs/campaigns/                  one page per campaign, organised by code then task
  docs/results.md                  how to use the exported records
  docs/reference/repository.md     repository layout
  docs/reference/convergence.md    the convergence criteria
  ```

- `campaigns/<code>/<task>/README.md` — plugin setup, campaign settings, analysis, result snapshot.
- `AGENTS.md` — durable project rules for future agents.

A new page must be added to the `nav` in `mkdocs.yml`, or `--strict` fails the build.

## Workflow

1. Check the current code before writing.

   ```bash
   find src/goldilocks_data -maxdepth 2 -type f | sort
   rg "def |class " src/goldilocks_data tests
   rg "project.scripts" -A3 pyproject.toml
   ```

2. Keep the package/campaign boundary straight. The package owns reusable
   mechanics; notebooks and campaign scripts own dataset-specific decisions —
   private CSV paths, local CIF directories, which `source_db_id` values belong
   in a batch. Do not document a private path as part of the package API.

3. Keep package ownership consistent.

   ```text
   codes/      -> DFT code identifiers
   intents/    -> calculation intent identifiers
   sweeps/     -> SweepPoint, AiidaJobSpec, kmesh/kindex helpers
   aiida/      -> submit orchestration, registry, cleanup, builder adapters
   analysis/   -> convergence and result analysis
   cli.py      -> thin command wrappers
   ```

4. Run checks before committing.

   ```bash
   uv run ruff check src tests campaigns/qe/kpoints/scripts
   uv run ruff format --check src tests campaigns/qe/kpoints/scripts
   uv run pytest -q
   uv sync --group docs && uv run mkdocs build --strict
   ```

## Style

- Be terse.
- Use short sections.
- Use examples over prose.
- Avoid roadmap promises in user-facing docs.
- If something is future work, say `not implemented yet`.
- Do not use flowery language.

## Common mistakes

- Documenting a planned CLI command as a current one. The only console script is
  `goldilocks-data`.
- Adding a page without adding it to the `mkdocs.yml` nav, which breaks
  `mkdocs build --strict`.
- Writing a private CSV or CIF path into package documentation.
- Claiming builder support beyond QE `pw.x` SCF.
- Adding compatibility aliases or migration paths without an explicit request.
