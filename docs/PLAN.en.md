# goldilocks-data

> The single source-of-truth document for this repo. Covers: ecosystem role,
> Phase A/B/C strategy, physics decisions, adaptive sweeps, the Parquet schema,
> package layout, pseudopotential strategy, convergence parameters, and the
> local + SCARF install/config flow.
> Bilingual: [PLAN.md](PLAN.md) is the Chinese primary; this is the English mirror,
> kept in sync.
>
> Module-level implementation detail lives in each `__init__.py` / docstring;
> this document covers cross-module design and ops only.

---

## 1. Context — UKRI Goldilocks ecosystem

UKRI Goldilocks (EP/Z530657/1) produces "just right" DFT inputs
(ecutwfc / k-grid / smearing / pseudo / SLURM scripts) for users. Four sibling
repositories, in dataflow order:

| Repo | Role | Relationship to us |
|---|---|---|
| **goldilocks-data** (this repo) | DFT data generation; AiiDA + QE on SCARF; emits Parquet | — |
| `goldilocks-models` | Trains ML on our Parquet; exports versioned artefacts | downstream |
| `goldilocks-core` | Recommendation + parsing; provides `infer_features`, k-mesh schedule, classifiers | upstream (we call it) |
| `goldilocks-webapp` | Frontend | indirect |

**Two contracts**:

- → `goldilocks-models`: Parquet rows. Each row = one SCF, tagged
  `under` / `just_right` / `over` per `(structure, family)`. Schema in §6.
- ← `goldilocks-core`: hard dependency (no stub). `kmesh.build_kmesh_entries`,
  `infer_features`, `derive_starting_magnetization`, classifier wrappers. If core
  is missing the data is unusable — by design. Inside the conda env, reference the
  sibling path with `pip install -e ../1-goldilocks-core`.

**Two-track architecture**: the offline track (`goldilocks-data` → `goldilocks-models`)
produces versioned model artefacts + a manifest into shared storage; the online track
(`goldilocks-webapp` → `goldilocks-core`) loads models from that manifest at startup.
The tracks are decoupled through the artefact store — data / models need not be online
when recommendations are served.

---

## 2. Phase 1 scope

| Dimension | Phase 1 |
|---|---|
| DFT code | Quantum ESPRESSO 7.2 (`pw.x`, SCARF EasyBuild shared install `QuantumESPRESSO/7.2-foss-2023a`) |
| Calc type | SCF only (no relax / bands / DOS / phonon / MD) |
| Structures | Materials Cloud MC3D PBEsol v2 — all 33,142 |
| Sweep axis | three adaptive convergence stages: **cutoff → degauss (metals only) → kpoints**, one index per round (see §5) |
| XC | PBEsol (committed via the pseudo family) |
| HPC | SCARF (STFC) |

Out of Phase 1: VASP / CP2K / ABINIT, relax / bands / DOS / phonon / MD,
USPP / GBRV pseudos, multi-user PostgreSQL, AFM enumeration, DFT+U.

---

## 3. Phase A → B → C strategy

### 3.1 Phase A — single family, single-methodology baseline

| Item | Value |
|---|---|
| Family (Phase A uses) | `PseudoDojo/0.4/PBEsol/SR/standard/upf` (1 family, "PD-A") |
| Families (preloaded in env) | see §12; reused by Phase B/C |
| Structures | MC3D, all 33,142 |
| nspin | MC3D `total/abs_mag` double threshold (zero-cost, see §4) |
| SOC | off |
| Convergence sweeps | three stages: **cutoff (sweep ecutwfc) → degauss (metals only) → kpoints (sweep kindex)**, one index per round (§5) |
| ecutwfc / degauss | both swept (Stage 1 / Stage 2); insulators lock degauss at 0.01 |
| Target SCF count | ~400k–600k (per structure: cutoff ~11 + degauss ~5 metals only + kpoints ~5–7) |
| Driver task | feed `goldilocks-models` `kpoints` task |
| Gate to B | `kpoints` model trained, kindex MAE < 1.5; Parquet snapshot v0.1 released |

**Why 1 family + all 33k (not 5k sample × 5 families)**: compute cost is comparable
(~165k vs 125k SCF), but element coverage is better (33k spans 70+ elements), giving
the model side a richer element-disjoint split. Methodology comparisons (NC vs PAW,
std vs stringent, PBE vs PBEsol vs LDA) are deferred to Phase B.

### 3.2 Phase B — multi-family, no SOC

Starts once the Phase A `kpoints` model is trained and live. Adds 6–10 families
(NC v0.4 PBE/PBEsol/LDA × std+stringent, PAW JTH v1.0 × std+stringent), same 33k
structures, same nspin decision. Drives the `pseudo` + `resources` tasks.

### 3.3 Phase C — SOC, transfer learning

Starts after Phase B. Runs only the heavy-element subset (`contains_heavy=True`)
≈ 1.5k structures with the FR family (`PseudoDojo/0.4/PBEsol/FR/standard/upf`):

```python
spin_type = SpinType.SPIN_ORBIT   # -> noncolin=True, lspinorb=True, nspin=4
```

aiida-qe auto-exposes `angle1` / `angle2` (initial-moment 3D direction, default
along z); the Phase C baseline leaves them alone, deferring true non-collinear
magnetism (spiral / canted) to Phase 1.5/2. ML path: use the `kpoints` model trained
on Phase A/B SR data as a warm start, reducing the sample count the SOC subset needs.

### 3.4 SpinType overview (why only 3 are used)

| SpinType | nspin | noncolin | lspinorb | Physics | When |
|---|---|---|---|---|---|
| `NONE` | 1 | F | F | closed-shell, non-magnetic | Phase A/B even electrons, non-magnetic |
| `COLLINEAR` | 2 | F | F | spin along one axis ↑↓, FM/AFM/FiM | Phase A/B odd electrons or magnetic |
| `NON_COLLINEAR` | 4 | T | F | spin in 3D, no relativity | **skipped** |
| `SPIN_ORBIT` | 4 | T | T | non-collinear + SOC, full relativity | Phase C `contains_heavy` |

**Skipping pure `NON_COLLINEAR`**: MC3D is mostly ordinary crystals; non-collinear
order is the minority, and when it matters the material is usually heavy → SOC cannot
be ignored → go straight to SPIN_ORBIT. Phase C jumps directly there.

