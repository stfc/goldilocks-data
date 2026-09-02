# Result snapshot

This directory is the portable analysis snapshot for the PseudoDojo QE SCF
k-point campaign.

| File | Purpose |
| --- | --- |
| `snapshot-metadata.json` | AiiDA profile, group, thresholds, timestamp, and row counts |
| `source-summary.csv` | One row per structure with convergence classification |
| `workchain-records.parquet` | Per-WorkChain values used to rebuild the summary |
| `manifest.json` | Dataset identity and relationships between the files |

The AiiDA group named in the metadata is the authoritative provenance source.
These files are a dated export, not a replacement for the AiiDA database.
