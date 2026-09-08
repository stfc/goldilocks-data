# Results

A dated view of the PseudoDojo QE SCF k-point campaign. The AiiDA group remains
the authoritative calculation record.

## Current snapshot

| Measure | Value |
| --- | ---: |
| WorkChains | 127,921 |
| Structures | 16,208 |
| Ultra converged | 15,474 |
| Ultra rate | 95.47% |
| Median ultra kindex | 4 |

Snapshot date: 1 September 2026. These figures are taken from
[`snapshot-metadata.json`](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/results/snapshot-metadata.json).

## The snapshot files

| File | Use it for | Where |
| --- | --- | --- |
| `snapshot-metadata.json` | Profile, AiiDA group, thresholds, ladder convention, timestamp, counts | [in the repo](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/results/snapshot-metadata.json) |
| `manifest.json` | Dataset identity and the file names | [in the repo](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/results/manifest.json) |
| `source-summary.csv` | One convergence-summary row per structure | regenerated locally |
| `workchain-records.parquet` | Calculation-level values behind the summary | regenerated locally |
| `analysis.ipynb` | Aggregation, quality checks, SSSP comparison | [in the repo](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/notebooks/analysis.ipynb) |

`source-summary.csv` and `workchain-records.parquet` are rebuilt from the AiiDA
group every campaign cycle and are not versioned; see
[`campaigns/qe/kpoints/results/README.md`](https://github.com/stfc/goldilocks-data/blob/main/campaigns/qe/kpoints/results/README.md).
They go to PSDI as a citable record when the campaign finishes.

## Provenance

The snapshot metadata identifies the profile and AiiDA group used for export.
For the live PseudoDojo campaign, the group is:

```text
goldilocks/qe-scf/nospin/pseudodojo
```

Return to AiiDA when you need the original inputs, outputs, process state, or
provenance graph.
