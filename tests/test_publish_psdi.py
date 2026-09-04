from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from goldilocks_data.publish import DraftCleanupError, create_deposit, load_deposit, read_token


class FakeFiles:
    def __init__(self, fail: bool) -> None:
        self.fail = fail
        self.uploaded: dict[str, Path] | None = None

    def upload(self, files: dict[str, Path]) -> None:
        if self.fail:
            raise RuntimeError("upload rejected")
        self.uploaded = files


class FakeDraft:
    def __init__(self, *, draft_id: Any = "abc12-34567", fail_upload: bool = False, fail_delete: bool = False) -> None:
        self.draft_id = draft_id
        self.fail_delete = fail_delete
        self.files = FakeFiles(fail_upload)
        self.metadata: dict[str, Any] | None = None
        self.bound_to: str | None = None
        self.deleted = False

    def get(self) -> dict[str, Any]:
        return {"id": self.draft_id}

    def update(self, metadata: dict[str, Any]) -> None:
        self.metadata = metadata

    def bind(self, community: str) -> None:
        self.bound_to = community

    def delete(self) -> None:
        if self.fail_delete:
            raise RuntimeError("delete rejected")
        self.deleted = True


class FakeRepository:
    def __init__(self, draft: FakeDraft) -> None:
        self.depositions = self
        self.draft = draft
        self.api_key: str | None = None

    def create(self) -> FakeDraft:
        return self.draft


def factory_for(draft: FakeDraft):
    def factory(*, url: str, api_key: str) -> FakeRepository:
        repository = FakeRepository(draft)
        repository.api_key = api_key
        return repository

    return factory


def test_create_deposit_uploads_updates_and_binds(tmp_path: Path, write_deposit, community: str) -> None:
    deposit = load_deposit(write_deposit(tmp_path / "d"), community=community)
    draft = FakeDraft()

    draft_id = create_deposit(deposit, token="secret", repository_factory=factory_for(draft))

    assert draft_id == "abc12-34567"
    assert draft.metadata == deposit.metadata
    assert draft.bound_to == community
    assert draft.files.uploaded == deposit.files
    # A draft is never submitted from here; a human does that on the website.
    assert draft.deleted is False


def test_create_deposit_deletes_the_partial_draft_when_upload_fails(
    tmp_path: Path, write_deposit, community: str
) -> None:
    deposit = load_deposit(write_deposit(tmp_path / "d"), community=community)
    draft = FakeDraft(fail_upload=True)

    with pytest.raises(RuntimeError, match="upload rejected"):
        create_deposit(deposit, token="secret", repository_factory=factory_for(draft))

    assert draft.deleted is True


def test_create_deposit_reports_the_draft_id_when_cleanup_also_fails(
    tmp_path: Path, write_deposit, community: str
) -> None:
    deposit = load_deposit(write_deposit(tmp_path / "d"), community=community)
    draft = FakeDraft(fail_upload=True, fail_delete=True)

    with pytest.raises(DraftCleanupError) as raised:
        create_deposit(deposit, token="secret", repository_factory=factory_for(draft))

    # Without the id in the message the orphan draft cannot be found by hand.
    assert raised.value.draft_id == "abc12-34567"
    assert "abc12-34567" in str(raised.value)
    assert "remove the partial draft" in str(raised.value)


def test_create_deposit_rejects_a_draft_without_an_id(tmp_path: Path, write_deposit, community: str) -> None:
    deposit = load_deposit(write_deposit(tmp_path / "d"), community=community)
    draft = FakeDraft(draft_id="")

    with pytest.raises(ValueError, match="no valid id"):
        create_deposit(deposit, token="secret", repository_factory=factory_for(draft))

    assert draft.deleted is True


def test_read_token_refuses_a_file_others_can_read(tmp_path: Path) -> None:
    path = tmp_path / "psdi.token"
    path.write_text("secret\n")
    path.chmod(0o644)

    with pytest.raises(PermissionError, match="readable beyond its owner"):
        read_token(path)


def test_read_token_reads_an_owner_only_file(tmp_path: Path) -> None:
    path = tmp_path / "psdi.token"
    path.write_text("  secret\n")
    path.chmod(0o600)

    assert read_token(path) == "secret"


def test_read_token_rejects_an_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "psdi.token"
    path.write_text("\n")
    path.chmod(0o600)

    with pytest.raises(ValueError, match="is empty"):
        read_token(path)


def test_publish_imports_without_the_psdi_client() -> None:
    # The client is an optional extra; importing the package must not need it.
    import goldilocks_data.publish as publish

    assert json.dumps({"ok": True})
    assert publish.create_deposit is create_deposit
