# Result snapshot

This directory is the portable analysis snapshot for the PseudoDojo QE SCF
k-point campaign.

| File | Purpose |
| --- | --- |
| `snapshot-metadata.json` | AiiDA profile, group, thresholds, timestamp, and row counts |
| `source-summary.csv` | One row per structure with convergence classification |
| `workchain-records.parquet` | Per-WorkChain values used to rebuild the summary |
| `manifest.json` | Dataset identity and relationships between the files |

Every `kindex` column here is **1-based**, with rung 1 the Γ-only `(1, 1, 1)`
mesh, built with a per-axis enumeration bound of 50. Both are recorded in
`snapshot-metadata.json` as `kindex_base` and `max_kpoints_per_axis`; read them
from there rather than assuming, because a rung means nothing without its
ladder.

The AiiDA group named in the metadata is the authoritative provenance source.
These files are a dated export, not a replacement for the AiiDA database.
