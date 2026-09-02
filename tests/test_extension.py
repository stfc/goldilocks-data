from __future__ import annotations

import pandas as pd

from goldilocks_data.sweeps.extension import plan_well_not_ultra_extensions


def _summary(*source_ids: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_db_id": source_id,
                "well_kindex": 1,
                "ultra_converged": False,
            }
            for source_id in source_ids
        ]
    )


def _records(source_id: str, energies: list[float | None]) -> list[dict]:
    return [
        {
            "source_db_id": source_id,
            "kindex": kindex,
            "energy": energy,
        }
        for kindex, energy in enumerate(energies)
    ]


def test_plans_three_points_after_highest_valid_kindex() -> None:
    records = pd.DataFrame(_records("a", [-1.0, -1.1, -1.2]))

    plan = plan_well_not_ultra_extensions(records, _summary("a"), {"a": {0, 1, 2}})

    assert plan.clean_sources == 1
    assert plan.workchain_count == 3
    assert plan.extensions[0].source_db_id == "a"
    assert plan.extensions[0].current_max_kindex == 2
    assert plan.extensions[0].new_kindices == (3, 4, 5)


def test_skips_sources_with_missing_energy() -> None:
    records = pd.DataFrame(_records("a", [-1.0, None, -1.2]))

    plan = plan_well_not_ultra_extensions(records, _summary("a"), {"a": {0, 1, 2}})

    assert plan.dirty_sources == 1
    assert not plan.extensions


def test_skips_partial_target_without_leapfrogging() -> None:
    records = pd.DataFrame(_records("a", [-1.0, -1.1, -1.2]))

    plan = plan_well_not_ultra_extensions(records, _summary("a"), {"a": {0, 1, 2, 3}})

    assert plan.partially_existing_sources == 1
    assert not plan.extensions


def test_skips_completed_target_and_moves_to_next_source() -> None:
    records = pd.DataFrame(_records("a", [-1.0, -1.1]) + _records("b", [-2.0, -2.1]))
    existing = {"a": {0, 1, 2, 3, 4}, "b": {0, 1}}

    plan = plan_well_not_ultra_extensions(records, _summary("a", "b"), existing)

    assert plan.already_complete_sources == 1
    assert [item.source_db_id for item in plan.extensions] == ["b"]


def test_respects_source_and_workchain_limits() -> None:
    records = pd.DataFrame(_records("a", [-1.0]) + _records("b", [-2.0]) + _records("c", [-3.0]))

    plan = plan_well_not_ultra_extensions(
        records,
        _summary("a", "b", "c"),
        {source_id: {0} for source_id in ("a", "b", "c")},
        source_limit=2,
        workchain_limit=4,
    )

    assert len(plan.extensions) == 1
    assert plan.workchain_count == 3
