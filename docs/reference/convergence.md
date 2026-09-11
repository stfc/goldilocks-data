# Convergence criteria

Energy convergence is measured per atom over a tail of at least three k-point
calculations.

| Label | Maximum energy variation |
| --- | ---: |
| Medium | 5 meV/atom |
| Well | 3 meV/atom |
| Ultra | 1 meV/atom |

For each label, the selected kindex is the smallest point whose remaining tail
satisfies the threshold. The oscillation is `max - min` over the whole tail, so
a longer sweep can only make a label harder to earn, never easier.

These three numbers are the campaign's, from
[`campaign.yaml`](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/campaign.yaml).
`ConvergenceThresholds` in the package defaults to 10 / 5 / 1 meV per atom, so
pass the thresholds explicitly when reproducing a record rather than relying on
the defaults.

## Kindex meaning

Kindex follows the current gamma-inclusive schedule. For one structure, an
index maps deterministically to one distinct k-point mesh. Because lattice
geometry changes that mapping, comparisons between pseudopotential campaigns
use the actual mesh dimensions rather than assuming that equal numerical
kindices mean equal meshes.

Changing the schedule changes the scientific data contract and requires
regenerating dependent training data and models.
