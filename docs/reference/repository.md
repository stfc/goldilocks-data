# Repository layout

The top-level directories separate reusable software from concrete data
campaigns and public documentation.

```text
goldilocks-data/
├── campaigns/
│   └── qe/kpoints/       task README, settings, scripts, notebook, results
├── src/
│   └── goldilocks_data/  reusable submission and analysis code
├── tests/                scientific and workflow regression tests
└── docs/                 this documentation site
```

## Ownership

| Location | Responsibility |
| --- | --- |
| `campaigns/` | Everything needed to reproduce or inspect one concrete dataset |
| `src/` | Mechanics shared across campaigns: submission, de-duplication, cleanup, schedules, and convergence |
| `tests/` | Synthetic regression tests that do not depend on private data |
| `docs/` | User-facing documentation built by MkDocs |

The package directory `src/goldilocks_data/codes/` contains Python types for
identifying DFT codes. It is distinct from `campaigns/`, which contains
operational data-generation projects.
