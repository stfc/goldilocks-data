from __future__ import annotations

from enum import StrEnum


class DftCode(StrEnum):
    """DFT codes supported by Goldilocks data workflows."""

    QE = "qe"
    VASP = "vasp"
    CP2K = "cp2k"
    CASTEP = "castep"
