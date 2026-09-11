# Data campaigns

A campaign is one reproducible combination of:

- an electronic-structure code;
- a calculation task;
- a pseudopotential family;
- an ordered parameter schedule;
- submission and convergence rules.

Every [published record](../published-records.md) comes out of one, and a
campaign page says what the settings were and how to reproduce the calculations
behind the record.

## Campaigns and what they published

| Campaign | Published as | Guide |
| --- | --- | --- |
| QE no-spin SCF k-point convergence | [`52713-55d86`](https://data-collections.psdi.ac.uk/records/52713-55d86) · [`mcpnq-g1j55`](https://data-collections.psdi.ac.uk/records/mcpnq-g1j55) | [Open](qe-kpoints.md) |
| QE nscf band structures | [`r3byg-xp284`](https://data-collections.psdi.ac.uk/records/r3byg-xp284) | [Open](qe-nscf-bands.md) |

The two SCF records are two views of one body of calculations, not two
campaigns: one is the converged mesh per structure, the other the full
per-calculation output.

Only campaigns that have published something appear here. A code or task is not
listed merely because support is planned.
