from __future__ import annotations

import json
from pathlib import Path

import pytest

from goldilocks_data.publish import load_deposit, parse_sha256sums, validate_dataset_record


def test_load_deposit_accepts_a_consistent_directory(tmp_path: Path, write_deposit, community: str) -> None:
    deposit = load_deposit(write_deposit(tmp_path / "d"), community=community)

    assert deposit.community == community
    assert deposit.record["dataset"] == "goldilocks-mc3d-nospin-scf-kmesh"
    # Payload and descriptors are all uploaded; SHA256SUMS cannot digest itself.
    assert set(deposit.files) == {"data.csv", "README.md", "dataset.json", "SHA256SUMS", "metadata.json"}


def test_load_deposit_rejects_a_tampered_payload(tmp_path: Path, write_deposit, community: str) -> None:
    directory = write_deposit(tmp_path / "d")
    (directory / "data.csv").write_text("source_db_id,k_index\n1,0\n2,4\n")

    with pytest.raises(ValueError, match="data.csv has SHA-256"):
        load_deposit(directory, community=community)


def test_load_deposit_rejects_a_listed_file_that_is_missing(tmp_path: Path, write_deposit, community: str) -> None:
    directory = write_deposit(tmp_path / "d")
    (directory / "data.csv").unlink()

    with pytest.raises(FileNotFoundError):
        load_deposit(directory, community=community)


def test_load_deposit_rejects_a_payload_file_absent_from_the_digest_list(
    tmp_path: Path, write_deposit, community: str
) -> None:
    # An unlisted file would be published with nothing attesting to its content.
    directory = write_deposit(tmp_path / "d")
    (directory / "extra.csv").write_text("stray\n")

    with pytest.raises(ValueError, match="absent from SHA256SUMS: extra.csv"):
        load_deposit(directory, community=community)


def test_load_deposit_requires_a_readme(tmp_path: Path, write_deposit, community: str) -> None:
    directory = write_deposit(tmp_path / "d")
    (directory / "README.md").unlink()

    with pytest.raises(FileNotFoundError):
        load_deposit(directory, community=community)


def test_load_deposit_rejects_a_default_preview_that_is_not_uploaded(
    tmp_path: Path, write_deposit, community: str, psdi_metadata: dict
) -> None:
    directory = write_deposit(tmp_path / "d")
    psdi_metadata["files"] = {"default_preview": "absent.md"}
    (directory / "metadata.json").write_text(json.dumps(psdi_metadata))

    with pytest.raises(ValueError, match="default_preview is not an upload file"):
        load_deposit(directory, community=community)


def test_load_deposit_requires_a_community(tmp_path: Path, write_deposit) -> None:
    with pytest.raises(ValueError, match="community must be"):
        load_deposit(write_deposit(tmp_path / "d"), community="")


def test_load_deposit_rejects_a_missing_directory(tmp_path: Path, community: str) -> None:
    with pytest.raises(NotADirectoryError):
        load_deposit(tmp_path / "absent", community=community)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"schema_version": 2}, "schema_version must be 1"),
        ({"dataset": ""}, "dataset must be a non-empty string"),
        ({"version": ""}, "version must be a non-empty string"),
        ({"rows": -1}, "rows must be a non-negative integer"),
        ({"rows": True}, "rows must be a non-negative integer"),
        ({"columns": []}, "columns must be a non-empty list"),
        ({"provenance": {}}, "provenance must be a non-empty object"),
        ({"conventions": "0-based"}, "conventions must be an object"),
    ],
)
def test_validate_dataset_record_rejects(dataset_record: dict, mutation: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_dataset_record(dict(dataset_record, **mutation))


def test_validate_dataset_record_rejects_a_duplicate_column(dataset_record: dict) -> None:
    columns = [{"name": "k_index", "dtype": "int"}, {"name": "k_index", "dtype": "str"}]
    with pytest.raises(ValueError, match="lists column k_index twice"):
        validate_dataset_record(dict(dataset_record, columns=columns))


def test_validate_dataset_record_rejects_a_column_without_a_dtype(dataset_record: dict) -> None:
    with pytest.raises(ValueError, match="column k_index needs a dtype"):
        validate_dataset_record(dict(dataset_record, columns=[{"name": "k_index"}]))


def test_validate_dataset_record_keeps_the_kmesh_convention(dataset_record: dict) -> None:
    # The convention block is why this file exists: a k_index with no stated
    # base and no stated enumeration bound is not reproducible.
    ladder = validate_dataset_record(dataset_record)["conventions"]["kmesh_ladder"]

    assert ladder["base"] == 0
    assert ladder["max_kpoints_per_axis"] == 50


def test_parse_sha256sums_accepts_binary_mode_lines() -> None:
    digest = "0" * 64
    assert parse_sha256sums(f"{digest} *data.csv\n") == {"data.csv": digest}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not-a-digest  data.csv\n", "has no SHA-256 digest"),
        (f"{'0' * 64}\n", "is not '<digest>  <name>'"),
        (f"{'0' * 64}  a.csv\n{'1' * 64}  a.csv\n", "lists a.csv twice"),
        (f"{'0' * 64}  sub/a.csv\n", "must be a bare filename"),
        ("\n\n", "lists no files"),
    ],
)
def test_parse_sha256sums_rejects(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_sha256sums(text)
