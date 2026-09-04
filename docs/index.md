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

## Current data campaign

The first campaign measures **Quantum ESPRESSO no-spin SCF k-point
convergence** with a gamma-inclusive kindex schedule. It compares PseudoDojo
and SSSP PBEsol pseudopotentials.

The campaign extends an unconverged structure by three meshes at a time,
records every calculation in AiiDA, and exports one summary row per structure.

## Where to go

[Install the environment](installation/index.md){ .md-button .md-button--primary }
[Run the k-point campaign](campaigns/qe-kpoints.md){ .md-button }
[Use the results](results.md){ .md-button }
[Published records](published-records.md){ .md-button }
