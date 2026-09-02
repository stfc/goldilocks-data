# goldilocks-data

> 本仓库的唯一文档（source of truth）。覆盖：生态定位、Phase A/B/C 策略、物理决策、
> 自适应 sweep、Parquet schema、包结构、赝势策略、收敛参数、本地+SCARF 安装配置。
> 双语：本文中文（主），[PLAN.en.md](PLAN.en.md) 英文 mirror，两边同步。
>
> 模块级实现细节在各 `__init__.py` / docstring；本文只管跨模块设计与运维。

---

## 1. 背景 — UKRI Goldilocks 生态

UKRI Goldilocks（EP/Z530657/1）给用户产出"恰到好处"的 DFT 输入
（ecutwfc / k-grid / smearing / pseudo / SLURM 脚本）。四个兄弟仓库按数据流：

| Repo | 角色 | 与本仓关系 |
|---|---|---|
| **goldilocks-data**（本仓） | DFT 数据生成；AiiDA + QE on SCARF；产出 Parquet | — |
| `goldilocks-models` | 用我们的 Parquet 训 ML 模型，导出版本化 artefact | 下游 |
| `goldilocks-core` | 推荐 + 解析；提供 `infer_features`、k-mesh schedule、分类器 | 上游（我们调用） |
| `goldilocks-webapp` | 前端 | 间接 |

**两个契约**：

- → `goldilocks-models`：Parquet 行。每行 = 一次 SCF，按 `(structure, family)` 标
  `under` / `just_right` / `over`。Schema 见 §6。
- ← `goldilocks-core`：硬依赖（无 stub）。`kmesh.build_kmesh_entries`、`infer_features`、
  `derive_starting_magnetization`、分类器包装。core 缺失则数据不可用 —— 设计如此。
  conda env 内用 `pip install -e ../1-goldilocks-core` 引 sibling path。

**双轨架构**：离线轨（`goldilocks-data` → `goldilocks-models`）产出版本化模型 artefact +
manifest 落共享存储；在线轨（`goldilocks-webapp` → `goldilocks-core`）启动时从共享存储
拉 manifest 加载模型。两轨通过 artefact 存储解耦 —— 在线推荐时 data / models 无需在线。

---

## 2. Phase 1 范围

| 维度 | Phase 1 |
|---|---|
| DFT code | Quantum ESPRESSO 7.2（`pw.x`，SCARF EasyBuild 共享安装 `QuantumESPRESSO/7.2-foss-2023a`） |
| Calc type | 仅 SCF（不做 relax / bands / DOS / phonon / MD） |
| Structures | Materials Cloud MC3D PBEsol v2 —— 33,142 全量 |
| Sweep 轴 | 三段自适应收敛：**cutoff → degauss(仅金属) → kpoints**，每轮一个 index（见 §5） |
| XC | PBEsol（由 pseudo family 锁定） |
| HPC | SCARF (STFC) |

不在 Phase 1：VASP / CP2K / ABINIT，relax / bands / DOS / phonon / MD，
USPP / GBRV pseudo，多用户 PostgreSQL，AFM 枚举，DFT+U。

---

## 3. Phase A → B → C 策略

### 3.1 Phase A — 单 family，单方法学 baseline

| 项 | 值 |
|---|---|
| Family（Phase A 使用） | `PseudoDojo/0.4/PBEsol/SR/standard/upf`（1 family，简称 PD-A） |
| Family（env 预装） | 见 §12 安装；Phase B/C 复用 |
| Structures | MC3D 33,142 全量 |
| nspin | MC3D `total/abs_mag` 双阈值（零成本，见 §4） |
| SOC | off |
| 收敛 sweep | 三段：**cutoff（扫 ecutwfc）→ degauss（仅金属）→ kpoints（扫 kindex）**，每轮一个 index（§5） |
| ecutwfc / degauss | 都扫（Stage 1 / Stage 2）；绝缘体 degauss 锁 0.01，不扫 |
| 目标 SCF 量 | ~400k–600k（每结构 cutoff ~11 + degauss ~5 仅金属 + kpoints ~5–7） |
| 驱动任务 | 喂 `goldilocks-models` 的 `kpoints` task |
| 进 B 的 gate | `kpoints` model 训完，kindex MAE < 1.5；Parquet snapshot v0.1 发布 |

**为什么 1 family + 33k 全量（而非 5k 抽样 × 5 family）**：计算成本相当
（~165k vs 125k SCF），但元素覆盖更好（33k 含 70+ 元素全覆盖），给 model 端的
element-disjoint split 更充分。方法学对比（NC vs PAW、std vs stringent、
PBE vs PBEsol vs LDA）推到 Phase B。

### 3.2 Phase B — 多 family，no SOC

启动条件：Phase A `kpoints` model 训完上线。加 6–10 个 family（NC v0.4 的
PBE/PBEsol/LDA × std+stringent，PAW JTH v1.0 × std+stringent），同 33k 结构、
同 nspin 决策。驱动 `goldilocks-models` 的 `pseudo` + `resources` task。

### 3.3 Phase C — SOC，迁移学习

启动条件：Phase B 完成。只跑含重元素（`contains_heavy=True`）子集 ≈ 1.5k 结构，
FR family（`PseudoDojo/0.4/PBEsol/FR/standard/upf`）：

```python
spin_type = SpinType.SPIN_ORBIT   # -> noncolin=True, lspinorb=True, nspin=4
```

