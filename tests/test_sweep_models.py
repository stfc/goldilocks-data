from __future__ import annotations

from dataclasses import dataclass

from goldilocks_data.codes import DftCode
from goldilocks_data.intents import CalculationIntent
from goldilocks_data.sweeps import AiidaJobSpec, SweepAxis
from goldilocks_data.sweeps.kindex import kindex_points


@dataclass(frozen=True, slots=True)
class Reciprocal:
    a: float
    b: float
    c: float


@dataclass(frozen=True, slots=True)
class Lattice:
    reciprocal_lattice: Reciprocal
    reciprocal_lattice_crystallographic: Reciprocal


@dataclass(frozen=True, slots=True)
class Structure:
    lattice: Lattice

    def __len__(self) -> int:
        return 2


def test_kindex_points_are_generic_sweep_points() -> None:
    structure = Structure(
        lattice=Lattice(
            reciprocal_lattice=Reciprocal(1.0, 1.0, 1.0),
            reciprocal_lattice_crystallographic=Reciprocal(0.2, 0.2, 0.2),
        )
    )

    points = kindex_points(structure, 0, 1)

    assert points[0].axis_values == {SweepAxis.KINDEX.value: 0}
    assert points[0].k_mesh == (1, 1, 1)
    assert points[0].extras["kindex"] == 0


def test_aiida_job_spec_keeps_code_and_intent_separate_from_sweep_axis() -> None:
    spec = AiidaJobSpec(
        source_db_id="100115",
        structure=object(),
        code=DftCode.QE,
        intent=CalculationIntent.SCF,
        points=(),
    )

    assert spec.code is DftCode.QE
    assert spec.intent is CalculationIntent.SCF
