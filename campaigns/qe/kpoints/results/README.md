# Result snapshot

This directory is the analysis snapshot for the PseudoDojo QE SCF k-point
campaign. It has two tracked files and two local ones.

**Tracked** — small, and the record of what the last export saw:

| File | Purpose |
| --- | --- |
| `snapshot-metadata.json` | AiiDA profile, group, thresholds, ladder convention, timestamp, and counts |
| `manifest.json` | Dataset identity and the names of the files below |

**Local, not in git** — regenerated from the AiiDA group in the metadata, and
too large and churny to version:

| File | Purpose |
| --- | --- |
| `source-summary.csv` | One row per structure with convergence classification |
| `workchain-records.parquet` | Per-WorkChain values used to rebuild the summary |

`extend.py` reads all four from `--snapshot-dir` (this directory by default), so
rebuild `source-summary.csv` and `workchain-records.parquet` here before running
a cycle. The campaign publishes to PSDI when it finishes; until then the AiiDA
group is the authoritative record and these tables are a dated local view of it.

Every `kindex` column is **1-based**, rung 1 the Γ-only `(1, 1, 1)` mesh. The
base and the enumeration bound that built the ladder are in
`snapshot-metadata.json` (`kindex_base`, `max_kpoints_per_axis`); read them from
there, because a rung means nothing without its ladder.