aiida-qe 自动 expose `angle1` / `angle2`（初始磁矩 3D 方向，默认沿 z），Phase C
baseline 不动；真非共线磁性（spiral / canted）留 Phase 1.5/2。ML 路径：用 Phase A/B
的 SR 数据训出的 `kpoints` model 作 warm start，减少 SOC 子集所需样本量。

### 3.4 SpinType 全景（为何只用 3 种）

| SpinType | nspin | noncolin | lspinorb | 物理 | 何时用 |
|---|---|---|---|---|---|
| `NONE` | 1 | F | F | 闭壳层无磁性 | Phase A/B 偶电子无磁性 |
| `COLLINEAR` | 2 | F | F | 自旋单轴 ↑↓，FM/AFM/FiM | Phase A/B 奇电子或磁性 |
| `NON_COLLINEAR` | 4 | T | F | 自旋 3D 任意方向，无相对论 | **跳过** |
| `SPIN_ORBIT` | 4 | T | T | 非共线 + SOC，完整相对论 | Phase C `contains_heavy` |

**跳过纯 `NON_COLLINEAR`**：MC3D 主体是常规晶体，非共线磁结构是少数派；真要研究
通常含重元素 → SOC 不可忽略 → 直接走 SPIN_ORBIT 更对。Phase C 一步到位。

---

## 4. 每结构物理决策

builder 阶段每结构做 2 个决策（degauss / starting_magnetization 已外包给 aiida-qe）：

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

`magnetism_prior(structure)` 决策树（multi-source fallback）：

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

**关键约束**：

- **奇电子是硬约束**：闭壳层容不下奇数电子 → 必须 nspin=2，无 false positive。
- **MC3D v2 `total_magnetization` 不可单独信赖**：481 个 v1-magnetic / v2-NM 体系里 94%
  含 Fe/Mn/Co/Ni/Cr；v2 false negative 在 7–10% 量级。决策必须叠 v1 + chemistry rule。
- **chemistry rule 是 broad inclusion**：含磁性元素即便 v1/v2 都说 NM 也开 nspin=2；
  代价是少数体系收敛到 0（浪费 ~5–10% walltime），收益是不漏磁性 ground state。
- **只能播 FM/FiM**：aiida-qe stock COLLINEAR 协议给同 kind 原子相同正值 sm，初始 ↑↑↑↑ →
  收敛到 FM 或 NM，**不可能自发收敛 AFM**。要 AFM 必须 kind-split + 反号 sm（Phase 1.5）。

### 4.1 全局固定参数（Phase 1 全部结构，含绝缘体）

统一 `occupations='smearing'`、`smearing='cold'`、`degauss=0.01 Ry`，对绝缘体同样适用：

- **smearing ≠ 当成金属**：smearing 只影响 BZ 积分的占据数 / 总能 / 自洽，**不改 H 的本征值**。
  `output_band` 里 `bands[k,n]` 永远是对角化结果，HOMO/LUMO/gap 永远能算
  （`gap = bands[:,n_occ].min() − bands[:,n_occ-1].max()`）。
- **绝缘体污染可忽略**：实测 Si（8e/cell）熵修正 ≈ 0.013 meV/atom（≪ 1 meV/atom 阈）。
- **cold smearing 的 σ⁴ 残差**：E(σ)−E(0) 主导项是 O(σ⁴)（Fermi-Dirac/Gauss 是 σ²，
  MP-N 是 σ^(2N+2)）。σ=0.01 Ry 下，一般金属 0.1–0.5 meV/atom，陡 DOS 金属 1–2 meV/atom。
- **收敛判定不受 smearing 影响**：sweep 内 σ 不变 → smearing 误差是常数偏移，
  在 §5.5 的 max-min window 极差里完全相消。这正是判据用 sweep window 极差而非绝对能量的原因。
- **Bonus**：免费的 metallicity y-label —— `gap > 0.05` insulator / `gap < −0.01` metal
  （带交叠）/ 否则 borderline。builder 的 `metallicity_guess` vs 实测 gap 成 (X,y) 对喂
  Phase 1.5 `metallicity` task。

其余固定参数：`tprnfor=true`、`tstress=true`；`nbnd ≥ n_occ + max(4, ⌈0.5·n_occ⌉)`
（保证能从 `output_band` 算 HOMO/LUMO）；`conv_thr=2e-10 Ry/atom`（与 MC3D 对齐）；
`mixing_beta=0.4`、`mixing_mode=plain`、`diagonalization=david`、`electron_maxstep=200`；
`tot_charge=0`；vdW / Hubbard U: off；`max_iterations=1`（PwBaseWorkChain 不 retry，
失败立即标 `scf_failed=True`，sweep window 本身吸收偶发噪声）。

---

## 5. 自适应收敛 sweep（cutoff → degauss → kpoints，均在 Phase A）

> **决策（2026-06-16）：三段收敛都在 Phase A 第一阶段做** —— cutoff、degauss（仅金属）、
> kpoints。先锁前者再扫后者（各轴正交），由一个 per-structure pipeline WorkChain 串起来。

### 5.1 总览

每个 (structure, family) 顺序跑三段,由一个 `ConvergencePipelineWorkChain` 编排:

```
Stage 1  cutoff   sweep ecutwfc  @ coarse fixed k=0.30, degauss=0.01
                  -> converged_ecutwfc  + 顺带分类 metal/insulator (gap, §5.3)
Stage 2  degauss  sweep degauss  @ converged ecutwfc, coarse k=0.30   (METALS ONLY)
                  -> converged_degauss  (insulator: skip, degauss=0.01)
Stage 3  kpoints  sweep kindex   @ converged ecutwfc + degauss
                  -> converged_kindex
```

