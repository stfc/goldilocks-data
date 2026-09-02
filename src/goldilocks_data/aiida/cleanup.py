from __future__ import annotations

from shlex import quote
from typing import Any

import pandas as pd

DEFAULT_KEEP_FIND_FILTER = " ".join(
    [
        "! -name 'aiida.in'",
        "! -name 'aiida.out'",
        "! -name '*.xml'",
        "! -name '_aiidasubmit.sh'",
        "! -name '_scheduler-stdout.txt'",
        "! -name '_scheduler-stderr.txt'",
    ]
)


def cleanup_candidates(group_label: str) -> list[Any]:
    """Return WorkChains in a group that are not marked as retention-cleaned."""

    from aiida.orm import Group, QueryBuilder, WorkChainNode, load_node

    qb = QueryBuilder()
    qb.append(Group, filters={"label": group_label}, tag="group")
    qb.append(WorkChainNode, with_group="group", filters={"extras.retention_cleaned": False}, project="id")
    nodes = [load_node(pk) for pk in qb.all(flat=True)]
    return sorted(
        nodes,
        key=lambda node: (
            str(node.base.extras.get("source_db_id")),
            int(node.base.extras.get("kindex", -1)),
        ),
    )


def calcjobs_with_remote(node: Any) -> list[Any]:
    """Return descendant CalcJobs that have a remote folder."""

    from aiida.orm import CalcJobNode, load_node

    node = load_node(node.pk)
    return [
        item for item in node.called_descendants if isinstance(item, CalcJobNode) and "remote_folder" in item.outputs
    ]


def cleanup_remote(calcjob: Any, *, dry_run: bool = True, keep_find_filter: str = DEFAULT_KEEP_FIND_FILTER) -> None:
    """Delete non-retained remote files for one CalcJob."""

    remote = calcjob.outputs.remote_folder
    remote_path = remote.get_remote_path()
    with remote.get_authinfo().get_transport() as transport:
        cd = f"cd {quote(remote_path)}"
        list_cmd = f"{cd} && find . -type f {keep_find_filter} -print | sort"
        exit_code, stdout, stderr = transport.exec_command_wait(list_cmd)
        if exit_code != 0:
            raise RuntimeError(stderr or stdout)

        if dry_run:
            return

        delete_cmd = f"{cd} && find . -type f {keep_find_filter} -delete && find . -type d -empty -delete"
        exit_code, stdout, stderr = transport.exec_command_wait(delete_cmd)
        if exit_code != 0:
            raise RuntimeError(stderr or stdout)


def cleanup_finished(
    group_label: str,
    *,
    dry_run: bool = True,
    limit: int | None = None,
    progress_interval: int = 25,
) -> pd.DataFrame:
    """Cleanup finished OK WorkChains, continuing past per-remote failures."""

    from aiida.orm import load_node

    records: list[dict[str, Any]] = []
    processed = 0
    candidates = cleanup_candidates(group_label)
    print(
        f"cleanup setup: {len(candidates)} candidate WorkChains, limit={limit}, dry_run={dry_run}",
        flush=True,
    )
    for candidate_index, node in enumerate(candidates, start=1):
        node = load_node(node.pk)
        if limit is not None and processed >= int(limit):
            break
        if not node.is_terminated or not node.is_finished_ok:
            continue

        node_failed = False
        try:
            calcjobs = calcjobs_with_remote(node)
        except Exception as exception:
            node_failed = True
            records.append(_failure_record(node, None, "find_calcjobs", exception))
            calcjobs = []

        for calcjob in calcjobs:
            try:
                cleanup_remote(calcjob, dry_run=dry_run)
            except Exception as exception:
                node_failed = True
                records.append(_failure_record(node, calcjob.pk, "cleanup_remote", exception))

        if not dry_run and not node_failed:
            node.base.extras.set("retention_cleaned", True)
        processed += 1
        if progress_interval > 0 and processed % int(progress_interval) == 0:
            print(
                f"cleanup progress: {processed} finished WorkChains cleaned, "
                f"{candidate_index}/{len(candidates)} candidates checked, "
                f"{len(records)} failures",
                flush=True,
            )

    print(f"cleanup done: {processed} finished WorkChains checked, {len(records)} failures", flush=True)
    return pd.DataFrame(records)


def _failure_record(node: Any, calcjob_pk: int | None, stage: str, exception: Exception) -> dict[str, Any]:
    return {
        "workchain_pk": int(node.pk),
        "calcjob_pk": calcjob_pk,
        "source_db_id": node.base.extras.get("source_db_id"),
        "kindex": node.base.extras.get("kindex"),
        "stage": stage,
        "reason": repr(exception),
    }
