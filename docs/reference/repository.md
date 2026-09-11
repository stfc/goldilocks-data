# Repository layout

The repository holds reusable software and the public documentation. It does not
hold datasets, calculation output, or the tooling that drives a particular run.

```text
goldilocks-data/
├── src/
│   └── goldilocks_data/  reusable submission and analysis code
├── tests/                scientific and workflow regression tests
└── docs/                 this documentation site
```

## Ownership

| Location | Responsibility |
| --- | --- |
| `src/` | Mechanics shared across every run: submission, de-duplication, cleanup, k-mesh schedules, convergence labelling, publishing |
| `tests/` | Regression tests that depend on no private data |
| `docs/` | User-facing documentation built by MkDocs |

## What stays outside

A concrete run — its AiiDA group and profile, its controller
scripts, its analysis notebook, the dated tables it exports — is operational,
not reusable, and lives outside this repository along with the private CSV and
CIF paths it reads. What is published from it goes to
[PSDI](../published-records.md) as a citable record instead.

A private path must never reach the package API.

The package directory `src/goldilocks_data/codes/` contains Python types for
identifying DFT codes; it is unrelated to the DFT codes themselves.
