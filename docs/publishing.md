# Publish a dataset

Publishing puts a documented dataset snapshot in [PSDI Data
Collections](https://data-collections.psdi.ac.uk) with a permanent identifier
and a page describing it.

## Nothing happens by accident

- everything is checked locally first — the schema, the file digests, the
  metadata — before any request is made;
- a **draft** is created, never submitted. You submit it on the PSDI website
  after looking at how it turned out;
- uploading needs an explicit `--confirm-upload`, so it cannot happen from a
  mistyped command;
- the token is read from a file only its owner can read, and is never printed;
- if a step fails partway, the half-made draft is deleted rather than left
  lying around.

## A deposit directory

```text
README.md                  the record page a reader sees first
dataset.json               the machine-readable schema and provenance
metadata.json              PSDI discovery metadata
SHA256SUMS                 a digest per payload file
convergence_summary.csv    payload
CIF_files.tar.gz           payload
LICENSE                    payload
```

`SHA256SUMS` is the manifest, in the format `shasum -a 256` writes, so anyone
verifies the download with `shasum -a 256 -c SHA256SUMS` and needs no tooling
from this repository. Validation refuses a digest mismatch, a listed file that
is missing, and a payload file present on disk but absent from `SHA256SUMS` —
an unlisted file would be published with nothing attesting to its content.

### `dataset.json` is not optional

A dataset whose column semantics live only in prose cannot be reproduced. The
`k_index` column of the first Goldilocks dataset had to be recomputed wholesale
because its convention was recorded nowhere, so the schema, the dtypes, and any
convention a consumer must share are required fields:

```json
{
  "schema_version": 1,
  "dataset": "goldilocks-mc3d-nospin-scf-kmesh",
  "version": "v1",
  "rows": 17757,
  "columns": [{"name": "k_index", "dtype": "int", "description": "..."}],
  "conventions": {
    "kmesh_ladder": {"base": 0, "rung_0": "gamma_only", "max_kpoints_per_axis": 50}
  },
  "provenance": {"code": "quantum_espresso", "calculation": "scf", "spin": "none"}
}
```

## Validate

Install the extra and run the command with no token. It validates and prints
what *would* be uploaded, and makes no request:

```bash
uv sync --extra publish
uv run goldilocks-data publish --deposit-dir path/to/deposit
```

```text
dataset:   goldilocks-mc3d-nospin-scf-kmesh v1  rows=17757
community: data-to-knowledge
files:
  CIF_files.tar.gz  (12165457 bytes)
  ...
validated. re-run with --token-file and --confirm-upload to create a PSDI draft.
```

## Store the token

The token comes from the PSDI website. Put it in a file only you can read:

```bash
install -m 600 /dev/null ~/.config/goldilocks-data/psdi.token
$EDITOR ~/.config/goldilocks-data/psdi.token
```

A token file readable by group or other is refused rather than warned about.

## Create the draft

```bash
uv run goldilocks-data publish \
  --deposit-dir path/to/deposit \
  --token-file ~/.config/goldilocks-data/psdi.token \
  --confirm-upload
```

The draft is bound to the `data-to-knowledge` community and **is not
submitted**. Open it on PSDI, check the page, then submit it there.

If the upload fails, the partial draft is deleted. If that deletion also fails,
the error names the draft id so you can remove it by hand in the PSDI web
interface.