---

## 4. Per-structure physics decisions

The builder makes 2 decisions per structure (degauss / starting_magnetization are
outsourced to aiida-qe):

```python
# Step 1: nspin / spin_type (multi-source fallback, see magnetism_prior)
n_electrons = sum(pseudo_family.get_pseudos(structure)[s.kind_name].z_valence
                  for s in structure.sites)
is_odd      = (int(n_electrons) % 2) == 1
is_magnetic = magnetism_prior(structure)
spin_type   = SpinType.COLLINEAR if (is_odd or is_magnetic) else SpinType.NONE

# Step 2: SOC (Phase C)
if PHASE_C and features.contains_heavy:
    spin_type = SpinType.SPIN_ORBIT

# metallicity_guess: kept as a feature only (written to extras / Parquet);
# it no longer decides degauss nor switches occupations.
metallicity_guess = classifiers.predict_metallicity(structure)
```

`magnetism_prior(structure)` decision tree (multi-source fallback):

```python
MAGNETIC = (MAGNETIC_3D | MAGNETIC_4D | MAGNETIC_5D | MAGNETIC_4F)  # element sets

def magnetism_prior(structure) -> bool:
    elems   = structure.get_symbols_set()
    mc3d_id = structure.base.extras.get('mc3d_id')
    # (a) strong prior: MC3D PBEsol-v1 magnetism backfill (trusted on its 8,913 ids)
    if mc3d_id and v1_pkl_says_magnetic(mc3d_id):
        return True
    # (b) chemistry rule: any magnetic element -> treat as magnetic candidate
    if elems & MAGNETIC:
        return True
    # (c) weak prior: MC3D PBEsol-v2 converged to any atomic |m| > 0.1
    if mc3d_id and v2_pkl_max_atomic_mag(mc3d_id) > 0.10:
        return True
    return False
```

**Key constraints**:

- **Odd electron count is a hard constraint**: a closed shell cannot hold an odd
  number of electrons → must use nspin=2, no false positive.
- **MC3D v2 `total_magnetization` is not trustworthy alone**: of 481 v1-magnetic /
  v2-NM systems, 94% contain Fe/Mn/Co/Ni/Cr; v2 false negatives run 7–10%. The decision
  must layer v1 + the chemistry rule.
- **The chemistry rule is broad inclusion**: any magnetic element turns nspin=2 on even
  if v1/v2 both say NM; the cost is a few systems converging to 0 (~5–10% wasted
  walltime), the benefit is never missing a magnetic ground state.
- **Can only seed FM/FiM**: the aiida-qe stock COLLINEAR protocol gives same-kind atoms
  the same positive sm, so initial ↑↑↑↑ → FM or NM, **never spontaneously AFM**. AFM
  requires kind-split + sign-flipped sm (Phase 1.5).

### 4.1 Globally fixed parameters (all Phase 1 structures, insulators included)

Uniform `occupations='smearing'`, `smearing='cold'`, `degauss=0.01 Ry`, including
insulators:

- **Smearing ≠ treating it as a metal**: smearing only affects occupations / total
  energy / SCF during BZ integration, **never the eigenvalues of H**. `output_band`
  `bands[k,n]` is always the diagonalization result, so HOMO/LUMO/gap are always
  computable (`gap = bands[:,n_occ].min() − bands[:,n_occ-1].max()`).
- **Insulator contamination is negligible**: measured on Si (8e/cell) the entropy
  correction ≈ 0.013 meV/atom (≪ the 1 meV/atom threshold).
- **cold smearing's σ⁴ residual**: the leading term of E(σ)−E(0) is O(σ⁴)
  (Fermi-Dirac/Gauss are σ², MP-N is σ^(2N+2)). At σ=0.01 Ry: ordinary metals
  0.1–0.5 meV/atom, steep-DOS metals 1–2 meV/atom.
- **Convergence verdict is unaffected by smearing**: within a sweep σ is constant →
  the smearing error is a constant offset that cancels in the §5.5 max-min window. That
  is exactly why the criterion uses the sweep-window spread, not absolute energy.
- **Bonus**: a free metallicity y-label — `gap > 0.05` insulator / `gap < −0.01` metal
  (band overlap) / else borderline. The builder's `metallicity_guess` vs measured gap
  forms an (X,y) pair feeding the Phase 1.5 `metallicity` task.

Other fixed parameters: `tprnfor=true`, `tstress=true`;
`nbnd ≥ n_occ + max(4, ⌈0.5·n_occ⌉)` (so HOMO/LUMO are computable from `output_band`);
`conv_thr=2e-10 Ry/atom` (aligned with MC3D); `mixing_beta=0.4`, `mixing_mode=plain`,
`diagonalization=david`, `electron_maxstep=200`; `tot_charge=0`; vdW / Hubbard U: off;
`max_iterations=1` (PwBaseWorkChain does not retry; failure immediately sets
`scf_failed=True`, and the sweep window itself absorbs sporadic noise).

---

## 5. Adaptive convergence sweeps (cutoff → degauss → kpoints, all in Phase A)

> **Decision (2026-06-16): all three convergence stages run in Phase A** — cutoff,
> degauss (metals only), kpoints. Lock the earlier axes before sweeping the later ones
> (the axes are orthogonal), orchestrated by a per-structure pipeline WorkChain.

### 5.1 Overview

Each (structure, family) runs three stages in order, chained by one
`ConvergencePipelineWorkChain`:

```
Stage 1  cutoff   sweep ecutwfc  @ coarse fixed k=0.30, degauss=0.01
                  -> converged_ecutwfc  + classify metal/insulator (gap, §5.3)
Stage 2  degauss  sweep degauss  @ converged ecutwfc, coarse k=0.30   (METALS ONLY)
                  -> converged_degauss  (insulator: skip, degauss=0.01)
Stage 3  kpoints  sweep kindex   @ converged ecutwfc + degauss
                  -> converged_kindex
```