正交性:cutoff 是 pseudo/元素性质;degauss 只对金属(绝缘体 gap 使占据数对 smearing 不
敏感);kpoints 是 BZ 采样。先锁前者再扫后者,避免多维网格爆炸。`round_number` 全局递增、
跨 stage;`sweep_axis ∈ {cutoff, degauss, kmesh}` + `sweep_index` 决定每轮跑什么。

### 5.2 三段的 schedule

**Stage 1 — cutoff（sweep ecutwfc）**:起点 anchor 在 PseudoDojo `low` tier 之下 10 Ry,
5 Ry 步进到 `high`+15;此阶段用粗固定 k=0.30、degauss=0.01。

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

anchor 在 `low−10` 保证起点深度 under-converged、曲线有梯度;到 normal(1 meV/atom 阈)
just_right;到 high+15 给 over。cutoff 阶段只借 aiida-qe `fast` 协议的 λ(k=0.30),base 仍
`protocol='moderate'`(保严谨 conv_thr/mixing),不借它放宽的 degauss/conv_thr。

**Stage 2 — degauss（sweep degauss，仅金属）**:在 Stage 1 收敛的 ecutwfc、同一套 coarse
k=0.30 上,degauss 从宽到窄扫,cold smearing:

```python
DEGAUSS_SCHEDULE_RY = [0.03, 0.02, 0.015, 0.01, 0.005]   # metals only; cold smearing
```

绝缘体跳过(degauss 锁 0.01,§5.3 gate)。金属 k 与 degauss 耦合,这里用"coarse k 定 degauss
→ 固定 degauss 扫 k"的顺序近似(够 baseline,真要 k–degauss 二维联扫留更后面)。

**Stage 3 — kpoints（sweep kindex，来自 core）**:

```python
from goldilocks_core.kmesh import build_kmesh_entries
entries = build_kmesh_entries(structure)   # ~30-90 entries per structure
# entries[0].k_index == 1  <=>  Gamma-only (mesh = (1,1,1))
```

- kindex 起算 = 1(Γ-only);跨结构不可比,`k_pra`(k-points per reciprocal Å)才可比。
- 缓存:首次算一次写 `StructureData.extras['kmesh_plan']`(含 `core_kmesh_api_version` =
  core git SHA),core 升级 → SHA 变 → 自动重算。
- 每行 Parquet 记 `schedule_generator` / `schedule_generator_version` / `schedule_max_index`。

### 5.3 金属/绝缘体分类（cutoff 阶段顺带，gate degauss）

每个 cutoff SCF 都出 gap,用 §4.1 的 `metallicity_from_gap`(gap>0.05 绝缘体 / <−0.01 金属 /
否则 borderline)分类。cutoff 是最早的 stage,分类结果 **gate Stage 2**:`insulator` → 跳过
degauss(锁 0.01);`metal` / `borderline` → 跑 degauss 收敛。coarse k=0.30 的 gap 只够粗
分类,borderline 兜底,最终可在收敛的 k 上复核。`metallicity_guess`(builder 端 ML 预测)
仍作 feature 记录,与实测 gap 成 (X,y) 对喂 model 的 metallicity task。

### 5.4 Driver — per-structure ConvergencePipelineWorkChain

每个 (structure, family) 由**一个 `ConvergencePipelineWorkChain`** 编排三段,daemon 负责
lifecycle,**不需要独立 monitor 进程**:

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

三个 stage WC 都继承 `BaseConvergenceWorkChain`(共享 setup / should_continue /
_is_converged / finalize),子类只定义"扫哪个轴 + 锁哪些值":

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

每个 stage WC 内部按 sweep_index=0,1,...,N 顺序提交 PwBaseWorkChain 至收敛(§5.5)或
max_rounds;exit codes 401 ERROR_SCF_FAILED / 402 ERROR_MAX_ROUNDS。

**fan-out 极简**:`for struct in pool: submit(ConvergencePipelineWorkChain, structure=struct, ...)`,
然后撒手 daemon 接管所有 33k pipeline WC。daemon 死 / Mac 重启 → restart 后从 pickle 续跑
(WorkChain checkpointing)。**inflight cap 走 daemon 配置**,不用自己写闸门:

```bash
verdi config set daemon.worker_process_slots 200   # 上限 active WC
```

大部分 WC 在 "waiting for inner SCF" 不占 active slot;slot=200 对应稳态 OK。

**round 间复用电荷密度（省机时，不占长期存储）**:电荷密度只依赖实空间网格(ecutrho)、
**与 k 无关**,所以同一 stage 内下一轮 SCF 用上一轮的 charge density 当起点(`startingpot='file'`
+ `parent_folder`)能省一截 SCF 步数(波函数因 k 变了不复用)。**存储不爆**:charge density
只在相邻两轮之间临时存在 SCARF scratch,下一轮读完就连同上一轮 workdir 一起清掉(§13.2 的
stash source_list 本就不含 charge density,永不长期保留)。稳态额外占用 ≈ active sweep
数量级(~200 份临时),不是 33k×N 份。

### 5.5 收敛判据（`labels.py`）

**判据（三段 cutoff/degauss/kpoints 通用）：最近 5 个 sweep 点的窗口，能量和力都要收敛 ——
两者同时满足才停。** 只关注能量和力(应力/gap/磁矩仍每轮记录但不进判据)。窗口用 5 点
（不是 3）抵抗金属/小 gap 体系收敛的非单调震荡,避免在偶然平台上误判收敛。

