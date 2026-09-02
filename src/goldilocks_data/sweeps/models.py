from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from goldilocks_data.codes.models import DftCode
from goldilocks_data.intents.models import CalculationIntent


class SweepAxis(StrEnum):
    """Supported SCF sweep dimensions."""

    KINDEX = "kindex"
    PSEUDOPOTENTIAL = "pp"
    CODE = "code"
    SPIN_TYPE = "spin_type"
    NSPIN = "nspin"
    MAGNETICITY = "magneticity"
    SOC = "soc"
    SMEARING = "smearing"
    CUTOFF = "cutoff"


@dataclass(frozen=True, slots=True)
class SweepPoint:
    """One point in a multidimensional SCF sweep."""

    axis_values: dict[str, Any]
    k_mesh: tuple[int, int, int] | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScfSweepSpec:
    """A source structure and explicit SCF sweep points to submit."""

    source_db_id: str
    structure: Any
    points: tuple[SweepPoint, ...]


@dataclass(frozen=True, slots=True)
class AiidaJobSpec:
    """A source structure, calculation intent, code, and explicit sweep points."""

    source_db_id: str
    structure: Any
    code: DftCode
    intent: CalculationIntent
    points: tuple[SweepPoint, ...]
