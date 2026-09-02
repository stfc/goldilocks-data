from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from aiida import load_profile
from aiida.orm import StructureData
from ase.io import read
from pymatgen.io.ase import AseAtomsAdaptor

from goldilocks_data.aiida import AiidaScfConfig
from goldilocks_data.aiida.cleanup import cleanup_finished
from goldilocks_data.aiida.submit import existing_kindices_by_source, submit_jobs
from goldilocks_data.codes import DftCode
from goldilocks_data.intents import CalculationIntent
from goldilocks_data.sweeps import AiidaJobSpec, KindexExtension, kindex_points, plan_well_not_ultra_extensions

TASK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DIR = TASK_ROOT / "results"
DEFAULT_SOURCE_DB = "Goldilocks_scf_K_mesh_convergence_nospin"


@dataclass(frozen=True, slots=True)
class Snapshot:
    records: pd.DataFrame
    summary: pd.DataFrame
    metadata: dict


def main() -> int:
    args = parse_args()
    profile = load_profile()
    config = AiidaScfConfig(
        code_label=args.code_label,
        pseudo_family_label=args.pseudo_family_label,
        group_label=args.group_label,
        degauss_ry=args.degauss_ry,
        num_machines=args.num_machines,
        num_mpiprocs_per_machine=args.num_mpiprocs_per_machine,
        max_wallclock_seconds=args.max_wallclock_seconds,
    )
    snapshot = load_snapshot(args.snapshot_dir, profile.name, config.group_label)
    print(
        f"snapshot: generated_at={snapshot.metadata['generated_at']} "
        f"workchains={snapshot.metadata['workchain_count']} "
        f"sources={snapshot.metadata['source_count']}"
    )

    active = active_workchain_count(config.group_label)
    available_slots = max(0, args.max_active - active)
    workchain_budget = min(args.max_new_workchains, available_slots)
    print(f"capacity: active={active} max_active={args.max_active} available_slots={available_slots}")

    if args.cleanup_limit != 0:
        cleanup_failures = cleanup_finished(
            config.group_label,
            dry_run=not args.execute,
            limit=args.cleanup_limit,
        )
        print(f"cleanup failures: {len(cleanup_failures)}")

    if workchain_budget < args.points_per_source:
        print(f"skip submit: fewer than {args.points_per_source} WorkChain slots are available")
        return 0

    existing = existing_kindices_by_source(config.group_label)
    plan = plan_well_not_ultra_extensions(
        snapshot.records,
        snapshot.summary,
        existing,
        points_per_source=args.points_per_source,
        source_limit=args.batch_size,
        workchain_limit=workchain_budget,
    )
    print(
        f"selection: well_not_ultra={plan.well_not_ultra_sources} "
        f"clean={plan.clean_sources} dirty={plan.dirty_sources} "
        f"already_complete={plan.already_complete_sources} "
        f"partially_existing={plan.partially_existing_sources}"
    )
    print(f"plan: sources={len(plan.extensions)} workchains={plan.workchain_count}")
    for extension in plan.extensions[:20]:
        print(
            f"  {extension.source_db_id}: current_max={extension.current_max_kindex} "
            f"submit={list(extension.new_kindices)}"
        )

    if not plan.extensions:
        print("nothing to submit")
        return 0
    if not args.execute:
        print("dry run: pass --execute to submit the planned WorkChains")
        return 0

    if args.cif_dir is None:
        raise ValueError("--cif-dir is required with --execute")
    result = submit_jobs(
        (build_job_spec(extension, args.cif_dir, args.source_db) for extension in plan.extensions),
        config,
    )
    print(
        f"submitted={len(result.submitted)} "
        f"skipped_existing={len(result.skipped_existing)} "
        f"failed_source_db_ids={len(result.failed_sources)}"
    )
    for failed in result.failed_sources:
        print(f"  failed {failed.source_db_id} {failed.stage}: {failed.reason}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extend clean well-but-not-ultra kindex sweeps from a saved analysis snapshot."
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--cif-dir", type=Path)
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB)
    parser.add_argument("--batch-size", type=int, default=200, help="Maximum sources selected per invocation.")
    parser.add_argument("--points-per-source", type=int, default=3)
    parser.add_argument("--max-new-workchains", type=int, default=600)
    parser.add_argument("--max-active", type=int, default=1000)
    parser.add_argument("--cleanup-limit", type=int, default=0)
    parser.add_argument("--code-label", default="qe-7.5-pw-admin@scarf")
    parser.add_argument("--pseudo-family-label", default="PseudoDojo/0.4/PBEsol/SR/standard/upf")
    parser.add_argument("--group-label", default="goldilocks/qe-scf/nospin/pseudodojo")
    parser.add_argument("--degauss-ry", type=float, default=0.01)
    parser.add_argument("--num-machines", type=int, default=1)
    parser.add_argument("--num-mpiprocs-per-machine", type=int, default=32)
    parser.add_argument("--max-wallclock-seconds", type=int, default=7200)
    return parser.parse_args()


