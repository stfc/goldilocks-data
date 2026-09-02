from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goldilocks_data.aiida.config import AiidaScfConfig


@dataclass(frozen=True, slots=True)
class FailedSourceRecord:
    """Persistent record for a source that could not be submitted."""

    source_db_id: str
    stage: str
    reason: str
    pk: int | None = None


def existing_failed_pk(source_db_id: str, stage: str, config: AiidaScfConfig) -> int | None:
    """Return an existing persistent failed-source record PK, if present."""

    from aiida import orm
    from aiida.orm import Group, QueryBuilder

    qb = QueryBuilder()
    qb.append(Group, filters={"label": config.resolved_failed_group_label}, tag="group")
    qb.append(
        orm.Dict,
        with_group="group",
        filters={"extras.source_db_id": str(source_db_id), "extras.fail_stage": stage},
        project="id",
    )
    rows = qb.all(flat=True)
    return int(rows[0]) if rows else None


def failed_source_ids(config: AiidaScfConfig) -> set[str]:
    """Return source IDs recorded as failed for this campaign."""

    from aiida import orm
    from aiida.orm import Group, QueryBuilder

    qb = QueryBuilder()
    qb.append(Group, filters={"label": config.resolved_failed_group_label}, tag="group")
    qb.append(
        orm.Dict,
        with_group="group",
        filters={"extras.record_type": "failed_source"},
        project="extras.source_db_id",
    )
    return {str(value) for value in qb.all(flat=True) if value is not None}


def record_failed_source(source_db_id: str, stage: str, reason: str, config: AiidaScfConfig) -> int:
    """Persist a failed-source record in AiiDA and return its PK."""

    from aiida import orm

    existing = existing_failed_pk(source_db_id, stage, config)
    if existing is not None:
        return existing

    node = orm.Dict(
        dict={
            "source_db_id": str(source_db_id),
            "stage": stage,
            "reason": reason,
            "group_label": config.group_label,
            "pseudo_family": config.pseudo_family_label,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    ).store()
    node.base.extras.set_many(
        {
            "source_db_id": str(source_db_id),
            "calc_type": "scf",
            "record_type": "failed_source",
            "fail_stage": stage,
            "fail_reason": reason,
            "pp": config.pseudo_family_label,
        }
    )
    add_to_group(node, config.resolved_failed_group_label)
    return int(node.pk)


def add_to_group(node: object, group_label: str) -> None:
    """Add a stored AiiDA node to a group, creating the group if needed."""

    from aiida.orm import Group

    group, _ = Group.collection.get_or_create(label=group_label)
    group.add_nodes([node])
