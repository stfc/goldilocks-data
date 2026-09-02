from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class KindexExtension:
    """Three-or-more consecutive kindex points planned for one source."""

    source_db_id: str
    current_max_kindex: int
    new_kindices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ExtensionPlan:
    """Planned extensions and source-level skip counts."""

    extensions: tuple[KindexExtension, ...]
    well_not_ultra_sources: int
    clean_sources: int
    dirty_sources: int
    already_complete_sources: int
    partially_existing_sources: int

    @property
    def workchain_count(self) -> int:
        """Return the number of new WorkChains in the plan."""

        return sum(len(extension.new_kindices) for extension in self.extensions)


def plan_well_not_ultra_extensions(
    records: pd.DataFrame,
    summary: pd.DataFrame,
    existing_kindices: dict[str, set[int]],
    *,
    points_per_source: int = 3,
    source_limit: int | None = None,
    workchain_limit: int | None = None,
) -> ExtensionPlan:
    """Plan consecutive kindex extensions for clean well-but-not-ultra sources."""

    if points_per_source < 1:
        raise ValueError("points_per_source must be at least 1")
    if source_limit is not None and source_limit < 0:
        raise ValueError("source_limit must be non-negative")
    if workchain_limit is not None and workchain_limit < 0:
        raise ValueError("workchain_limit must be non-negative")

    records = records.copy()
    summary = summary.copy()
    records["source_db_id"] = records["source_db_id"].astype("string")
    summary["source_db_id"] = summary["source_db_id"].astype("string")
    eligible = summary[summary["well_kindex"].notna() & ~summary["ultra_converged"].astype(bool)]
    eligible_ids = sorted(eligible["source_db_id"].dropna().astype(str).unique())
    grouped_records = {str(source_db_id): group for source_db_id, group in records.groupby("source_db_id")}

    extensions: list[KindexExtension] = []
    clean_sources = 0
    dirty_sources = 0
    already_complete_sources = 0
    partially_existing_sources = 0
    planned_workchains = 0

    for source_db_id in eligible_ids:
        source_records = grouped_records.get(source_db_id)
        if source_records is None:
            dirty_sources += 1
            continue

        submitted = set(source_records["kindex"].dropna().astype(int))
        valid = set(source_records.loc[source_records["energy"].notna(), "kindex"].dropna().astype(int))
        if not valid or submitted - valid:
            dirty_sources += 1
            continue
        clean_sources += 1

        current_max = max(valid)
        target = tuple(range(current_max + 1, current_max + points_per_source + 1))
        existing = existing_kindices.get(source_db_id, set())
        existing_target = set(target) & existing
        if existing_target == set(target):
            already_complete_sources += 1
            continue
        if existing_target:
            partially_existing_sources += 1
            continue

        if source_limit is not None and len(extensions) >= source_limit:
            continue
        if workchain_limit is not None and planned_workchains + len(target) > workchain_limit:
            continue
        extensions.append(KindexExtension(source_db_id, current_max, target))
        planned_workchains += len(target)

    return ExtensionPlan(
        extensions=tuple(extensions),
        well_not_ultra_sources=len(eligible_ids),
        clean_sources=clean_sources,
        dirty_sources=dirty_sources,
        already_complete_sources=already_complete_sources,
        partially_existing_sources=partially_existing_sources,
    )