```python
ENERGY_TOL_EV_PER_ATOM = 1.0e-3   # 1 meV/atom
FORCE_TOL_EV_PER_A     = 5.0e-2   # 0.05 eV/A
N_WINDOW               = 5        # last 5 sweep points (was 3; 5 resists oscillation)
# converged = energy window AND force window both within tol
# earliest verdict at sweep_index >= 4 (need 5 points); judged per sweep_axis
```

派生标签（回填到同 `(struct, family, sweep_axis)` 所有行）：
- `convergence_label_energy` / `convergence_label_forces` ∈ {under, just_right, over, null}
  （各按 sweep_index 相对 converged_at_index）
- `converged_at_index`（能量与力**都**满足的最新 index）、`dE_window_meV_per_atom`、
  `dF_window_eV_per_A`、`converged_at_ecutwfc`、`converged_at_degauss`、`converged_at_kindex`
- 仅记录、不进判据：`stress_max`、`band_gap_estimate`、`total_magnetization`

`just_right` 是 model `cutoff` / `degauss` / `kpoints` task 的 y 标签源（按 sweep_axis 区分）。

### 5.6 四层 safeguards

| 层 | 触发 | 行为 |
|---|---|---|
| 1. SCF 内部 fail | exit_status ≠ 0 | `max_iterations=1` 无 retry，标 `scf_failed=True`，终止该 sweep_axis，数据保留 |
| 2. 单阶段轮上限 | 单 sweep_axis 累计 10 轮仍未收敛 | hard halt，标 `convergence_status='max_rounds_exhausted'` |
| 3. 单结构 wallclock 预算 | 累计 > 24h per (struct, family) | halt，标 `convergence_status='budget_exceeded'` |
| 4. Γ-pathological（仅 kmesh） | round1 vs round2 ΔE/atom > 100 meV | 标 `gamma_pathological=True`；收敛窗口跳过 Γ-only 点 |

**`convergence_status` 取值（区分负样本含义,decision 6）**：`converged` / `scf_failed`
（SCF 挂）/ `schedule_exhausted`（该 stage 的 schedule 跑完仍没满足判据，≠ 轮上限）/
`max_rounds_exhausted`（达 10 轮上限）/ `budget_exceeded`（超 wallclock 预算）。模型把后四种
当不同类型的负样本。

> TODO：`gamma_pathological` 阈值 100 meV 是占位，用 100 个 MC3D 结构样本校准。

---

## 6. Schema — Parquet 行契约

每行 = 一次 PwBaseWorkChain SCF。按 `structure_id` 分区：
`data/processed/v<X.Y.Z>/structure_id=<MC3D-ID>/*.parquet`。完整字段定义在
`src/goldilocks_data/schema.py`（`Record` pydantic）；本节列字段名 + role。

**Provenance（metadata）**：`workchain_uuid`, `calculation_uuid`,
`aiida_archive_version`, `goldilocks_data_version`, `git_sha`, `submitted_at`,
`submitter`, `schedule_generator(_version)`, `schedule_max_index`。

**Input — structure features（feature）**（来自 `goldilocks_core.infer_features`，扁平化）：
`source_db`, `source_id`, `formula`, `spacegroup_number`, `crystal_system`, `n_atoms`,
`cell_volume`, `element_set`, `n_electrons_neutral`, `contains_lanthanide`,
`contains_actinide`, `contains_heavy`, `heavy_elements`, `likely_magnetic`,
`magnetic_elements`, `is_metal_guess`, `dimensionality_larsen`, `anisotropy_ratio`。

**Input — pseudo + numerics（feature）**：`pseudo_family`, `pseudo_selection_reason`,
`pseudo_source`, `pseudo_method`, `pseudo_functional`, `pseudo_accuracy`,
`pseudo_version`, `pseudo_relativistic`, `pseudo_format`, `ecutwfc`, `ecutrho`, `k_mesh`,
`k_offset`, `k_distance`, `k_density_mp`, `k_linedensity_jarvis`, `sweep_axis`, `kindex`,
`k_pra`, `n_reduced_kpoints`, `smearing_type`, `degauss`, `mixing_beta`, `conv_thr`。

**Input — physics decisions（feature）**：`nspin`, `noncolin`, `lspinorb`, `soc_enabled`,
`magnetic_state_decision`, `starting_magnetization_source`, `metallicity_guess`,
`vdw_used`, `cutoff_source`, `occupations`。

**Output — physics（label）**：`total_energy`, `fermi_energy`, `forces_max`, `stress_max`,
`band_gap_estimate`, `total_magnetization`, `n_scf_iterations`, `final_scf_accuracy`,
`exit_status`, `warnings`。

**Output — convergence labels（derived_label，按 sweep_axis 独立判定）**：
`convergence_label_energy`, `convergence_label_forces`, `converged_at_index`,
`converged_at_ecutwfc`, `converged_at_degauss`, `converged_at_kindex`, `convergence_status`,
`metallicity`, `dE_window_meV_per_atom`, `dF_window_eV_per_A`, `round_number`,
`gamma_pathological`, `scf_failed`。（`sweep_axis ∈ {cutoff, degauss, kmesh}`；能量与力都进
收敛判据，§5.5；窗口 5 点。）

**Output — resources（label，`resources.py` 收集）**：请求侧 `n_nodes_requested` /
`n_mpi_per_node_requested` / `n_omp_threads` / `walltime_requested_s` /
`mem_per_node_requested_mb`；实际侧（sacct + aiida.out）`peak/avg_memory_mb_actual` /
`walltime_actual_s` / `slurm_exit_code` / `slurm_state` / `qe_*` / `memory_efficiency` /
`walltime_efficiency`；并行 `npool` / `nbgrp` / `ndiag` / `parallelization_strategy`。

