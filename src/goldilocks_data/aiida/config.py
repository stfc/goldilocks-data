from __future__ import annotations

from dataclasses import dataclass, field

from goldilocks_data.aiida.registry import FailedSourceRecord


@dataclass(frozen=True, slots=True)
class AiidaScfConfig:
    """Runtime settings for submitting SCF sweeps through AiiDA."""

    code_label: str
    pseudo_family_label: str
    group_label: str
    failed_group_label: str | None = None
    degauss_ry: float = 0.01
    nbnd: int | None = None
    num_machines: int = 1
    num_mpiprocs_per_machine: int = 32
    max_wallclock_seconds: int = 7200
    skip_existing: bool = True
    enable_aiida_caching: bool = True
    configure_profile_caching: bool = True

    @property
    def resolved_failed_group_label(self) -> str:
        return self.failed_group_label or f"{self.group_label}/failed-sources"


@dataclass(slots=True)
class SubmitSummary:
    """Summary returned by batch submission."""

    submitted: list[int] = field(default_factory=list)
    skipped_existing: list[int] = field(default_factory=list)
    failed_sources: list[FailedSourceRecord] = field(default_factory=list)
