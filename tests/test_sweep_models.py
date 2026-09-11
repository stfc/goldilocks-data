from __future__ import annotations

from pymatgen.core import Lattice, Structure

from goldilocks_data.codes import DftCode
from goldilocks_data.intents import CalculationIntent
from goldilocks_data.kmesh import kindex_points
from goldilocks_data.sweeps import AiidaJobSpec, SweepAxis


def test_kindex_points_are_generic_sweep_points() -> None:
    # Diamond silicon: rung 1 is the Gamma-only mesh, as it is on every ladder.
    structure = Structure.from_spacegroup("Fd-3m", Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    points = kindex_points(structure, 1, 2)

    assert points[0].axis_values == {SweepAxis.KINDEX.value: 1}
    assert points[0].k_mesh == (1, 1, 1)
    assert points[0].extras["kindex"] == 1


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
