from __future__ import annotations

import gc
import time
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable

from goldilocks_data.aiida.builders.qe import (
    build_qe_pw_scf_builder,
    check_qe_pseudo_family_support,
    qe_pw_scf_extras,
)
from goldilocks_data.aiida.config import AiidaScfConfig, SubmitSummary
from goldilocks_data.aiida.registry import (
    FailedSourceRecord,
    add_to_group,
    record_failed_source,
)
from goldilocks_data.codes.models import DftCode
from goldilocks_data.intents.models import CalculationIntent
from goldilocks_data.sweeps.models import AiidaJobSpec, ScfSweepSpec, SweepAxis, SweepPoint


@dataclass(frozen=True, slots=True)
class BuilderAdapter:
    """A code/intent-specific adapter for AiiDA builder construction."""

    build_builder: Callable[[Any, Any, Any, SweepPoint, AiidaScfConfig], Any]
    build_extras: Callable[[str, Any, SweepPoint, Any, AiidaScfConfig], dict[str, Any]]
    check_inputs: Callable[[Any, Any], str | None] | None = None


BUILDER_ADAPTERS: dict[tuple[DftCode, CalculationIntent], BuilderAdapter] = {
    (DftCode.QE, CalculationIntent.SCF): BuilderAdapter(
        build_builder=build_qe_pw_scf_builder,
        build_extras=qe_pw_scf_extras,
        check_inputs=check_qe_pseudo_family_support,
    ),
}


def configure_profile_caching(config: AiidaScfConfig, profile: Any) -> None:
    """Enable AiiDA caching for the current profile when requested."""

    if not config.enable_aiida_caching:
        return

    from aiida.manage.caching import get_use_cache
    from aiida.manage.configuration import get_config

    process_types = [
        "aiida.calculations:quantumespresso.pw",
        "aiida.workflows:quantumespresso.pw.base",
    ]
    aiida_config = get_config()
    enabled_for = (
        aiida_config.get_option(
            "caching.enabled_for",
            scope=profile.name,
            default=[],
        )
        or []
    )
    enabled_for = sorted(set(enabled_for) | set(process_types))

    if config.configure_profile_caching:
        aiida_config.set_option("caching.enabled_for", enabled_for, scope=profile.name)
        aiida_config.store()

    for process_type in process_types:
        get_use_cache(identifier=process_type)


def submit_jobs(specs: Iterable[AiidaJobSpec], config: AiidaScfConfig, *, progress_interval: int = 10) -> SubmitSummary:
    """Submit explicit AiiDA job specs, continuing past per-source failures."""

    from aiida import load_profile
    from aiida.engine import submit
    from aiida.manage.caching import enable_caching
    from aiida.orm import load_code, load_group

    profile = load_profile()
    configure_profile_caching(config, profile)

    code = load_code(config.code_label)
    pseudo_group = load_group(config.pseudo_family_label)
    summary = SubmitSummary()
    cache_context = enable_caching() if config.enable_aiida_caching else nullcontext()

    with cache_context:
        for spec_index, spec in enumerate(specs, start=1):
            adapter = _adapter_for(spec)
            source_started_at = time.monotonic()
            submitted_before = len(summary.submitted)
            skipped_before = len(summary.skipped_existing)
            failed_before = len(summary.failed_sources)
            print(
                f"submit source_db_id={spec.source_db_id} points={len(spec.points)} source_index={spec_index}",
                flush=True,
            )
            try:
                if adapter.check_inputs is not None:
                    input_error = adapter.check_inputs(pseudo_group, spec.structure)
                    if input_error is not None:
                        failed = _record_failed(
                            spec.source_db_id,
                            "input_check",
                            input_error,
                            config,
                        )
                        summary.failed_sources.append(failed)
                        print(
                            f"submit source done source_db_id={spec.source_db_id} "
                            f"submitted={len(summary.submitted) - submitted_before} "
                            f"skipped_existing={len(summary.skipped_existing) - skipped_before} "
                            f"failed={len(summary.failed_sources) - failed_before} "
                            f"elapsed_s={time.monotonic() - source_started_at:.1f}",
                            flush=True,
                        )
                        gc.collect()
                        continue

                existing_kindex_pks = existing_kindex_pks_for_source(spec.source_db_id, config.group_label)
                for point in spec.points:
                    if config.skip_existing:
                        kindex = point.axis_values.get(SweepAxis.KINDEX.value)
                        if spec.code == DftCode.QE and spec.intent == CalculationIntent.SCF and kindex is not None:
                            existing = existing_kindex_pks.get(int(kindex))
                            if existing is not None:
                                summary.skipped_existing.append(existing)
                                continue
                        else:
                            existing = existing_workchain_pk(
                                spec.source_db_id,
                                spec.code,
                                spec.intent,
                                point,
                                config.group_label,
                            )
                            if existing is not None:
                                summary.skipped_existing.append(existing)
                                continue

                    try:
                        builder = adapter.build_builder(
                            code,
                            pseudo_group,
                            spec.structure,
                            point,
                            config,
                        )
                        node = submit(builder)
                        node.base.extras.set_many(
                            adapter.build_extras(
                                spec.source_db_id,
                                pseudo_group,
                                point,
                                builder,
                                config,
                            )
                        )
                        add_to_group(node, config.group_label)
                        summary.submitted.append(int(node.pk))
                        kindex = point.axis_values.get(SweepAxis.KINDEX.value)
                        if kindex is not None:
                            existing_kindex_pks[int(kindex)] = int(node.pk)
                        if progress_interval > 0 and len(summary.submitted) % int(progress_interval) == 0:
                            print(
                                f"submit progress: {len(summary.submitted)} submitted, "
                                f"{len(summary.skipped_existing)} skipped_existing, "
                                f"{len(summary.failed_sources)} failed_source_db_ids",
                                flush=True,
                            )
                    except Exception as exception:
                        failed = _record_failed(
                            spec.source_db_id,
                            _point_stage(point),
                            repr(exception),
                            config,
                        )
                        summary.failed_sources.append(failed)
                        break
            except Exception as exception:
                failed = _record_failed(
                    spec.source_db_id,
                    "source_setup",
                    repr(exception),
                    config,
                )
                summary.failed_sources.append(failed)
            print(
                f"submit source done source_db_id={spec.source_db_id} "
                f"submitted={len(summary.submitted) - submitted_before} "
                f"skipped_existing={len(summary.skipped_existing) - skipped_before} "
                f"failed={len(summary.failed_sources) - failed_before} "
                f"elapsed_s={time.monotonic() - source_started_at:.1f}",
                flush=True,
            )
            gc.collect()
    return summary