**Lifecycle + audit（metadata）**：`process_state`（AiiDA 原生）, `exit_status`,
`is_smoke_test`, `mc3d_*`（`pseudo_flagged_suboptimal` / `afm_likely` /
`high_pressure` / `theoretical_only` / `total_magnetization` /
`absolute_magnetization` / `band_gap`）。`phase` 在导出时派生，不存 extras。

**PK / UUID / source_id**：PK 是本地 DB 自增（跨机无意义，**Tag/Parquet 不存 PK**）；
UUID 永久跨 archive；`source_id`（`mc3d-XXX/pbesol-v2`，**带 protocol 后缀**消歧）是跨
数据集外部 ID。MC3D 不原生挂 source_id，靠 `mc3d-pbesol-v2-metadata.json` 建
`uuid → source_id` 反向 lookup（33,142 条，~50ms 无瓶颈）；可在 archive 导入时一次性
回填到 StructureData extras。

**对外承诺**：v0.1.0 起加字段不破坏，删/改走 minor；按 `structure_id` 分区可直接
`pl.scan_parquet`；每行有 `workchain_uuid` + `calculation_uuid` 可反查 archive；
`schema.json` 同包发布；feature/label/derived_label/metadata 角色跨 minor 不变。

---

## 7. Tags（极简方案）

**原则：不冗余，其余字段导出时从 `node.inputs.pw.parameters` + `node.outputs.*` 实时
派生（单一真理源，零漂移）。** Phase A 规模（~2500 节点级别）直接 walk inputs/outputs
几十秒搞定，不需要把 30+ 决策字段冗余进 extras。

- **WorkChainNode extras 只 2 个 key**：`source_db_id`（`'mc3d-12345/pbesol-v2'`）+
  `sweep_kind`（`'sweep_cutoff'` / `'sweep_degauss'` / `'sweep_kindex'`）。stage WC 与 inner 都挂。
  跨层用 `process_label` 区分：`ConvergencePipelineWorkChain`（编排器）/ `Cutoff|Degauss|Kpoints
  ConvergenceWorkChain`（stage outer）/ `PwBaseWorkChain`（inner SCF）。
- **StructureData extras 是 provenance 单一来源**：导入器写一次（`source_db`, `source_id`,
  `mc3d_*` audit 字段），WorkChain 通过 `get_source()` 反查，不复制。
- **执行状态用 AiiDA 原生 `process_state`**，不自建 lifecycle 群。
- **"已导出"用 Parquet 行 `workchain_uuid` 主键去重**，不存 flag。
- **HPC 清理由 `stash` + `clean_workdir=True` 一步完成**（§13.2），不需要 extras flag。

**Groups 仅作生命周期容器**（不表达业务字段）：`mc3d-pbesol-v2-structures`（数据集成员）、
`pilot/v1/mc3d-100`（pilot batch）、aiida-pseudo 自带的 family group（别动）。
业务过滤全走 extras + inputs walk，Parquet 出来后 pandas filter。groups 是 view 不是 truth。

---

## 8. 包结构

`src/goldilocks_data/` —— ~13 个 `.py` 平铺，无子包（IDE 单屏看完，每文件目标 < 200 行）：

| 文件 | 职责 | 何时写 |
|---|---|---|
| `__init__.py` | `__version__` | Step 0 |
| `cli.py` | typer 入口：`smoke / submit / export` | Step 1 |
| `config.py` | pydantic `AppConfig`：paths、`family_label`、阈值常量 | Step 0 |
| `tags.py` | `BuilderTags` pydantic —— 单一真理源 | Step 1 |
| `schema.py` | `Record` pydantic —— Parquet 行契约 | Step 1 |
| `aiida_ops.py` | runtime AiiDA 操作：`tag_workchain()` / `get_source()` / `query_calcs()` | Step 1 |
| `utils.py` | 显示 / 格式化辅助（`format_state()` emoji process state） | Step 1 |
| `mc3d.py` | MC3D archive 导入 + audit extras | Step 1 |
| `classifiers.py` | metallicity ML 包装 + AFM 双阈值启发式 | Step 1 |
| `builder.py` | 物理决策（§4）+ `build_pwbase_at_cutoff/kmesh()` | Step 1 |
| `workflows.py` | `ConvergencePipelineWorkChain` + `Cutoff/Degauss/Kpoints ConvergenceWorkChain` + `BaseConvergenceWorkChain`（§5.4） | Phase A start |
| `submit.py` | 极简 fan-out | Phase A start |
| `labels.py` | window 收敛判据（§5.5）+ enrich Parquet 行 | Phase A start |
| `export.py` | finished outer WC → Parquet（按 `structure_id` 分区） | Phase A round 末 |
| `resources.py` | sacct + aiida.out 解析 + `plan_resources()` | Phase A start |

**砍掉的**：`kmesh.py`（全走 core）、`parse.py`（并入 export）、
`families/*`（1 family 不需 registry）、`protocols/*.yaml`、`_core_stub.py`、
`monitor.py`（adaptive sweep 由 outer WC + daemon 自管，不需常驻 monitor）。

设计原则：flat over nested；one concern per file；no core stub（硬依赖）；
WorkChain orchestration（daemon 自带 checkpoint/recovery）；`tags.py` 是数据、
`aiida_ops.py` 是动作；schema 加字段不破坏（minor 版本管理）。

---

## 9. Roadmap

