# Calculations

Every [published record](../published-records.md) came out of one set of
calculations, defined by:

- an electronic-structure code;
- a calculation task;
- a pseudopotential family;
- an ordered parameter schedule;
- explicit submission and convergence rules.

A page here gives those settings, a script that runs the same calculations
yourself, and what you can do with the published data without running anything.

## What produced what

| Calculations | Published as |
| --- | --- |
| [QE SCF k-point sweeps](qe-kpoints.md) | [`52713-55d86`](https://data-collections.psdi.ac.uk/records/52713-55d86) · [`mcpnq-g1j55`](https://data-collections.psdi.ac.uk/records/mcpnq-g1j55) |
| [QE nscf band structures](qe-nscf-bands.md) | [`r3byg-xp284`](https://data-collections.psdi.ac.uk/records/r3byg-xp284) |

The two SCF records are two views of one body of calculations: one is the
converged mesh per structure, the other the full per-calculation output.
