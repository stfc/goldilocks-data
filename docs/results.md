# Results

The exported snapshot is a portable view of the PseudoDojo QE SCF k-point
campaign. The AiiDA group remains the authoritative calculation record.

## Current snapshot

| Measure | Value |
| --- | ---: |
| WorkChains | 127,921 |
| Structures | 16,208 |
| Ultra converged | 15,474 |
| Ultra rate | 95.47% |
| Median ultra kindex | 3 |

Snapshot date: 1 September 2026.

## Download or inspect

| File | Use it for | Link |
| --- | --- | --- |
| `source-summary.csv` | One convergence summary row per structure | [Download](https://raw.githubusercontent.com/stfc/goldilocks-data/main/campaigns/qe/kpoints/results/source-summary.csv) |
| `workchain-records.parquet` | Calculation-level values behind the summary | [Download](https://github.com/stfc/goldilocks-data/raw/refs/heads/main/campaigns/qe/kpoints/results/workchain-records.parquet) |
| `snapshot-metadata.json` | Profile, AiiDA group, thresholds, timestamp, and counts | [Inspect](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/results/snapshot-metadata.json) |
| `analysis.ipynb` | Aggregation, quality checks, and SSSP comparison | [Inspect](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/notebooks/analysis.ipynb) |

## Provenance

The snapshot metadata identifies the profile and AiiDA group used for export.
For the live PseudoDojo campaign, the group is:

```text
goldilocks/qe-scf/nospin/pseudodojo
```

Use the exported tables for analysis. Return to AiiDA when you need the
original inputs, outputs, process state, or provenance graph.