| Phase | 内容 | 量级 | Gate to next |
|---|---|---|---|
| **Step 0** | conda env、AiiDA profile、SCARF computer + code、pseudo family、`config/tags/schema` 骨架 | — | `verdi status` 全绿 + `verdi computer test scarf` 全过 |
| **Step 1** | Si bulk × 1 family 冒烟 SCF；notebook dump Node/extras/outputs → `Record` | ~1 SCF | `Finished[0]` + 1 行 Parquet 字段全填 |
| **Step 2** | 1 个 MC3D 结构 SCF + 完整 round 循环 | ~5 SCF | 出 `convergence_label_*`，schema 全路径验证 |
| **Phase A** | 33k × 1 family 三段收敛（cutoff/degauss/kpoints） | ~400k–600k SCF | `kpoints` task 训完，kindex MAE < 1.5 |
| **Phase B** | 33k × multi-family（no SOC） | ~500k–700k SCF | `pseudo` + `resources` task 训完 |
| **Phase C** | heavy 子集 × FR family，transfer-learning warm start | ~30k SCF | SOC kpoints model 上线 |

**Phase 1 总 ≈ 65–95 万 SCF；乐观 18 个月，悲观 30+ 个月。** 不跳 Step 0/1/2 直冲
Phase A；gate 没过不进下一阶段；Phase A 不跑多 family/SOC/stringent/PAW（留 B/C）；
Phase A 严格 round-by-round，不跑 K-mesh 笛卡儿积全并发。

---

## 10. 赝势策略

### 10.1 当前结论

- **Phase A 锁定**：`PseudoDojo/0.4/PBEsol/SR/standard/upf`（PD-A）。
- **元素覆盖**：PD-A = 72，MC3D PBEsol v2 = 70（`MC3D ⊂ PD-A`），SSSP = 103。
- ✅ **MC3D 33,142 结构受 PD-A 元素 gap 影响：0（0.0%）**，不需 SSSP fallback。
- 趣闻：`PD-A − MC3D = {La, Lu}` —— MC3D PBEsol v2 整库零镧系/零锕系（Materials Cloud
  当年按 PBEsol pseudo 可用性预过滤过）。
- **跨数据集（MP / JARVIS）的 element gap** 走 §10.4 convention（MC3D 阶段不激活）。
- **SOC 路径（Phase C）** 必须 PseudoDojo FR family，SSSP 没有 FR 变体。

### 10.2 PD-A vs SSSP

```
PD-A (PBEsol/SR/standard)  :  72 elements
SSSP (1.3/PBEsol/precision): 103 elements   (strict superset of PD-A)
SSSP - PD-A                :  31 elements
```

31 个缺失元素：中段镧系 Ce–Yb（13）+ 全部锕系（15）+ 边缘放射性 At/Fr/Ra（3）。
**PD-A 含 La/Lu 但没中间 13 个**：La（4f⁰）/ Lu（4f¹⁴ 全填深结合）常规 SR pseudo 即稳；
Ce–Yb（4f¹–4f¹³ 部分填充）SR 难收敛，必须 SR3plus 把 4f⁺³ 冻进 core。

### 10.3 SR3plus 与 single-methodology 约束

```
SR3plus (14): Ce..Yb + Lu      PD-A union SR3plus = 85 elements
overlap with PD-A: {Lu}
```

**关键约束**：SR3plus **只有 PBE，没有 PBEsol**（PseudoDojo 未发布 PBEsol/SR3plus）。
Phase A 用 PBEsol 时 fallback 到 SR3plus = 混 functional，违反 §3.1 single-methodology。
→ 因此镧系结构 fallback 选 **SSSP**（纯 PBEsol）而非 SR3plus（混 PBE）。

### 10.4 Pseudo selection convention（跨数据集）

为后续扩到含镧系/锕系的 MP / JARVIS 预定 builder 路由（`recommend_pseudo_family`）：

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

- **SOC 硬约束**：FR family 只 71 元素；SSSP 没 FR；SR 顶 SOC 是物理错。SOC 结构含 FR 漏掉
  的元素时 Phase 1 唯一选项是 skip（标 `phase_c_skip='no_fr_pseudo'`）。
- MC3D 永远走 `pd_a_default`；扩到 MP/JARVIS 自动激活 SSSP fallback，**builder 逻辑零改动**。
- 新增 schema 字段 `pseudo_selection_reason` 让 model 学"什么结构会 fallback 到 SSSP"。

---

## 11. 收敛参数全景

### 11.1 Phase 1 当前覆盖

| 参数 | 状态 | 备注 |
|---|---|---|
| `ecutwfc` | ✅ Stage 1 扫（cutoff） | anchor low−10..high+15（§5.2） |
| `ecutrho` | ✅ 联动 | NC `4×ecutwfc`；PAW 8–12× |
| `degauss` | ✅ Stage 2 扫，**仅金属** | 绝缘体锁 0.01（cold）；由分类 gate（§5.3） |
| k-mesh / kindex | ✅ Stage 3 扫 | `goldilocks_core.build_kmesh_entries`，逐轮加密 |
| `kpoints_distance` | ✅ Stage 3 变量；cutoff/degauss 阶段锁 0.30 | 由 `build_kmesh_entries` 逐轮给出 |
| `smearing` | ✅ 全局 `cold` | degauss 见上（金属扫、绝缘体锁 0.01） |
| `conv_thr` | ✅ 全局锁 2e-10 Ry/atom | 与 MC3D 对齐 |
| `mixing_beta` / `electron_maxstep` | ✅ 锁 0.4 / 200 | |
| `occupations` | ✅ 全局 `smearing` | metal/insulator 单分支 |
| `nbnd` | ✅ ≥ n_occ + max(4, ⌈0.5·n_occ⌉) | HOMO/LUMO 可填 |
| `nspin` / `starting_magnetization` | ✅ §4 决策 | 不 sweep，只决策 |
| `pseudo_family` | ✅ Phase A 锁 PD-A | Phase B 才扫多 family |
| `tprnfor` / `tstress` | ✅ 全局 True | 力进收敛判据（§5.5），应力仅 audit |