def submit_scf_sweeps(specs: list[ScfSweepSpec], config: AiidaScfConfig) -> SubmitSummary:
    """Submit SCF sweep specs using the QE adapter by default."""

    jobs = [
        AiidaJobSpec(
            source_db_id=spec.source_db_id,
            structure=spec.structure,
            code=DftCode.QE,
            intent=CalculationIntent.SCF,
            points=spec.points,
        )
        for spec in specs
    ]
    return submit_jobs(jobs, config)


def existing_workchain_pk(
    source_db_id: str,
    code: DftCode,
    intent: CalculationIntent,
    point: SweepPoint,
    group_label: str,
) -> int | None:
    """Return an existing WorkChain PK for a source/code/intent/sweep point."""

    from aiida.orm import Group, QueryBuilder, WorkChainNode

    filters: dict[str, Any] = {
        "extras.source_db_id": str(source_db_id),
        "extras.code": code.value,
        "extras.calc_type": intent.value,
    }
    for axis, value in point.axis_values.items():
        filters[f"extras.{axis}"] = value

    qb = QueryBuilder()
    qb.append(Group, filters={"label": group_label}, tag="group")
    qb.append(
        WorkChainNode,
        with_group="group",
        filters=filters,
        project="id",
    )
    rows = qb.all(flat=True)
    return int(rows[0]) if rows else None


def existing_kindex_pks_for_source(source_db_id: str, group_label: str) -> dict[int, int]:
    """Return existing kindex values and WorkChain PKs for a source in a campaign group."""

    from aiida.orm import Group, QueryBuilder, WorkChainNode

    qb = QueryBuilder()
    qb.append(Group, filters={"label": group_label}, tag="group")
    qb.append(
        WorkChainNode,
        with_group="group",
        filters={"extras.source_db_id": str(source_db_id), "extras.calc_type": "scf"},
        project=["extras.kindex", "id"],
    )
    return {int(kindex): int(pk) for kindex, pk in qb.all() if kindex is not None and pk is not None}


def existing_kindices_for_source(source_db_id: str, group_label: str) -> set[int]:
    """Return kindex values already present for a source in a campaign group."""

    return set(existing_kindex_pks_for_source(source_db_id, group_label))


def existing_kindices_by_source(group_label: str) -> dict[str, set[int]]:
    """Return existing SCF kindex values grouped by source ID for a campaign group."""

    from collections import defaultdict

    from aiida.orm import Group, QueryBuilder, WorkChainNode

    qb = QueryBuilder()
    qb.append(Group, filters={"label": group_label}, tag="group")
    qb.append(
        WorkChainNode,
        with_group="group",
        filters={"extras.calc_type": "scf"},
        project=["extras.source_db_id", "extras.kindex"],
    )

    existing: defaultdict[str, set[int]] = defaultdict(set)
    for source_db_id, kindex in qb.all():
        if source_db_id is None or kindex is None:
            continue
        existing[str(source_db_id)].add(int(kindex))
    return dict(existing)


def source_has_kindex_range(source_db_id: str, group_label: str, kindex_min: int, kindex_max: int) -> bool:
    """Return whether all requested kindex values already exist for a source."""

    existing = existing_kindices_for_source(source_db_id, group_label)
    expected = set(range(int(kindex_min), int(kindex_max) + 1))
    return expected.issubset(existing)


def _adapter_for(spec: AiidaJobSpec) -> BuilderAdapter:
    try:
        return BUILDER_ADAPTERS[(spec.code, spec.intent)]
    except KeyError as exception:
        raise ValueError(f"No builder adapter for code={spec.code} intent={spec.intent}") from exception


def _record_failed(
    source_db_id: str,
    stage: str,
    reason: str,
    config: AiidaScfConfig,
) -> FailedSourceRecord:
    pk = record_failed_source(source_db_id, stage, reason, config)
    return FailedSourceRecord(source_db_id, stage, reason, pk)


def _point_stage(point: SweepPoint) -> str:
    if SweepAxis.KINDEX.value in point.axis_values:
        return f"submit_kindex_{point.axis_values[SweepAxis.KINDEX.value]}"
    axes = "_".join(f"{axis}_{value}" for axis, value in sorted(point.axis_values.items()))
    return f"submit_{axes}" if axes else "submit_point"