Orthogonality: cutoff is a pseudo/element property; degauss matters only for metals
(insulators' gap makes occupations smearing-insensitive); kpoints is BZ sampling. Lock
the earlier axes first to avoid a multi-D grid explosion. `round_number` increments
globally across stages; `sweep_axis ∈ {cutoff, degauss, kmesh}` + `sweep_index`
determine each round.

### 5.2 The three stage schedules

**Stage 1 — cutoff (sweep ecutwfc)**: anchor the start 10 Ry below the PseudoDojo `low`
tier, step 5 Ry up to `high`+15; this stage uses a coarse fixed k=0.30 and degauss=0.01.

```python
# config.py
ECUTRHO_RATIO          =   4.0   # NC pseudo; PAW uses 8.0
CUTOFF_START_OFFSET_RY = -10.0   # start = low_tier - 10  (deep under-converged)
CUTOFF_END_OFFSET_RY   =  15.0   # end   = high_tier + 15 (reach over-converged)
CUTOFF_STEP_RY         =   5.0
CUTOFF_FLOOR_RY        =  20.0   # numerical floor; start never below this
KDIST_FOR_CUTOFF_SWEEP =   0.30  # A^-1, coarse fixed k-mesh for cutoff + degauss stages
# tiers from family.get_recommended_cutoffs(structure, stringency='low'|'high').
# SSSP / no-tier families: all tiers degrade to 'normal'.
# Example CdTe on PD-A (low=94, normal=102, high=114):
#   schedule = [84, 89, 94, 99, 102, 107, 112, 114, 117, 122, 127]  (11 points)
```

`low−10` start guarantees a deeply under-converged start with gradient; at normal
(1 meV/atom threshold) it is just_right; high+15 gives over. The cutoff stage borrows
only the aiida-qe `fast` protocol's λ (k=0.30); the base stays `protocol='moderate'`
(rigorous conv_thr/mixing), not its widened degauss/conv_thr.

**Stage 2 — degauss (sweep degauss, metals only)**: on the Stage 1 converged ecutwfc and
the same coarse k=0.30, sweep degauss from wide to narrow, cold smearing:

```python
DEGAUSS_SCHEDULE_RY = [0.03, 0.02, 0.015, 0.01, 0.005]   # metals only; cold smearing
```

Insulators skip it (degauss locked at 0.01, §5.3 gate). For metals k and degauss are
coupled; this uses a "coarse-k degauss → fixed-degauss k sweep" sequential approximation
(fine for the baseline; a full k–degauss 2D sweep is left for later).

**Stage 3 — kpoints (sweep kindex, from core)**:

```python
from goldilocks_core.kmesh import build_kmesh_entries
entries = build_kmesh_entries(structure)   # ~30-90 entries per structure
# entries[0].k_index == 1  <=>  Gamma-only (mesh = (1,1,1))
```

- kindex starts at 1 (Γ-only); not comparable across structures, `k_pra` is.
- Cache: computed once, written to `StructureData.extras['kmesh_plan']` (with
  `core_kmesh_api_version` = core git SHA); core upgrade → SHA changes → auto-recompute.
- Each Parquet row records `schedule_generator` / `schedule_generator_version` /
  `schedule_max_index`.

### 5.3 Metal/insulator classification (at the cutoff stage, gates degauss)

Every cutoff SCF yields a gap; classify via §4.1's `metallicity_from_gap` (gap>0.05
insulator / <−0.01 metal / else borderline). Being the earliest stage, its label
**gates Stage 2**: `insulator` → skip degauss (lock 0.01); `metal` / `borderline` → run
degauss convergence. The coarse k=0.30 gap is only good for rough classification;
`borderline` is the catch-all, re-checkable at the converged k. `metallicity_guess`
(builder-time ML prediction) is still recorded as a feature, forming an (X,y) pair with
the measured gap for the model metallicity task.

### 5.4 Driver — per-structure ConvergencePipelineWorkChain

Each (structure, family) is orchestrated by **one `ConvergencePipelineWorkChain`** over the
three stages; the daemon handles lifecycle — **no separate monitor process needed**:

```python
class ConvergencePipelineWorkChain(WorkChain):
    """Run the three convergence stages for one (structure, family), in order.

    cutoff -> (degauss if metal) -> kpoints, forwarding converged values.
    """
    # outline:
    #   run_cutoff  -> CutoffConvergenceWorkChain  -> converged_ecutwfc + metallicity
    #   run_degauss -> DegaussConvergenceWorkChain (skipped if insulator) -> converged_degauss
    #   run_kpoints -> KpointsConvergenceWorkChain(ecutwfc, degauss) -> converged_kindex
```

The three stage WCs all inherit `BaseConvergenceWorkChain` (shared setup /
should_continue / _is_converged / finalize); each subclass only defines "which axis to
sweep + which values to lock":

```python
class CutoffConvergenceWorkChain(BaseConvergenceWorkChain):
    # sweep ecutwfc; lock k=0.30, degauss=0.01; sweep_axis='cutoff', sweep_kind='sweep_cutoff'
    # outputs: convergence_status, converged_index, converged_ecutwfc, metallicity

class DegaussConvergenceWorkChain(BaseConvergenceWorkChain):
    # sweep degauss; lock ecutwfc, k=0.30; METALS ONLY; sweep_axis='degauss'
    # outputs: convergence_status, converged_index, converged_degauss

class KpointsConvergenceWorkChain(BaseConvergenceWorkChain):
    # sweep kindex; lock ecutwfc + degauss; sweep_axis='kmesh'
    # outputs: convergence_status, converged_index, converged_kindex
```

Each stage WC internally submits PwBaseWorkChain at sweep_index=0,1,...,N until
converged (§5.5) or max_rounds; exit codes 401 ERROR_SCF_FAILED / 402 ERROR_MAX_ROUNDS.

**Fan-out is trivial**: `for struct in pool: submit(ConvergencePipelineWorkChain,
structure=struct, ...)`, then let the daemon take over all 33k pipeline WCs. Daemon dies
/ Mac reboots → after restart they resume from pickle (WorkChain checkpointing). **The
inflight cap is a daemon config**, no hand-written gate:

```bash
verdi config set daemon.worker_process_slots 200   # active-WC ceiling
```

Most WCs sit in "waiting for inner SCF" and don't occupy an active slot; slot=200 is
fine at steady state.