### 11.2 Phase 1.5 / 2 / future 扩展维度

> （degauss/smearing 收敛已上移到 Phase A 主线，见 §5.2/§5.3，不在本节。）

- **smearing_type sweep**（Phase 1.5，仅金属）：Phase A 固定 `cold`；后续比较 cold / mp1 /
  gauss 对金属的影响（degauss 本身已在 Phase A 扫）。
- **force / stress 阈值**（Phase 2 vc-relax）：`forc_conv_thr` / `press_conv_thr`，与
  cutoff/kmesh 正交。
- **vdW**（Phase 1.5）：`vdw_corr ∈ {grimme-d3/d4, ts, rVV10}`，对层状/分子晶体影响大；
  MC3D 主体 bulk，优先级低。
- **SOC**（Phase C）：`noncolin/lspinorb/nspin=4` + FR family（见 §3.3 / §10.4）。
- 其余（MC3D 主路径外）：supercell（缺陷）、vacuum/slab thickness（2D/表面）、dipole
  correction、q-mesh/phonon supercell（Phase 3）、DFT+U、hybrid functional（代价 100×，scope 外）。

**非收敛但影响结果、记进 schema 作 feature 的**：pseudo functional（PBEsol）/ method
（NC）/ accuracy tier（standard）/ `tot_charge=0` / `vdw_used=False` / `assume_isolated=None`。

**model 端核心 sweep label**（均 Phase A 产出）：`ecutwfc`（cutoff regression）、k-mesh
（kpoints regression）、`degauss`（金属 smearing regression）；（B）`pseudo_family`
（pseudo classification）。这些是 model 端核心 y 标签产出，所有 schema 设计最终服务于此。

---

## 12. 安装与配置（macOS + SCARF + QE）

> ✅ 这是**实测可用**的当前安装方式（brew RabbitMQ/PostgreSQL + `presto` on PostgreSQL +
> `core.ssh_async`），与本机现状一致：AiiDA 2.7.3、profile `presto`、RabbitMQ 4.3、
> computer `scarf`、code `qe-7.2-pw@scarf`、pseudo `PseudoDojo/0.4/PBEsol/SR/standard/upf`。
> 命令里的本地路径（`/Users/.../Desktop/*.yaml`）按自己机器改。

### 12.1 AiiDA + 服务

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

先确保本地 `ssh scarf` 免密能登。`scarf.yaml`：

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

> `core.ssh_async`（基于 asyncssh）是 AiiDA 推荐 transport，比已 deprecated 的 `core.ssh`
> 显著快，且没有 `safe_interval` 这种串行闸门 —— 对 Phase A 33k × 多 round 的大量 SSH
> transport 是必需（`core.ssh` 串行 30s 间隔会成 production blocker）。asyncssh schema 精简，
> 大量 SSH 选项（key file / proxy / agent）从 `~/.ssh/config` 读，不在 YAML 里。

### 12.3 Quantum ESPRESSO code

SCARF 用 EasyBuild 集中编译 QE（维护 user `scarf562`）。`qe-7.2-pw@scarf.yaml`：

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

> 要点：先 `module load amd-modules`（AMD partition 工具链 bundle，重置工具链所以不需
> `module purge`），再 load QE module。不写死 `OMP_NUM_THREADS` —— builder 在 §13 动态
> 注入 `--cpus-per-task` + `OMP_NUM_THREADS`。

### 12.4 PseudoDojo 赝势

```bash
pip install aiida-pseudo
# Phase A family (the only one MC3D needs):
aiida-pseudo install pseudo-dojo -v 0.4 -x PBEsol -f upf -s high
verdi -p presto group list -a
```

Phase B/C 需要时再装其余 family（NC v0.4 的 PBE/PBEsol/LDA × std/stringent、PAW JTH v1.0
× std/stringent、FR variants）。安装幂等，已装的跳过。**物理上不可能的组合别白试**
（服务器 404）：LDA×FR、LDA/PBEsol × SR3plus、PBEsol×PAW、PAW×FR、PAW×SR3plus。

### 12.5 注意：别在这个 env 直接装 aiida-workgraph

`aiida-workgraph 0.8.1` 会把 `aiida-core` 降级到 2.7.x，而 `aiida-quantumespresso 5.0.0`
需要 `aiida-core~=2.8` → 依赖冲突。若需要 workgraph，新建独立 env
（`conda create -n aiida-workgraph python=3.12`）。误装后恢复：

```bash
pip uninstall -y aiida-workgraph aiida-pythonjob aiida-shell node-graph node-graph-widget
pip install -U "aiida-core[atomic-tools]~=2.8" aiida-quantumespresso
verdi -p presto daemon restart && verdi -p presto status
```

### 12.6 重启 Mac 后启动服务

brew services 一般会自启 RabbitMQ/PostgreSQL；daemon 需手动：

```bash
brew services start rabbitmq postgresql   # if not already running
verdi daemon start
verdi status                              # verify all green
```

### 12.7 踩坑速查（troubleshooting）

