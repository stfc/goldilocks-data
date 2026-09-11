# Install goldilocks-data

The package holds the reusable mechanics: the k-mesh ladder, AiiDA submission
and de-duplication, convergence labelling, and the PSDI publishing command. It
does not need AiiDA to be installed unless you are actually submitting
calculations.

`uv` manages every environment here. Do not use `pip`.

## From the repository

This is what you want for campaign work, because the campaign scripts and the
notebook live in the repository too.

```bash
git clone https://github.com/stfc/goldilocks-data.git
cd goldilocks-data
uv sync
uv run goldilocks-data --help
```

`uv sync` creates `.venv` and installs the package in editable mode. Prefix
commands with `uv run` and the environment is used without activating anything.

## As a dependency of another project

The package is not on PyPI. Add it from GitHub:

```bash
uv add "goldilocks-data @ git+https://github.com/stfc/goldilocks-data"
```

Pin a commit or a tag for anything reproducible:

```bash
uv add "goldilocks-data @ git+https://github.com/stfc/goldilocks-data@v0.1.0"
```

## What comes with the base install

`pandas` and `pymatgen`.

`pymatgen` is a plain dependency and not an extra on purpose. The k-mesh ladder
reads the reciprocal lattice throughout and reduces every rung by symmetry, so
a caller needs a real pymatgen `Structure` either way — and the reduction never
falls back to an unreduced count, because a wrong `n_reduced_kpoints` is an
ordinary-looking integer. See [k-mesh quantities](../reference/kmesh.md).

That base is enough to build a ladder, label convergence, and read a published
record.

## Optional extras

| Extra | Installs | Needed for |
| --- | --- | --- |
| `aiida` | `aiida-core`, `aiida-quantumespresso` | submitting sweeps, querying the database, remote-folder cleanup |
| `kmesh` | `pyarrow` | reading the parquet campaign-record snapshots |
| `publish` | `data-collections-api` | `goldilocks-data publish`, the PSDI deposit command |

Add them to a clone with `--extra`:

```bash
uv sync --extra aiida --extra kmesh
```

Or run a single command with the extras it needs and nothing else:

```bash
uv run --extra aiida --extra kmesh python \
  campaigns/qe/kpoints/scripts/monitor.py --once --cif-dir /path/to/CIF_files
```

!!! note "The `kmesh` extra no longer matches its name"

    It once carried the k-mesh machinery. That moved into the base install when
    `pymatgen` did, and what is left is the parquet reader the campaign scripts
    need. The name is kept because campaign commands and shell history use it.

The `aiida` extra installs the Python side only. A working AiiDA profile,
services, and a configured computer and code are a separate setup — see
[Install AiiDA on macOS](aiida-macos.md) and
[Add Quantum ESPRESSO and SCARF](qe-scarf.md).

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check src tests campaigns/qe/kpoints/scripts
uv run ruff format src tests campaigns/qe/kpoints/scripts
```

The docs site:

```bash
uv sync --group docs
uv run mkdocs serve          # http://127.0.0.1:8000
uv run mkdocs build --strict
```

`--strict` turns a broken internal link into a build failure, which is what CI
runs.

## Check it works

```bash
uv run python -c "
from pymatgen.core import Lattice, Structure
from goldilocks_data.kmesh import build_gamma_kmesh_entries

silicon = Structure.from_spacegroup('Fd-3m', Lattice.cubic(5.43), ['Si'], [[0, 0, 0]])
entry = build_gamma_kmesh_entries(silicon, min_k_distance=0.2)[-1]
print(entry.kindex, entry.mesh, entry.n_reduced_kpoints)
"
```

Diamond silicon prints `5 (5, 5, 5) 10`: rung 5 of its ladder, a 125-point mesh
that symmetry reduces to 10. A `10` here means the reduction ran.
