from __future__ import annotations

import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

from goldilocks_data.publish.deposit import Deposit

PSDI_API = "https://data-collections.psdi.ac.uk/api"


class DraftCleanupError(RuntimeError):
    """An upload failed and the resulting partial draft could not be removed."""

    def __init__(self, draft_id: str | None, upload_error: Exception, cleanup_error: Exception) -> None:
        self.draft_id = draft_id
        self.upload_error = upload_error
        self.cleanup_error = cleanup_error
        label = draft_id or "unknown"
        super().__init__(
            f"PSDI draft {label} upload failed ({upload_error}); "
            f"cleanup also failed ({cleanup_error}); remove the partial draft in PSDI"
        )


def read_token(path: Path) -> str:
    """Read a PSDI token from a file that only its owner can read.

    A token readable by group or other is treated as compromised rather than
    merely untidy, so this refuses instead of warning. The token is returned for
    immediate use and never logged.
    """

    if not path.is_file():
        raise FileNotFoundError(path)
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(f"{path} is readable beyond its owner; run: chmod 600 {path}")
    token = path.read_text().strip()
    if not token:
        raise ValueError(f"{path} is empty")
    return token


def _default_repository_factory() -> Callable[..., Any]:
    from data_collections_api.invenio import InvenioRepository

    return InvenioRepository


def create_deposit(
    deposit: Deposit,
    *,
    token: str,
    repository_factory: Callable[..., Any] | None = None,
) -> str:
    """Create, populate, and bind one PSDI draft, and return its identifier.

    The draft is never submitted: a human reviews it on the PSDI website and
    submits it there. If any step after creation fails, the partial draft is
    deleted, so a failure costs a draft rather than leaving a half-made record.

    ``repository_factory`` is injectable so the upload sequence is testable
    without a network or a token.
    """

    factory = repository_factory or _default_repository_factory()
    repository = factory(url=PSDI_API, api_key=token)
    draft = repository.depositions.create()
    draft_id: str | None = None
    try:
        draft_id = draft.get()["id"]
        if not isinstance(draft_id, str) or not draft_id:
            raise ValueError("PSDI draft response has no valid id")
        draft.update(deposit.metadata)
        draft.files.upload(deposit.files)
        draft.bind(deposit.community)
    except Exception as upload_error:
        try:
            draft.delete()
        except Exception as cleanup_error:
            raise DraftCleanupError(draft_id, upload_error, cleanup_error) from upload_error
        raise
    return draft_id
