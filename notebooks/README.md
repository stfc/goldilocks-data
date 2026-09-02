# notebooks

探索性 notebook（非生产代码；生产逻辑落到 `src/goldilocks_data/`）。
2026-06-16 从 11 个零散 notebook 整理浓缩成下面 4 个,每个开头有一段说明。

| Notebook | 内容 | 由哪些旧文件合并 |
|---|---|---|
| [01-aiida-smoke-cookbook.ipynb](01-aiida-smoke-cookbook.ipynb) | Si bulk SCF 冒烟 + AiiDA 操作 cookbook（process-state、output 解析、5 个 QueryBuilder 模式、HPC 选择性清理、Parquet 行预览、节点删除） | aiida-scf |
| [02-physics-decisions.ipynb](02-physics-decisions.ipynb) | 每结构物理决策:4 种 SpinType 的 &SYSTEM 对比 + 奇偶电子 nspin 筛选（PLAN §3.4 / §4） | aiida-spintype, even-odd-electrons |
| [03-mc3d-and-pseudo-analysis.ipynb](03-mc3d-and-pseudo-analysis.ipynb) | MC3D 数据集 + 赝势覆盖分析:PD-A vs SSSP vs SR3plus 元素覆盖、MC3D v2 的 0.0% PD-A gap、33,142 结构磁性分类、v1 磁性、v1/v2 对比 | pseudo-analysis, mc3d-pbesol-v2-analysis, mc3d-pbesol-v1-analysis, mc3d-v1-v2-comparison |
| [04-pilot-sampling.ipynb](04-pilot-sampling.ipynb) | Phase A pilot 分层抽样（40 small + 40 medium + 20 large, seed=42 → `pilot/v1/mc3d-100`）+ pilot spin_type 决策 | structure-sample |

**注意:** notebook 03 的 MC3D 分析依赖 MC3D archive,当前 `presto` profile 里没导入,
**大部分 cell 不可重跑** —— cell 输出和 `data/processed/*.pkl` 是唯一记录,别清空输出。

数据:`data/processed/*.pkl`（v1/v2 磁性)、`data/pilot/v1/mc3d-100-meta.csv`、
`data/processed/v0.1.0-smoke/...parquet`（冒烟样例)。

原始 11 个 notebook 备份在仓库根目录 `.notebooks-orig-backup-20260616.tar.gz`,确认无误后可删。

QE k-point campaign 已整理到
[`codes/qe/kpoints/`](../codes/qe/kpoints/README.md)。生产提交脚本、当前分析
notebook 和结果 snapshot 都在该 task 目录中；旧的 06–08 notebook 仅作为本地
archive 保留，不纳入版本控制。
