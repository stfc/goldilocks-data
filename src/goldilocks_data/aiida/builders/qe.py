from __future__ import annotations

from typing import Any

from goldilocks_data.aiida.config import AiidaScfConfig
from goldilocks_data.sweeps.models import SweepPoint


def check_qe_pseudo_family_support(pseudo_group: Any, structure: Any) -> str | None:
    """Return ``None`` when the QE pseudo family covers the structure."""

    try:
        pseudo_group.get_recommended_cutoffs(structure=structure, unit="Ry")
        pseudo_group.get_pseudos(structure=structure)
    except Exception as exception:
        return str(exception)
    return None


def build_qe_pw_scf_builder(
    code: Any,
    pseudo_group: Any,
    structure: Any,
    point: SweepPoint,
    config: AiidaScfConfig,
) -> Any:
    """Build a QE ``PwBaseWorkChain`` builder for one SCF point."""

    from aiida import orm
    from aiida.orm import KpointsData
    from aiida_quantumespresso.common.types import ElectronicType, SpinType
    from aiida_quantumespresso.workflows.pw.base import PwBaseWorkChain

    if point.k_mesh is None:
        raise ValueError("QE pw.x SCF submission requires point.k_mesh")

    overrides = {
        "pseudo_family": pseudo_group.label,
        "pw": {
            "parameters": {
                "SYSTEM": {"degauss": config.degauss_ry},
            },
        },
    }
    builder = PwBaseWorkChain.get_builder_from_protocol(
        code=code,
        structure=structure,
        protocol="moderate",
        electronic_type=ElectronicType.METAL,
        spin_type=SpinType.NONE,
        overrides=overrides,
    )
    if config.nbnd is not None:
        parameters = builder.pw.parameters.get_dict()
        parameters.setdefault("SYSTEM", {})["nbnd"] = int(config.nbnd)
        builder.pw.parameters = orm.Dict(dict=parameters)

    kpoints = KpointsData()
    kpoints.set_kpoints_mesh(point.k_mesh)
    builder.kpoints = kpoints
    builder.pw.metadata.options.resources = {
        "num_machines": config.num_machines,
        "num_mpiprocs_per_machine": config.num_mpiprocs_per_machine,
    }
    builder.pw.metadata.options.max_wallclock_seconds = config.max_wallclock_seconds
    builder.clean_workdir = orm.Bool(False)
    return builder


def qe_pw_scf_extras(
    source_db_id: str,
    pseudo_group: Any,
    point: SweepPoint,
    builder: Any,
    config: AiidaScfConfig,
) -> dict[str, Any]:
    """Build searchable extras for one QE pw.x SCF WorkChain."""

    system = builder.pw.parameters.get_dict().get("SYSTEM", {})
    extras = {
        "source_db_id": str(source_db_id),
        "calc_type": "scf",
        "code": "qe",
        "sweep_axis": ",".join(point.axis_values),
        "pp": pseudo_group.label,
        "smearing_type": system.get("smearing"),
        "degauss": system.get("degauss"),
        "nspin": system.get("nspin", 1),
        "retention_cleaned": False,
    }
    extras.update(point.extras)
    if config.nbnd is not None:
        extras["nbnd"] = int(config.nbnd)
    return extras
