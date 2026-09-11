# Goldilocks Data

Setting up a DFT calculation means choosing numerical inputs that are hard to
choose well. A k-point mesh that is too coarse gives the wrong energy; one that
is too dense wastes compute.

Goldilocks learns those choices from systematic convergence calculations.
**This site is where those data are made and documented.**

!!! tip "Just want recommended inputs?"

    Then you want [Goldilocks Core](https://github.com/stfc/goldilocks-core).
    Give it a structure and a calculation intent; it selects suitable inputs.

    Read on if you want to reproduce a data campaign, inspect how convergence
    was labelled, or use the exported records.

## What this repository does

1. **Generate** — submit parameter sweeps through AiiDA with stable structure
   identifiers and calculation provenance.
2. **Analyse** — apply explicit convergence criteria and find the smallest
   acceptable input for each structure.
3. **Publish** — deposit documented snapshots as citable
   [published records](published-records.md) for research and model training.

Model training belongs in
[Goldilocks ML](https://stfc.github.io/goldilocks-ml/). End-user input
generation belongs in Goldilocks Core.

## What has been published

Three records, from two campaigns, all on MC3D structures with Quantum ESPRESSO:

| Campaign | Records |
| --- | --- |
| [No-spin SCF k-point convergence](campaigns/qe-kpoints.md) | the converged mesh per structure, and the full per-calculation output behind the paper |
| [nscf band structures](campaigns/qe-nscf-bands.md) | eigenvalues along the high-symmetry path, with Fermi level, metallicity and band gap |

Each [record](published-records.md) says what its columns mean and which
conventions it froze; each campaign page says how to reproduce the calculations
behind it.

## Where to go

[Published records](published-records.md){ .md-button .md-button--primary }
[Install goldilocks-data](installation/package.md){ .md-button }
[Data campaigns](campaigns/index.md){ .md-button }
