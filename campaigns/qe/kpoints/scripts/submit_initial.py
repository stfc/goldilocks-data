from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from aiida import load_profile
from aiida.orm import StructureData
from ase.io import read
from pymatgen.io.ase import AseAtomsAdaptor

from goldilocks_data.aiida import AiidaScfConfig
from goldilocks_data.aiida.cleanup import cleanup_finished
from goldilocks_data.aiida.registry import failed_source_ids
from goldilocks_data.aiida.submit import existing_kindices_by_source, submit_jobs
from goldilocks_data.codes import DftCode
from goldilocks_data.intents import CalculationIntent
from goldilocks_data.sweeps import AiidaJobSpec
from goldilocks_data.sweeps.kindex import kindex_points
from goldilocks_data.sweeps.kmesh import generate_candidate_k_distances, k_distance_to_mesh

SUMMARY_NOTE_COLUMN = "Convergence Notes"
FULL_NOTE_COLUMN = "Convergence Notes (modified)"
DEFAULT_SOURCE_DB = "Goldilocks_scf_K_mesh_convergence_nospin"


@dataclass(frozen=True, slots=True)
class LocalJobInput:
    source_db_id: str
    kindex_max: int


def main() -> int:
    args = parse_args()
    load_profile()

    config = AiidaScfConfig(
        code_label=args.code_label,
        pseudo_family_label=args.pseudo_family_label,
        group_label=args.group_label,
        degauss_ry=args.degauss_ry,
        num_machines=args.num_machines,
        num_mpiprocs_per_machine=args.num_mpiprocs_per_machine,
        max_wallclock_seconds=args.max_wallclock_seconds,
    )

    active = active_workchain_count(config.group_label)
    print(f"active workchains: {active}")

    if args.cleanup_limit != 0:
        cleanup_failures = cleanup_finished(
            config.group_label,
            dry_run=not args.execute,
            limit=args.cleanup_limit,
        )
        print(f"cleanup failures: {len(cleanup_failures)}")
        if not cleanup_failures.empty:
            print(cleanup_failures.to_string(index=False))

    if active >= args.max_active:
        print(f"skip submit: active workchains >= max_active ({args.max_active})")
        return 0

    local_inputs = next_unprocessed_inputs(
        config=config,
        cif_dir=args.cif_dir,
        convergence_summary=args.convergence_summary,
        full_scf_summary=args.full_scf_summary,
        batch_size=args.batch_size,
        ultra_extra_kindex=args.ultra_extra_kindex,
    )
    print(f"next unprocessed source_db_ids: {len(local_inputs)}")
    for item in local_inputs[:10]:
        print(f"  {item.source_db_id}: submit 0..{item.kindex_max}")

    if not args.execute:
        print("dry run: pass --execute to submit jobs and delete cleanup files")
        return 0

    summary = submit_jobs(
        (build_job_spec(item, args.cif_dir, args.source_db) for item in local_inputs),
        config,
    )
    print(
        f"submitted={len(summary.submitted)} "
        f"skipped_existing={len(summary.skipped_existing)} "
        f"failed_source_db_ids={len(summary.failed_sources)}"
    )
    if summary.failed_sources:
        for failed in summary.failed_sources:
            print(f"  failed {failed.source_db_id} {failed.stage}: {failed.reason}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cif-dir", type=Path, required=True)
    parser.add_argument("--convergence-summary", type=Path, required=True)
    parser.add_argument("--full-scf-summary", type=Path, required=True)
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-active", type=int, default=1000)
    parser.add_argument("--cleanup-limit", type=int, default=500)
    parser.add_argument("--ultra-extra-kindex", type=int, default=2)
    parser.add_argument("--code-label", default="qe-7.5-pw-admin@scarf")
    parser.add_argument("--pseudo-family-label", default="PseudoDojo/0.4/PBEsol/SR/standard/upf")
    parser.add_argument("--group-label", default="goldilocks/qe-scf/nospin/pseudodojo")
    parser.add_argument("--degauss-ry", type=float, default=0.01)
    parser.add_argument("--num-machines", type=int, default=1)
    parser.add_argument("--num-mpiprocs-per-machine", type=int, default=32)
    parser.add_argument("--max-wallclock-seconds", type=int, default=7200)
    return parser.parse_args()


