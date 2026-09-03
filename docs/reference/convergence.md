# Convergence criteria

Energy convergence is measured per atom over a tail of at least three k-point
calculations.

| Label | Maximum energy variation |
| --- | ---: |
| Medium | 5 meV/atom |
| Well | 3 meV/atom |
| Ultra | 1 meV/atom |

For each label, the selected kindex is the smallest point whose remaining tail
satisfies the threshold.

## Kindex meaning

Kindex follows the current gamma-inclusive schedule. For one structure, an
index maps deterministically to one distinct k-point mesh. Because lattice
geometry changes that mapping, comparisons between pseudopotential campaigns
use the actual mesh dimensions rather than assuming that equal numerical
kindices mean equal meshes.

Changing the schedule changes the scientific data contract and requires
regenerating dependent training data and models.
