# Add Quantum ESPRESSO and SCARF

This page adds the QE calculation plugin, pseudopotential manager, SCARF
computer, and a remote `pw.x` executable to the AiiDA environment.

## Install the plugins

Activate the environment created on the previous page, then run:

```bash
uv pip install aiida-quantumespresso aiida-pseudo
verdi plugin list aiida.calculations
```

The plugin list should contain entries beginning with `quantumespresso`.

## Install the pseudopotentials

The current PseudoDojo campaign uses the PBEsol, scalar-relativistic,
`standard` protocol:

```bash
aiida-pseudo install pseudo-dojo \
  -v 0.4 -x PBEsol -r SR -p standard -f upf -s high
verdi -p goldilocks group list -a
```

Expected family:

```text
PseudoDojo/0.4/PBEsol/SR/standard/upf
```

## Register SCARF

First make sure your normal SSH configuration works:

```bash
ssh scarf
```

Create `scarf.yaml`, replacing the angle-bracketed values:

```yaml
label: scarf
description: STFC SCARF
hostname: <SSH host or alias>
transport: core.ssh_async
scheduler: core.slurm
shebang: '#!/bin/bash'
work_dir: /work4/<project>/<username>/aiida
mpirun_command: srun -u -n {tot_num_mpiprocs}
mpiprocs_per_machine: 32
use_double_quotes: false
prepend_text: ''
append_text: ''
```

Register and test it:

```bash
verdi -p goldilocks computer setup -n --config scarf.yaml
verdi -p goldilocks computer configure core.ssh_async scarf
verdi -p goldilocks computer test scarf
```

## Register `pw.x`

Create `qe-pw.yaml`. Use the executable path and module name supplied by the
current SCARF software stack:

```yaml
label: qe-pw
description: Quantum ESPRESSO pw.x
default_calc_job_plugin: quantumespresso.pw
computer: scarf
filepath_executable: <absolute path to pw.x>
use_double_quotes: true
prepend_text: |+
  module load <Quantum ESPRESSO module>
append_text: ''
```

```bash
verdi -p goldilocks code create core.code.installed -n --config qe-pw.yaml
verdi -p goldilocks code show qe-pw@scarf
```

## Final checks

```bash
verdi -p goldilocks status
verdi -p goldilocks computer test scarf
verdi -p goldilocks code list
verdi -p goldilocks group list -a
```

See the
[official plugin installation guide](https://aiida-quantumespresso.readthedocs.io/en/latest/installation/index.html)
for current compatibility information.

Continue with [the QE SCF k-point campaign](../campaigns/qe-kpoints.md).
