from __future__ import annotations

from enum import StrEnum


class CalculationIntent(StrEnum):
    """Kinds of calculations that can be submitted through AiiDA."""

    SCF = "scf"
    NSCF = "nscf"
    RELAX = "relax"
    PHONON = "phonon"
    MD = "md"
    TDDFT = "tddft"
    DFT_U = "dft_u"