def next_unprocessed_inputs(
    *,
    config: AiidaScfConfig,
    cif_dir: Path,
    convergence_summary: Path,
    full_scf_summary: Path,
    batch_size: int,
    ultra_extra_kindex: int,
) -> list[LocalJobInput]:
    summary = load_summary(convergence_summary, SUMMARY_NOTE_COLUMN)
    full_summary = load_summary(full_scf_summary, FULL_NOTE_COLUMN)
    failed_ids = failed_source_ids(config)
    ultra_rows = ultra_rows_by_source(summary, full_summary)
    eligible_ids = eligible_source_ids(ultra_rows, cif_dir)
    existing_kindices = existing_kindices_by_source(config.group_label)
    print(
        f"scan setup: {len(eligible_ids)} eligible source_db_ids, "
        f"{len(existing_kindices)} source_db_ids with existing workchains, "
        f"{len(failed_ids)} failed source_db_id records"
    )

    items: list[LocalJobInput] = []
    skipped_failed = 0
    skipped_complete = 0
    for scanned, source_db_id in enumerate(eligible_ids, start=1):
        if source_db_id in failed_ids:
            skipped_failed += 1
            if scanned % 100 == 0:
                print_scan_progress(scanned, len(eligible_ids), len(items), skipped_failed, skipped_complete)
            continue
        row = ultra_rows[source_db_id]
        ultra_mesh = (int(row["k1"]), int(row["k2"]), int(row["k3"]))
        pmg_structure = load_pmg_structure(source_db_id, cif_dir)
        new_ultra = new_kindex_for_mesh(pmg_structure, ultra_mesh)
        kindex_max = new_ultra + int(ultra_extra_kindex)
        existing = existing_kindices.get(source_db_id, set())
        if source_has_expected_kindices(existing, 0, kindex_max):
            skipped_complete += 1
            if scanned % 100 == 0:
                print_scan_progress(scanned, len(eligible_ids), len(items), skipped_failed, skipped_complete)
            continue
        items.append(LocalJobInput(source_db_id, kindex_max))
        if scanned % 100 == 0:
            print_scan_progress(scanned, len(eligible_ids), len(items), skipped_failed, skipped_complete)
        if len(items) >= batch_size:
            break
    print_scan_progress(scanned if eligible_ids else 0, len(eligible_ids), len(items), skipped_failed, skipped_complete)
    return items


def source_has_expected_kindices(existing: set[int], kindex_min: int, kindex_max: int) -> bool:
    return set(range(int(kindex_min), int(kindex_max) + 1)).issubset(existing)


def print_scan_progress(
    scanned: int,
    total: int,
    selected: int,
    skipped_failed: int,
    skipped_complete: int,
) -> None:
    print(
        f"scan progress: {scanned}/{total} scanned, "
        f"{selected} selected, "
        f"{skipped_complete} complete, "
        f"{skipped_failed} failed-record source_db_ids"
    )


def load_summary(path: Path, note_column: str) -> pd.DataFrame:
    table = pd.read_csv(path)
    table["source_db_id"] = table["source_db_id"].astype(str)
    table[note_column] = table[note_column].astype(str)
    return table


def eligible_source_ids(ultra_rows: dict[str, pd.Series], cif_dir: Path) -> list[str]:
    cif_ids = {path.stem for path in cif_dir.glob("*.cif")}
    return sorted(cif_ids & set(ultra_rows))


def ultra_rows_by_source(summary: pd.DataFrame, full_summary: pd.DataFrame) -> dict[str, pd.Series]:
    rows: dict[str, pd.Series] = {}
    for table, note_column in [(summary, SUMMARY_NOTE_COLUMN), (full_summary, FULL_NOTE_COLUMN)]:
        ultra_table = table.loc[table[note_column] == "ultra"].sort_values(["source_db_id", "k_index"])
        for source_db_id, group in ultra_table.groupby("source_db_id", sort=False):
            row = group.iloc[-1]
            previous = rows.get(source_db_id)
            if previous is None or int(row["k_index"]) > int(previous["k_index"]):
                rows[source_db_id] = row
    return rows


def load_structure(source_db_id: str, cif_dir: Path, source_db: str) -> StructureData:
    cif_path = cif_dir / f"{source_db_id}.cif"
    atoms = read(cif_path)
    structure = StructureData(ase=atoms)
    structure.base.extras.set_many(
        {
            "source_db": source_db,
            "source_db_id": source_db_id,
            "source_file": str(cif_path),
        }
    )
    structure.store()
    return structure


def load_pmg_structure(source_db_id: str, cif_dir: Path):
    cif_path = cif_dir / f"{source_db_id}.cif"
    atoms = read(cif_path)
    return AseAtomsAdaptor.get_structure(atoms)


def new_kindex_for_mesh(pmg_structure, mesh: tuple[int, int, int]) -> int:
    candidates = generate_candidate_k_distances(pmg_structure)
    if not candidates:
        raise ValueError(f"Mesh {mesh} not found in gamma-inclusive schedule")

    schedule = [k_distance_to_mesh(pmg_structure, candidates[0] + 1.0)]
    schedule.extend(
        k_distance_to_mesh(pmg_structure, 0.5 * (upper + lower))
        for upper, lower in zip(candidates[:-1], candidates[1:], strict=True)
    )

    seen: set[tuple[int, int, int]] = set()
    for candidate_mesh in schedule:
        if candidate_mesh in seen:
            continue
        if candidate_mesh == mesh:
            return len(seen)
        seen.add(candidate_mesh)
    raise ValueError(f"Mesh {mesh} not found in gamma-inclusive schedule")


def build_job_spec(item: LocalJobInput, cif_dir: Path, source_db: str) -> AiidaJobSpec:
    structure = load_structure(item.source_db_id, cif_dir, source_db)
    pmg_structure = AseAtomsAdaptor.get_structure(structure.get_ase())
    return AiidaJobSpec(
        source_db_id=item.source_db_id,
        structure=structure,
        code=DftCode.QE,
        intent=CalculationIntent.SCF,
        points=kindex_points(pmg_structure, 0, item.kindex_max),
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