def load_snapshot(snapshot_dir: Path, profile_name: str, group_label: str) -> Snapshot:
    records_path = snapshot_dir / "workchain-records.parquet"
    summary_path = snapshot_dir / "source-summary.csv"
    metadata_path = snapshot_dir / "snapshot-metadata.json"
    missing = [path for path in (records_path, summary_path, metadata_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing snapshot files: {', '.join(str(path) for path in missing)}")

    metadata = json.loads(metadata_path.read_text())
    if metadata.get("aiida_profile") != profile_name:
        raise ValueError(f"Snapshot profile {metadata.get('aiida_profile')!r} does not match {profile_name!r}")
    if metadata.get("group_label") != group_label:
        raise ValueError(f"Snapshot group {metadata.get('group_label')!r} does not match {group_label!r}")

    records = pd.read_parquet(records_path)
    summary = pd.read_csv(summary_path, dtype={"source_db_id": "string"})
    records["source_db_id"] = records["source_db_id"].astype("string")
    if len(records) != int(metadata["workchain_count"]):
        raise ValueError("Snapshot WorkChain count does not match its metadata")
    if len(summary) != int(metadata["source_count"]):
        raise ValueError("Snapshot source count does not match its metadata")
    return Snapshot(records, summary, metadata)


def build_job_spec(extension: KindexExtension, cif_dir: Path, source_db: str) -> AiidaJobSpec:
    cif_path = cif_dir / f"{extension.source_db_id}.cif"
    atoms = read(cif_path)
    pmg_structure = AseAtomsAdaptor.get_structure(atoms)
    points = kindex_points(pmg_structure, extension.new_kindices[0], extension.new_kindices[-1])
    actual_kindices = tuple(int(point.axis_values["kindex"]) for point in points)
    if actual_kindices != extension.new_kindices:
        raise ValueError(
            f"Kindex schedule exhausted for {extension.source_db_id}: "
            f"requested={extension.new_kindices} available={actual_kindices}"
        )

    structure = StructureData(ase=atoms)
    structure.base.extras.set_many(
        {
            "source_db": source_db,
            "source_db_id": extension.source_db_id,
            "source_file": str(cif_path),
        }
    )
    structure.store()
    return AiidaJobSpec(
        source_db_id=extension.source_db_id,
        structure=structure,
        code=DftCode.QE,
        intent=CalculationIntent.SCF,
        points=points,
    )


def active_workchain_count(group_label: str) -> int:
    from aiida.orm import Group, QueryBuilder, WorkChainNode

    qb = QueryBuilder()
    qb.append(Group, filters={"label": group_label}, tag="group")
    qb.append(
        WorkChainNode,
        with_group="group",
        filters={"attributes.process_state": {"in": ["created", "waiting", "running"]}},
        project="id",
    )
    return qb.count()


if __name__ == "__main__":
    raise SystemExit(main())
