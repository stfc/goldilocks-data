from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SHA256SUMS = "SHA256SUMS"
README = "README.md"
DATASET_RECORD = "dataset.json"
METADATA = "metadata.json"

#: Files that are read from the deposit but never listed in SHA256SUMS.
#: SHA256SUMS cannot meaningfully digest itself, and metadata.json is not part
#: of the payload at all.
UNLISTED_FILES = frozenset({SHA256SUMS, METADATA})

#: Files read from the deposit but not uploaded. metadata.json is what PSDI is
#: *told*, not a file it receives: its contents become the record's own title,
#: creators, description and rights through the draft update. SHA256SUMS is the
#: local integrity manifest — every digest in it is re-derived before upload, and
#: PSDI stores its own checksum per file once the record exists.
LOCAL_ONLY_FILES = frozenset({METADATA, SHA256SUMS})

_DIGEST_LENGTH = 64


@dataclass(frozen=True, slots=True)
class Deposit:
    """A validated deposit directory ready for one PSDI draft.

    ``files`` maps the upload name to a local path, and holds the payload only:
    ``metadata.json`` is sent as the draft's metadata instead, and ``SHA256SUMS``
    stays local. Every payload digest in ``SHA256SUMS`` has been re-derived from
    disk before this object exists.
    """

    directory: Path
    metadata: dict[str, Any]
    record: dict[str, Any] | None
    community: str
    files: dict[str, Path]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256sums(text: str) -> dict[str, str]:
    """Parse ``shasum -a 256`` output into ``{name: digest}``.

    The format is ``<64 hex chars><two spaces><name>``. Binary-mode lines use
    ``" *"`` instead and are accepted. Blank lines are ignored.
    """

    sums: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator:
            digest, separator, name = line.partition(" *")
        name = name.strip()
        if not separator or not name:
            raise ValueError(f"{SHA256SUMS} line {number} is not '<digest>  <name>': {line!r}")
        digest = digest.strip().lower()
        if len(digest) != _DIGEST_LENGTH or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"{SHA256SUMS} line {number} has no SHA-256 digest: {digest!r}")
        if name in sums:
            raise ValueError(f"{SHA256SUMS} lists {name} twice")
        if Path(name).name != name:
            raise ValueError(f"{SHA256SUMS} entry {name!r} must be a bare filename")
        sums[name] = digest
    if not sums:
        raise ValueError(f"{SHA256SUMS} lists no files")
    return sums


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def validate_dataset_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate ``dataset.json``: the schema a consumer reads instead of guessing.

    A dataset whose column semantics live only in prose cannot be reproduced. The
    ``k_index`` column in the first Goldilocks dataset had to be recomputed
    wholesale for exactly that reason, so the fields below are required rather
    than advisory.
    """

    if record.get("schema_version") != 1:
        raise ValueError(f"{DATASET_RECORD} schema_version must be 1")

    for field_name in ("dataset", "version"):
        value = record.get(field_name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{DATASET_RECORD} {field_name} must be a non-empty string")

    rows = record.get("rows")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
        raise ValueError(f"{DATASET_RECORD} rows must be a non-negative integer")

    columns = record.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError(f"{DATASET_RECORD} columns must be a non-empty list")
    seen: set[str] = set()
    for column in columns:
        if not isinstance(column, dict):
            raise ValueError(f"{DATASET_RECORD} each column must be an object")
        name = column.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{DATASET_RECORD} each column needs a non-empty name")
        if name in seen:
            raise ValueError(f"{DATASET_RECORD} lists column {name} twice")
        seen.add(name)
        if not isinstance(column.get("dtype"), str) or not column["dtype"]:
            raise ValueError(f"{DATASET_RECORD} column {name} needs a dtype")

    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError(f"{DATASET_RECORD} provenance must be a non-empty object")

    conventions = record.get("conventions")
    if conventions is not None and not isinstance(conventions, dict):
        raise ValueError(f"{DATASET_RECORD} conventions must be an object when present")

    return record


def load_deposit(directory: Path, *, community: str) -> Deposit:
    """Validate a deposit directory completely, before any network call.

    Refuses on a missing descriptor, a malformed dataset record, a digest or size
    mismatch, a file listed but absent, or a payload file present on disk yet
    absent from ``SHA256SUMS`` — an unlisted file would be uploaded with nothing
    attesting to its content.
    """

    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    if not community:
        raise ValueError("community must be a non-empty string")

    metadata = _load_json(directory / METADATA)
    # dataset.json is optional: with one, a consumer checks the schema instead
    # of reading prose; without one, the column semantics live only in README.md.
    record_path = directory / DATASET_RECORD
    record = validate_dataset_record(_load_json(record_path)) if record_path.is_file() else None

    readme = directory / README
    if not readme.is_file():
        raise FileNotFoundError(readme)

    sums_path = directory / SHA256SUMS
    if not sums_path.is_file():
        raise FileNotFoundError(sums_path)
    sums = parse_sha256sums(sums_path.read_text())

    on_disk = {path.name for path in directory.iterdir() if path.is_file()}
    unlisted = sorted(on_disk - set(sums) - UNLISTED_FILES)
    if unlisted:
        names = ", ".join(unlisted)
        raise ValueError(f"files are present but absent from {SHA256SUMS}: {names}")

    files: dict[str, Path] = {}
    for name, expected in sums.items():
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"{name} has SHA-256 {actual}; {SHA256SUMS} expects {expected}")
        files[name] = path

    for name in UNLISTED_FILES - LOCAL_ONLY_FILES:
        files[name] = directory / name

    default_preview = metadata.get("files", {}).get("default_preview")
    if default_preview is not None and default_preview not in files:
        raise ValueError(f"files.default_preview is not an upload file: {default_preview}")

    return Deposit(
        directory=directory,
        metadata=metadata,
        record=record,
        community=community,
        files=files,
    )