**Reuse charge density across rounds (saves CPU, no long-term storage)**: the charge
density depends only on the real-space grid (ecutrho), **not on k**, so within a stage the
next round's SCF restarts from the previous round's charge density (`startingpot='file'`
+ `parent_folder`), cutting SCF iterations (wavefunctions can't be reused since k
changes). **Storage stays bounded**: the charge density lives on SCARF scratch only
between two consecutive rounds and is wiped with the previous round's workdir once
consumed (§13.2's stash source_list never includes it). Steady-state overhead ≈ the
number of active sweeps (~200 transient copies), not 33k×N.

### 5.5 Convergence criterion (`labels.py`)

**Criterion (shared by all three stages, cutoff/degauss/kpoints): over the last 5 sweep
points, both energy and forces must converge — stop only when both hold.** We care about
energy and forces only (stress/gap/magnetization are still recorded each round but don't
enter the criterion). The window is 5 points (not 3) to resist non-monotonic oscillation
of convergence in metals / small-gap systems and avoid a chance-plateau false positive.

```python
ENERGY_TOL_EV_PER_ATOM = 1.0e-3   # 1 meV/atom
FORCE_TOL_EV_PER_A     = 5.0e-2   # 0.05 eV/A
N_WINDOW               = 5        # last 5 sweep points (was 3; 5 resists oscillation)
# converged = energy window AND force window both within tol
# earliest verdict at sweep_index >= 4 (need 5 points); judged per sweep_axis
```

Derived labels (backfilled to all rows of the same `(struct, family, sweep_axis)`):
- `convergence_label_energy` / `convergence_label_forces` ∈ {under, just_right, over, null}
  (each by sweep_index relative to converged_at_index)
- `converged_at_index` (latest index where **both** energy and forces hold),
  `dE_window_meV_per_atom`, `dF_window_eV_per_A`, `converged_at_ecutwfc`,
  `converged_at_degauss`, `converged_at_kindex`
- recorded only, not in the criterion: `stress_max`, `band_gap_estimate`,
  `total_magnetization`

`just_right` is the y-label source for the model `cutoff` / `degauss` / `kpoints` tasks
(per sweep_axis).

### 5.6 Four-layer safeguards

| Layer | Trigger | Behavior |
|---|---|---|
| 1. inner SCF fail | exit_status ≠ 0 | `max_iterations=1` no retry; set `scf_failed=True`, terminate that sweep_axis, keep data |
| 2. per-stage round cap | one sweep_axis hits 10 rounds unconverged | hard halt, set `convergence_status='max_rounds_exhausted'` |
| 3. per-structure wallclock budget | cumulative > 24h per (struct, family) | halt, set `convergence_status='budget_exceeded'` |
| 4. Γ-pathological (kmesh only) | round1 vs round2 ΔE/atom > 100 meV | set `gamma_pathological=True`; the convergence window skips the Γ-only point |

**`convergence_status` values (distinct negative-sample meanings, decision 6)**:
`converged` / `scf_failed` (SCF crashed) / `schedule_exhausted` (that stage's schedule ran
out before the criterion was met, ≠ round cap) / `max_rounds_exhausted` (hit the 10-round
cap) / `budget_exceeded` (over the wallclock budget). The model treats the latter four as
different kinds of negative samples.

> TODO: the `gamma_pathological` 100 meV threshold is a placeholder; calibrate on a
> 100-structure MC3D sample.

---

## 6. Schema — Parquet row contract

Each row = one PwBaseWorkChain SCF. Partitioned by `structure_id`:
`data/processed/v<X.Y.Z>/structure_id=<MC3D-ID>/*.parquet`. Full field definitions in
`src/goldilocks_data/schema.py` (`Record` pydantic); this section lists names + roles.

**Provenance (metadata)**: `workchain_uuid`, `calculation_uuid`,
`aiida_archive_version`, `goldilocks_data_version`, `git_sha`, `submitted_at`,
`submitter`, `schedule_generator(_version)`, `schedule_max_index`.

**Input — structure features (feature)** (from `goldilocks_core.infer_features`,
flattened): `source_db`, `source_id`, `formula`, `spacegroup_number`,
`crystal_system`, `n_atoms`, `cell_volume`, `element_set`, `n_electrons_neutral`,
`contains_lanthanide`, `contains_actinide`, `contains_heavy`, `heavy_elements`,
`likely_magnetic`, `magnetic_elements`, `is_metal_guess`, `dimensionality_larsen`,
`anisotropy_ratio`.

**Input — pseudo + numerics (feature)**: `pseudo_family`, `pseudo_selection_reason`,
`pseudo_source`, `pseudo_method`, `pseudo_functional`, `pseudo_accuracy`,
`pseudo_version`, `pseudo_relativistic`, `pseudo_format`, `ecutwfc`, `ecutrho`,
`k_mesh`, `k_offset`, `k_distance`, `k_density_mp`, `k_linedensity_jarvis`,
`sweep_axis`, `kindex`, `k_pra`, `n_reduced_kpoints`, `smearing_type`, `degauss`,
`mixing_beta`, `conv_thr`.

**Input — physics decisions (feature)**: `nspin`, `noncolin`, `lspinorb`,
`soc_enabled`, `magnetic_state_decision`, `starting_magnetization_source`,
`metallicity_guess`, `vdw_used`, `cutoff_source`, `occupations`.

**Output — physics (label)**: `total_energy`, `fermi_energy`, `forces_max`,
`stress_max`, `band_gap_estimate`, `total_magnetization`, `n_scf_iterations`,
`final_scf_accuracy`, `exit_status`, `warnings`.

**Output — convergence labels (derived_label, judged per sweep_axis)**:
`convergence_label_energy`, `convergence_label_forces`, `converged_at_index`,
`converged_at_ecutwfc`, `converged_at_degauss`, `converged_at_kindex`, `convergence_status`,
`metallicity`, `dE_window_meV_per_atom`, `dF_window_eV_per_A`, `round_number`,
`gamma_pathological`, `scf_failed`. (`sweep_axis ∈ {cutoff, degauss, kmesh}`; both energy
and forces enter the criterion, §5.5; 5-point window.)

**Output — resources (label, collected by `resources.py`)**: request side
`n_nodes_requested` / `n_mpi_per_node_requested` / `n_omp_threads` /
`walltime_requested_s` / `mem_per_node_requested_mb`; actual side (sacct + aiida.out)
`peak/avg_memory_mb_actual` / `walltime_actual_s` / `slurm_exit_code` / `slurm_state`
/ `qe_*` / `memory_efficiency` / `walltime_efficiency`; parallelism `npool` / `nbgrp`
/ `ndiag` / `parallelization_strategy`.

**Lifecycle + audit (metadata)**: `process_state` (AiiDA-native), `exit_status`,
`is_smoke_test`, `mc3d_*` (`pseudo_flagged_suboptimal` / `afm_likely` /
`high_pressure` / `theoretical_only` / `total_magnetization` /
`absolute_magnetization` / `band_gap`). `phase` is derived at export, not stored in
extras.

**PK / UUID / source_id**: PK is the local DB auto-increment (meaningless across
machines, **never stored in Tag/Parquet**); UUID is permanent across archives;
`source_id` (`mc3d-XXX/pbesol-v2`, **with the protocol suffix** for disambiguation) is
the cross-dataset external ID. MC3D does not attach source_id natively; a
`mc3d-pbesol-v2-metadata.json` builds a `uuid → source_id` reverse lookup (33,142
entries, ~50ms, no bottleneck) and can be backfilled onto StructureData extras during
archive import.

**External promises**: from v0.1.0, adding fields is non-breaking, deleting/changing
goes through a minor bump; partitioned by `structure_id` so `pl.scan_parquet` works
directly; every row has `workchain_uuid` + `calculation_uuid` to trace back to the
archive; `schema.json` ships with the package; the feature/label/derived_label/metadata
roles are stable across minors.

---

## 7. Tags (minimal scheme)

**Principle: no redundancy; everything else is derived at export from
`node.inputs.pw.parameters` + `node.outputs.*` (single source of truth, zero drift).**
At Phase A scale (~2500-node ballpark) walking inputs/outputs takes seconds — no need
to redundantly store 30+ decision fields in extras.

- **WorkChainNode extras hold only 2 keys**: `source_db_id`
  (`'mc3d-12345/pbesol-v2'`) + `sweep_kind` (`'sweep_cutoff'` / `'sweep_degauss'` /
  `'sweep_kindex'`). Stage WCs and the inner SCF carry them. Cross-layer queries use
  `process_label`: `ConvergencePipelineWorkChain` (orchestrator) /
  `Cutoff|Degauss|Kpoints ConvergenceWorkChain` (stage outer) / `PwBaseWorkChain` (inner).
- **StructureData extras are the single source of provenance**: the importer writes
  them once (`source_db`, `source_id`, `mc3d_*` audit fields); WorkChains read back via
  `get_source()`, never copy.
- **Execution state uses AiiDA-native `process_state`**, no homegrown lifecycle group.
- **"Already exported" is deduplicated** by the Parquet row's `workchain_uuid` primary
  key, no flag.
- **HPC cleanup is one step** via `stash` + `clean_workdir=True` (§13.2), no extras flag.

**Groups serve only as lifecycle containers** (no business fields):
`mc3d-pbesol-v2-structures` (dataset membership), `pilot/v1/mc3d-100` (pilot batch),
the aiida-pseudo family groups (don't touch). Business filtering goes through extras +
inputs walk, then pandas filter on the Parquet. Groups are a view, not truth.

---

## 8. Package layout

`src/goldilocks_data/` — ~13 flat `.py` files, no subpackages (fits one IDE screen,
target < 200 lines each):

| File | Responsibility | When written |
|---|---|---|
| `__init__.py` | `__version__` | Step 0 |
| `cli.py` | typer entry: `smoke / submit / export` | Step 1 |
| `config.py` | pydantic `AppConfig`: paths, `family_label`, threshold constants | Step 0 |
| `tags.py` | `BuilderTags` pydantic — single source of truth | Step 1 |
| `schema.py` | `Record` pydantic — Parquet row contract | Step 1 |
| `aiida_ops.py` | runtime AiiDA ops: `tag_workchain()` / `get_source()` / `query_calcs()` | Step 1 |
| `utils.py` | display / formatting helpers (`format_state()` emoji process state) | Step 1 |
| `mc3d.py` | MC3D archive import + audit extras | Step 1 |
| `classifiers.py` | metallicity ML wrapper + AFM double-threshold heuristic | Step 1 |
| `builder.py` | physics decisions (§4) + `build_pwbase_at_cutoff/kmesh()` | Step 1 |
| `workflows.py` | `ConvergencePipelineWorkChain` + `Cutoff/Degauss/Kpoints ConvergenceWorkChain` + `BaseConvergenceWorkChain` (§5.4) | Phase A start |
| `submit.py` | trivial fan-out | Phase A start |
| `labels.py` | window convergence criterion (§5.5) + enrich Parquet rows | Phase A start |
| `export.py` | finished outer WC → Parquet (partition by `structure_id`) | Phase A round end |
| `resources.py` | sacct + aiida.out parsing + `plan_resources()` | Phase A start |

**Dropped**: `kmesh.py` (all via core), `parse.py` (merged into export),
`families/*` (1 family needs no registry), `protocols/*.yaml`, `_core_stub.py`,
`monitor.py` (the adaptive sweep is self-managed by the outer WC + daemon, no resident
monitor).

Design principles: flat over nested; one concern per file; no core stub (hard
dependency); WorkChain orchestration (daemon provides checkpoint/recovery); `tags.py`
is data, `aiida_ops.py` is actions; adding schema fields is non-breaking (minor
versioning).

---

## 9. Roadmap

| Phase | Content | Scale | Gate to next |
|---|---|---|---|
| **Step 0** | conda env, AiiDA profile, SCARF computer + code, pseudo family, `config/tags/schema` skeleton | — | `verdi status` all green + `verdi computer test scarf` passes |
| **Step 1** | Si bulk × 1 family smoke SCF; notebook dumps Node/extras/outputs → `Record` | ~1 SCF | `Finished[0]` + one fully-filled Parquet row |
| **Step 2** | 1 MC3D structure SCF + a full round loop | ~5 SCF | `convergence_label_*` emitted, full schema path validated |
| **Phase A** | 33k × 1 family three-stage convergence (cutoff/degauss/kpoints) | ~400k–600k SCF | `kpoints` task trained, kindex MAE < 1.5 |
| **Phase B** | 33k × multi-family (no SOC) | ~500k–700k SCF | `pseudo` + `resources` tasks trained |
| **Phase C** | heavy subset × FR family, transfer-learning warm start | ~30k SCF | SOC kpoints model live |

**Phase 1 total ≈ 0.65–0.95M SCF; optimistic 18 months, pessimistic 30+ months.**
Don't skip Step 0/1/2 straight to Phase A; don't advance past a gate that hasn't
passed; Phase A runs no multi-family/SOC/stringent/PAW (leave to B/C); Phase A is
strictly round-by-round, not the full k-mesh Cartesian product concurrently.

---

## 10. Pseudopotential strategy

### 10.1 Current conclusions

- **Phase A locked to** `PseudoDojo/0.4/PBEsol/SR/standard/upf` (PD-A).
- **Element coverage**: PD-A = 72, MC3D PBEsol v2 = 70 (`MC3D ⊂ PD-A`), SSSP = 103.
- ✅ **MC3D's 33,142 structures affected by PD-A element gaps: 0 (0.0%)** — no SSSP
  fallback needed.
- Trivia: `PD-A − MC3D = {La, Lu}` — MC3D PBEsol v2 has zero lanthanides/actinides
  across the whole library (Materials Cloud pre-filtered by PBEsol pseudo availability).
- **Cross-dataset (MP / JARVIS) element gaps** go through the §10.4 convention (not
  active in the MC3D phase).
- **The SOC path (Phase C)** requires a PseudoDojo FR family; SSSP has no FR variant.

### 10.2 PD-A vs SSSP

```
PD-A (PBEsol/SR/standard)  :  72 elements
SSSP (1.3/PBEsol/precision): 103 elements   (strict superset of PD-A)
SSSP - PD-A                :  31 elements
```

The 31 missing elements: mid lanthanides Ce–Yb (13) + all actinides (15) + fringe
radioactives At/Fr/Ra (3). **PD-A includes La/Lu but not the middle 13**: La (4f⁰) and
Lu (4f¹⁴, full and deeply bound) are stable with an ordinary SR pseudo; Ce–Yb (4f¹–4f¹³,
partially filled) are hard to converge with SR and need SR3plus to freeze 4f⁺³ into the
core.

### 10.3 SR3plus vs the single-methodology constraint

```
SR3plus (14): Ce..Yb + Lu      PD-A union SR3plus = 85 elements
overlap with PD-A: {Lu}
```

**Key constraint**: SR3plus exists **only for PBE, not PBEsol** (PseudoDojo never
released PBEsol/SR3plus). Falling back to SR3plus while Phase A uses PBEsol = mixed
functional, violating the §3.1 single-methodology baseline. → So lanthanide structures
fall back to **SSSP** (pure PBEsol), not SR3plus (mixed PBE).

### 10.4 Pseudo selection convention (cross-dataset)

For later expansion to MP / JARVIS (which contain lanthanides/actinides), the builder
routing (`recommend_pseudo_family`) is pre-defined:

```python
def recommend_pseudo_family(elements: set[str], soc_required: bool) -> tuple[str, str]:
    """Returns (family_label, selection_reason)."""
    if soc_required:
        # SSSP ships no FR variant -> can never use SSSP for SOC.
        if not (elements <= PD_FR_ELEMENTS):
            return ('', 'soc_skip_no_fr_pseudo')
        return ('PseudoDojo/0.4/PBEsol/FR/standard/upf', 'pd_fr_soc')
    if elements <= PD_A_ELEMENTS:
        return ('PseudoDojo/0.4/PBEsol/SR/standard/upf', 'pd_a_default')
    return ('SSSP/1.3/PBEsol/precision', 'sssp_fallback_element_gap')
```

- **SOC hard constraints**: the FR family has only 71 elements; SSSP has no FR; an SR
  pseudo standing in for SOC is physically wrong. When a SOC structure contains an
  element the FR family misses, the only Phase 1 option is skip (mark
  `phase_c_skip='no_fr_pseudo'`).
- MC3D always takes `pd_a_default`; expanding to MP/JARVIS auto-activates the SSSP
  fallback with **zero builder change**.
- The new schema field `pseudo_selection_reason` lets the model learn "what kind of
  structure gets fallen back to SSSP".

---

## 11. Convergence-parameter overview

### 11.1 Phase 1 current coverage

| Parameter | Status | Note |
|---|---|---|
| `ecutwfc` | ✅ Stage 1 sweep (cutoff) | anchor low−10..high+15 (§5.2) |
| `ecutrho` | ✅ coupled | NC `4×ecutwfc`; PAW 8–12× |
| `degauss` | ✅ Stage 2 sweep, **metals only** | insulators lock 0.01 (cold); gated by classification (§5.3) |
| k-mesh / kindex | ✅ Stage 3 sweep | `goldilocks_core.build_kmesh_entries`, densified per round |
| `kpoints_distance` | ✅ Stage 3 variable; locked 0.30 in cutoff/degauss stages | provided per round by `build_kmesh_entries` |
| `smearing` | ✅ globally `cold` | degauss see above (swept for metals, locked 0.01 for insulators) |
| `conv_thr` | ✅ globally locked 2e-10 Ry/atom | aligned with MC3D |
| `mixing_beta` / `electron_maxstep` | ✅ locked 0.4 / 200 | |
| `occupations` | ✅ globally `smearing` | single branch for metal/insulator |
| `nbnd` | ✅ ≥ n_occ + max(4, ⌈0.5·n_occ⌉) | HOMO/LUMO computable |
| `nspin` / `starting_magnetization` | ✅ §4 decision | decided, not swept |
| `pseudo_family` | ✅ Phase A locked to PD-A | multi-family only from Phase B |
| `tprnfor` / `tstress` | ✅ globally True | forces enter the criterion (§5.5), stress audit only |

### 11.2 Phase 1.5 / 2 / future dimensions

> (degauss/smearing convergence has moved into the Phase A main line, §5.2/§5.3, not here.)

- **smearing_type sweep** (Phase 1.5, metals only): Phase A fixes `cold`; later compare
  cold / mp1 / gauss for metals (degauss itself is already swept in Phase A).
- **force / stress thresholds** (Phase 2 vc-relax): `forc_conv_thr` / `press_conv_thr`,
  orthogonal to cutoff/kmesh.
- **vdW** (Phase 1.5): `vdw_corr ∈ {grimme-d3/d4, ts, rVV10}`, big effect on
  layered/molecular crystals; MC3D is mostly bulk so low priority.
- **SOC** (Phase C): `noncolin/lspinorb/nspin=4` + FR family (see §3.3 / §10.4).
- Others (off the MC3D main path): supercell (defects), vacuum/slab thickness
  (2D/surface), dipole correction, q-mesh/phonon supercell (Phase 3), DFT+U, hybrid
  functional (100× cost, out of scope).

**Non-convergence but result-affecting, recorded in schema as features**: pseudo
functional (PBEsol) / method (NC) / accuracy tier (standard) / `tot_charge=0` /
`vdw_used=False` / `assume_isolated=None`.

**Core model-side sweep labels** (all produced in Phase A): `ecutwfc` (cutoff
regression), k-mesh (kpoints regression), `degauss` (metal smearing regression); (B)
`pseudo_family` (pseudo classification). These are the core y-label outputs the model
side consumes; all schema design ultimately serves them.

---

## 12. Install & configuration (macOS + SCARF + QE)

> ✅ This is the **verified, currently working** install (brew RabbitMQ/PostgreSQL +
> `presto` on PostgreSQL + `core.ssh_async`), matching this machine: AiiDA 2.7.3,
> profile `presto`, RabbitMQ 4.3, computer `scarf`, code `qe-7.2-pw@scarf`, pseudo
> `PseudoDojo/0.4/PBEsol/SR/standard/upf`. Adjust the local paths
> (`/Users/.../Desktop/*.yaml`) to your machine.

### 12.1 AiiDA + services

```bash
# 1) AiiDA
pip install aiida-core
verdi --version

# 2) RabbitMQ
brew install rabbitmq
brew services start rabbitmq

# 3) RabbitMQ consumer_timeout — long workflows can hit the broker's default
#    consumer_timeout; raise it so the broker does not kill / re-submit jobs.
#    Edit /opt/homebrew/etc/rabbitmq/rabbitmq.conf, add:
#       consumer_timeout = 3600000000   # 1000 hours, in milliseconds
brew services restart rabbitmq

# 4) PostgreSQL
brew install postgresql
brew services start postgresql
psql postgres -c '\q'     # sanity check: opens then exits

# 5) AiiDA profile (PostgreSQL-backed presto)
verdi presto --use-postgres
verdi profile list
verdi profile set-default presto

# 6) silence RabbitMQ version warning, then start daemon
verdi config set warnings.rabbitmq_version false
verdi daemon start
verdi status              # expect all green: config / profile / storage / broker / daemon
```

### 12.2 SCARF computer

First confirm passwordless `ssh scarf` works locally. `scarf.yaml`:

```yaml
label: scarf
description: https://www.scarf.rl.ac.uk/index.html
hostname: scarf
transport: core.ssh_async
scheduler: core.slurm
shebang: '#!/bin/bash'
work_dir: /work4/scd/scarf1418/aiida
mpirun_command: srun -u -n {tot_num_mpiprocs}
mpiprocs_per_machine: 32
use_double_quotes: false
prepend_text: ''
append_text: ''
```

```bash
verdi -p presto computer setup -n --config /path/to/scarf.yaml
verdi -p presto computer configure core.ssh_async scarf
# at the prompt: backend = openssh, "use login shell" = n, others default
verdi -p presto computer test scarf       # expect Opening connection / scheduler / etc. all [OK]
```

> `core.ssh_async` (asyncssh-based) is AiiDA's recommended transport, significantly
> faster than the deprecated `core.ssh` and without a `safe_interval` serial gate —
> required for Phase A's 33k × multi-round flood of SSH transports (`core.ssh`'s serial
> 30s interval becomes a production blocker). The asyncssh schema is lean; most SSH
> options (key file / proxy / agent) are read from `~/.ssh/config`, not the YAML.

### 12.3 Quantum ESPRESSO code

SCARF builds QE centrally with EasyBuild (maintainer user `scarf562`).
`qe-7.2-pw@scarf.yaml`:

```yaml
label: qe-7.2-pw
description: Quantum ESPRESSO pw.x
default_calc_job_plugin: quantumespresso.pw
computer: scarf
filepath_executable: /work4/scd/scarf562/eb-amd/software/QuantumESPRESSO/7.2-foss-2023a/bin/pw.x
use_double_quotes: true
prepend_text: |+
  module load amd-modules
  module load QuantumESPRESSO/7.2-foss-2023a

append_text: ' '
```

```bash
verdi -p presto code create core.code.installed -n --config /path/to/qe-7.2-pw@scarf.yaml
verdi -p presto code list                  # qe-7.2-pw@scarf
verdi -p presto code show qe-7.2-pw@scarf
```

> Notes: `module load amd-modules` first (the AMD-partition toolchain bundle, which
> resets the toolchain so `module purge` is unnecessary), then the QE module. Don't
> hard-code `OMP_NUM_THREADS` — the builder injects `--cpus-per-task` + `OMP_NUM_THREADS`
> dynamically in §13.

### 12.4 PseudoDojo pseudopotentials

```bash
pip install aiida-pseudo
# Phase A family (the only one MC3D needs):
aiida-pseudo install pseudo-dojo -v 0.4 -x PBEsol -f upf -s high
verdi -p presto group list -a
```

Install the other families when Phase B/C needs them (NC v0.4 PBE/PBEsol/LDA ×
std/stringent, PAW JTH v1.0 × std/stringent, FR variants). Installation is idempotent;
already-installed families are skipped. **Don't bother with physically impossible
combinations** (server 404s): LDA×FR, LDA/PBEsol × SR3plus, PBEsol×PAW, PAW×FR,
PAW×SR3plus.

### 12.5 Note: don't install aiida-workgraph in this env

`aiida-workgraph 0.8.1` downgrades `aiida-core` to 2.7.x, while
`aiida-quantumespresso 5.0.0` needs `aiida-core~=2.8` → dependency conflict. If you need
workgraph, make a separate env (`conda create -n aiida-workgraph python=3.12`). Recover
after an accidental install:

```bash
pip uninstall -y aiida-workgraph aiida-pythonjob aiida-shell node-graph node-graph-widget
pip install -U "aiida-core[atomic-tools]~=2.8" aiida-quantumespresso
verdi -p presto daemon restart && verdi -p presto status
```

### 12.6 Starting services after a Mac reboot

brew services usually auto-start RabbitMQ/PostgreSQL; the daemon is manual:

```bash
brew services start rabbitmq postgresql   # if not already running
verdi daemon start
verdi status                              # verify all green
```

### 12.7 Troubleshooting quick reference

| Symptom | Cause / fix |
|---|---|
| `ImportError: cannot import name 'Sentinel' from typing_extensions` | conda partial-fail left two dist-info dirs. `ls site-packages \| grep typing_ext`, delete the old `*.dist-info`, `conda install --force-reinstall typing_extensions` (`pydantic_core ≥ 2.27` needs `typing_extensions ≥ 4.13`) |
| `bad CPU type in executable: verdi` | Apple Silicon running x86 miniconda needs Rosetta: `softwareupdate --install-rosetta --agree-to-license` (no perf cost locally — no numerics run here, QE runs over SSH on SCARF) |
| `new collation ... incompatible with template database (C)` | create the DB with `TEMPLATE template0` (the bare template allows any locale); also pin a UTF-8 locale in `~/.zshrc` |
| psql `syntax error at or near "CREATE"`, prompt becomes `postgres-#` | missing semicolon between statements; `postgres-#` (hyphen) = continuation, every SQL statement needs a trailing `;` |
| `connection to server on socket ... failed: No such file` | wrong unix-socket path; fall back to `psql -h localhost ...`; verdi/aiida use TCP and are unaffected |
| stale `postmaster.pid` | **don't just `rm` it** — on Apple Silicon + conda PG, deleting it triggers a still-running PG to graceful-shutdown. First `ps aux \| grep postgres` to confirm the process is really gone, then delete and restart |
| terminal prints checkpoint LOG every ~5min | pure noise: `ALTER SYSTEM SET log_checkpoints = off; SELECT pg_reload_conf();` |
| `checkpoints are occurring too frequently ... increase max_wal_size` | **tune before Phase A**: `ALTER SYSTEM SET max_wal_size='4GB'; ALTER SYSTEM SET checkpoint_timeout='15min'; SELECT pg_reload_conf();` (100+ concurrent SCF submits trigger WAL thrashing) |
| `DetachedInstanceError` in jupyter | `verdi daemon restart` / PG restart swapped the session. No kernel restart needed — just re-`load_group/load_code/load_node` |

---

## 13. Resource collection + HPC file retention

### 13.1 Resource collection (`resources.py`)

Three mutually-checking data sources: **SLURM `sacct`**
(`MaxRSS`/`AveRSS`/`Elapsed`/`State`/`ExitCode`, run over SSH after finish),
**QE `aiida.out`** (estimated RAM, PWSCF wall time, regex-parsed), and **AiiDA
`node.attributes`** (`job_id`, `scheduler_state`, read directly).

Declare memory at submit so sacct `ReqMem` is meaningful:

```python
options = {
    'resources': {'num_machines': n, 'num_mpiprocs_per_machine': n_mpi},
    'max_wallclock_seconds': walltime_s,
    'custom_scheduler_commands': '\n'.join([
        f'#SBATCH --mem={mem_per_node_mb}M',
        f'#SBATCH --comment=goldilocks/{sweep_id}',
    ]),
}
```

`mem_per_node_mb` is heuristically estimated by `plan_resources()` (v0, required for
Phase A; v1 replaced by ML in Phase B+). SCARF sacct retention is ≥ 12 months; the
collection interval keeps a 4× margin; nodes past the window are marked
`actual_resources_source='qe_only'`.

> SCARF cluster specs to be measured with `sinfo` / `scontrol show node` and filled into
> `configs/clusters/scarf.yaml`: `default_partition`, `max_walltime_s`,
> `mem_per_node_mb`, `cores_per_node`, whether QE is OMP-built.

### 13.2 HPC file retention — `stash` + `clean_workdir=True`

One atomic step on finish (retrieve needed files to the local archive + stash selected
files to an HPC persistent area + wipe the original workdir), without manual `rm -rf` or
deleting the whole remote folder:

```python
from aiida.common.datastructures import StashMode

builder.pw.metadata.options.stash = {
    'source_list': [
        'aiida.in', 'aiida.out', '_aiidasubmit.sh',
        '_scheduler-stdout.txt', '_scheduler-stderr.txt',
        'out/aiida.xml', 'out/aiida.save/data-file-schema.xml',
    ],
    'target_base': '/work4/scd/scarf1418/aiida-stash',   # persistent (not scratch); mkdir -p first
    'stash_mode': StashMode.COPY.value,
}
builder.clean_workdir = orm.Bool(True)   # clean only after stash
```

Exclude the disk hogs (`wfc*.hdf5` / `charge-density.hdf5` / `*.upf` / `pseudo/` etc.).
The charge density is **only reused transiently between consecutive rounds** (§5.4,
startingpot='file') and wiped with the workdir once the next round consumes it —
**never stashed / kept long-term**, so it does not consume long-term storage.
On finish AiiDA creates a `RemoteStashFolderData` on the CalcJob, output link
`remote_stash` (`node.outputs.remote_stash.target_basepath` gives the persistent path).
Estimate ~50 KB per calc × 33k × multi-round ≈ a few GB.

---

## 14. Open questions + references

| # | Topic | Current default | Impact |
|---|---|---|---|
| 1 | `gamma_pathological` threshold | 100 meV/atom placeholder | §5.6; calibrate on historical metal data before P2 |
| 2 | SCARF cluster specs | pending `sinfo` / `module avail` | §13.1 |
| 3 | model-side element-disjoint split, N per element | not asked | §3.1; decides whether 33k or 15k is enough |
| 4 | how to mark SOC scope | `is_soc` field vs `calc_type='scf_soc'` | §6; affects the model `supported_scope` |
| 5 | PSDI upload channel | pending | publish at end of Phase 1 |
| 6 | `goldilocks-core` repo fetch status | unconfirmed | Step 0 prerequisite |

**References**:
- `3-goldilocks-models/docs/PLAN.md` — sibling model contract
- `4-goldilocks-core/src/goldilocks_core/kmesh.py` — kindex schedule generation
- UKRI grant EP/Z530657/1
- PseudoDojo <http://www.pseudo-dojo.org/>
- Materials Cloud MC3D <https://www.materialscloud.org/discover/mc3d>
- aiida-quantumespresso <https://aiida-quantumespresso.readthedocs.io/>
- AiiDA RabbitMQ compatibility <https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/troubleshooting.html#rabbitmq-incompatibility>