| 症状 | 原因 / 修复 |
|---|---|
| `ImportError: cannot import name 'Sentinel' from typing_extensions` | conda 装包 partial-fail 留双 dist-info。`ls site-packages \| grep typing_ext`，删旧 `*.dist-info`，`conda install --force-reinstall typing_extensions`（`pydantic_core ≥ 2.27` 需 `typing_extensions ≥ 4.13`） |
| `bad CPU type in executable: verdi` | Apple Silicon 跑 x86 miniconda 需 Rosetta：`softwareupdate --install-rosetta --agree-to-license`（本地不跑数值计算，无性能代价；QE 全在 SCARF SSH 跑） |
| `new collation ... incompatible with template database (C)` | 建库必须 `TEMPLATE template0`（裸模板允许任意 locale）；并把 UTF-8 locale 写进 `~/.zshrc` 兜底 |
| psql 报 `syntax error at or near "CREATE"`，提示符变 `postgres-#` | 多语句漏分号；`postgres-#`（中划线）= 续行，每条 SQL 末尾必须 `;` |
| `connection to server on socket ... failed: No such file` | unix socket 路径不对，fallback `psql -h localhost ...`；verdi/aiida 走 TCP 不受影响 |
| 看到 stale `postmaster.pid` | **别直接 `rm`** —— Apple Silicon + conda PG 实测删它会触发还在跑的 PG 主动 graceful shutdown。先 `ps aux \| grep postgres` 确认进程真没了，再删后重启 |
| terminal 每 ~5min 刷 checkpoint LOG | 纯噪声：`ALTER SYSTEM SET log_checkpoints = off; SELECT pg_reload_conf();` |
| `checkpoints are occurring too frequently ... increase max_wal_size` | **Phase A 启动前必调**：`ALTER SYSTEM SET max_wal_size='4GB'; ALTER SYSTEM SET checkpoint_timeout='15min'; SELECT pg_reload_conf();`（100+ 并行 SCF submit 会触发 WAL thrashing） |
| jupyter 里 `DetachedInstanceError` | `verdi daemon restart` / PG 重启切了 session。不用重启 kernel，重新 `load_group/load_code/load_node` 即可 |

---

## 13. 资源采集 + HPC 文件保留

### 13.1 资源采集（`resources.py`）

三路数据源互校验：**SLURM `sacct`**（`MaxRSS`/`AveRSS`/`Elapsed`/`State`/`ExitCode`，
完成后 SSH 跑）、**QE `aiida.out`**（estimated RAM、PWSCF wall time，regex 解析）、
**AiiDA `node.attributes`**（`job_id`、`scheduler_state`，直接读）。

提交时主动声明内存让 sacct `ReqMem` 有意义：

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

`mem_per_node_mb` 由 `plan_resources()` 启发式估（v0，Phase A 必须；v1 Phase B+ 用 ML 替换）。
sacct 保留期 SCARF ≥ 12 个月，采集间隔留 4× 安全边际；超期未采标
`actual_resources_source='qe_only'`。

> SCARF 集群规格待 `sinfo` / `scontrol show node` 实测填进 `configs/clusters/scarf.yaml`：
> `default_partition`、`max_walltime_s`、`mem_per_node_mb`、`cores_per_node`、QE 是否 OMP 编译。

### 13.2 HPC 文件保留 —— `stash` + `clean_workdir=True`

完成时一步原子操作（retrieve 必要文件回本地 + stash 选定文件到 HPC 持久区 + 擦原 workdir），
不用手动 `rm -rf` 也不删整个 remote folder：

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

排除占盘主体（`wfc*.hdf5` / `charge-density.hdf5` / `*.upf` / `pseudo/` 等）。charge density
**只在相邻轮次之间临时复用**（§5.4 startingpot='file'），下一轮读完即随 workdir 清掉，**永不
stash / 长期保留** —— 所以不吃长期存储。完成后
AiiDA 创建 `RemoteStashFolderData` 挂在 CalcJob 上，output link `remote_stash`
（`node.outputs.remote_stash.target_basepath` 拿持久路径）。估算每 calc ~50 KB ×
33k × 多 round ≈ 几 GB。

---

## 14. Open questions + References

| # | 议题 | 当前默认 | 影响 |
|---|---|---|---|
| 1 | `gamma_pathological` 阈值 | 100 meV/atom 占位 | §5.6；P2 前用历史金属数据校准 |
| 2 | SCARF 集群规格 | 待 `sinfo` / `module avail` | §13.1 |
| 3 | model 端 element-disjoint split 每元素 N 个 | 未问 | §3.1；影响真需 33k 还是 15k 够 |
| 4 | SOC scope 标记方式 | `is_soc` 字段 vs `calc_type='scf_soc'` | §6；影响 model `supported_scope` |
| 5 | PSDI 上传通道 | 待确认 | Phase 1 末发布 |
| 6 | `goldilocks-core` 仓 fetch 状态 | 未确认 | Step 0 前置 |

**References**：
- `3-goldilocks-models/docs/PLAN.md` —— sibling model 契约
- `4-goldilocks-core/src/goldilocks_core/kmesh.py` —— kindex schedule 生成
- UKRI grant EP/Z530657/1
- PseudoDojo <http://www.pseudo-dojo.org/>
- Materials Cloud MC3D <https://www.materialscloud.org/discover/mc3d>
- aiida-quantumespresso <https://aiida-quantumespresso.readthedocs.io/>
- AiiDA RabbitMQ 兼容性 <https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/troubleshooting.html#rabbitmq-incompatibility>
