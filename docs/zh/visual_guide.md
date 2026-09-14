# 可视化指南

本文介绍 `gmlst` 的本地可视化工作流，包括 Web 服务器启动、输入格式、MST 构建、算法选择、CLI 导出、智能体摘要输出、布局切换、元数据着色以及前端构建方式。若要先从 CLI 导出适合可视化的 profile 表，请结合 [novel_workflow.md](novel_workflow.md) 和 [commands.md](commands.md) 一起阅读。

## 概述

`visual` 模块提供一个本地 Web 界面，用于把 MLST 或 cgMLST 的 profile 表构建成 MST（Minimum Spanning Tree，最小生成树）并进行交互式查看。

它特别适合以下场景：

- 查看样本如何按 allele profile 聚类
- 根据元数据列给节点着色
- 比较不同 missing token 处理方式对距离的影响
- 导出适合汇报或论文使用的 SVG 图

CLI 子命令适合以下场景：

- 无浏览器环境下构建 MST payload
- 生成供下游工具或 AI 智能体消费的 JSON
- 获取可在一个 context 窗口内读完的紧凑分析摘要

## 启动服务器

最常用的启动方式是：

```bash
gmlst visual web --open-browser
```

常见参数：

- `--host`，默认 `127.0.0.1`
- `--port`，默认 `8787`

示例：

```bash
# 使用默认地址并自动打开浏览器
gmlst visual web --open-browser

# 使用自定义端口
gmlst visual web --port 9000

# 明确需要远程访问时绑定所有网卡
gmlst visual web --host 0.0.0.0 --port 8787
```

只有在可信网络环境中才建议这样做。这个可视化服务更适合作为本地便利界面使用，而不是带认证能力的对外服务。

典型启动日志：

```text
Serving MST web app on http://127.0.0.1:8787
```

## 上传数据

界面支持两类常见 profile 表：

1. `gmlst` 生成的 profile 表
2. 第一列为 `#Strain` 的 GrapeTree 风格文件

解析器可以自动识别 tab、逗号和分号分隔，因此 TSV 是最常见形式，但 CSV 风格文件也可以导入。

这意味着你既可以直接上传分型结果表，也可以先从 CLI 导出 GrapeTree 格式再导入。

GrapeTree 风格表头示例：

```tsv
#Strain	dnaA	ftsZ	gyrB	...
ST1	12	44	109	...
ST2	12	44	111	...
```

带元数据列的示例：

```tsv
#Strain	dnaA	ftsZ	gyrB	Source	Ward	Year
ST1	12	44	109	blood	ICU	2024
ST2	12	44	111	wound	WardA	2024
```

元数据既可以直接嵌入同一个表，也可以作为单独的 metadata 文件按样本 ID 关联后上传。

### 元数据自动检测

当表中混合了 locus 列和自由文本列（如 `clade`、`source`、`分离地点`）时，解析器会自动检测值是否像 allele call（纯数字、`LNF`、`~2`、`1?`、`NIPH`、逗号分隔多 allele 等）。值全部不像 allele 的列会被自动归类为元数据，无需手动拆分。

一个注意点：纯数字列（如 `year`）与 allele 编号无法区分，会保留为 locus。需要按年份分析时，请通过单独的 `--metadata` 文件传入。

## 构建 MST

加载 profile 表后，界面会根据样本之间的 allele 差异构建最小生成树。

典型流程如下：

1. 启动 `gmlst visual web`
2. 上传或粘贴 profile 表
3. 选择 MST 相关参数
4. 渲染图形
5. 如有需要导出 SVG

MST 在这里有三个主要价值：

- 用紧凑方式展示样本间最近邻关系
- 很适合基于 cgMLST profile 的比较
- 能在进入更复杂系统发育分析之前，先做快速交互式探索

### MST 算法

支持三种算法：

| 方法 | 算法 | 优化目标 | 适用场景 | 规模上限 |
|---|---|---|---|---|
| `grapetree_classic` **（默认）** | Kruskal MST（Hamming 距离） | 总 Hamming 距离最小 | **大数据集（500+ 样本）** | O(n² log n) — 1000 样本约 37s |
| `grapetree_v2` | Edmonds + 分支重排（harmonic/eBurst 权重） | 复合种群结构指标 | **与 GrapeTree 软件输出对齐** | O(n²) 距离矩阵 — 1000 样本约 255s、3.5GB 内存 |
| `edmonds` | Edmonds 有向生成树 + 子树重排 | 总 Hamming 距离最小 | 小数据集（≤100 样本），需要确定性结果 | O(n³) — **n>200 不可用** |

992 样本 × 100 loci 实测：

| 方法 | 耗时 | 峰值内存 | 总权重 |
|---|---|---|---|
| `grapetree_classic` | 37s | 230 MB | 8824 |
| `grapetree_v2` | 255s | 3.5 GB | 约为 classic 的 2 倍 |
| `edmonds` | >20 分钟（超时） | — | — |

各方法的关键行为差异：

- **edmonds** 通过子树重排能找到总权重最低的树（比 classic 低约 0.4%），但逐根循环使其复杂度为 O(n³)，超过约 200 个样本后不可用。
- **grapetree_v2** 使用复合指标（归一化距离 + harmonic 权重 + eBurst 权重），产生的树总 Hamming 权重可达最小值的 2 倍，但拓扑结构更符合种群聚类，且需要 O(n²) 内存存储距离矩阵。
- **grapetree_classic** 是标准 Kruskal 最小生成树：与 edmonds 权重相同（仅在并列时有差异），速度快、内存低。自 v0.1.6 起为默认方法。

在简单数据集（≤6 个样本、无权重并列）上，三种方法产生完全相同的树。在更大或更多态的数据集上，`grapetree_v2` 因复合优化目标而偏离其他方法，`edmonds` 通过重排找到略优于 `classic` 的树。

## CLI MST 命令

### 全量 JSON 输出

```bash
gmlst visual mst --input profiles.tsv --metadata meta.tsv --output result.json
```

生成完整 MST payload（节点、边、元数据、错配位点）。1000 样本约 750KB–1.1MB，**约 290K tokens，不能直接读入 LLM context**。适合工具链处理或作为 Web 前端数据源。

### 摘要输出（面向智能体）

```bash
gmlst visual mst --input profiles.tsv --metadata meta.tsv --format summary --output summary.json
```

生成紧凑分析摘要（1000 样本约 7KB，约 1K tokens），AI 智能体可直接读入。摘要包含：

| 字段 | 内容 | 分析价值 |
|---|---|---|
| `mst_summary` | 边数、权重最小/中位/最大值、零权重对数 | 树形概况与数据质量 |
| `clusters` | 连通分量（边权≤15）、大小、主导元数据、纯度 | 群体结构与克隆复合体 |
| `top_variable_loci` | 错配频率最高的位点 | 分型标记物候选 |
| `outliers` | 高边权（>50）连接的节点 | 高偏离/导入株、数据质量标记 |
| `suggested_analysis` | 可执行的后续分析建议 | 分析路线图 |

### 其他 MST 相关命令

```bash
# 成对距离矩阵
gmlst visual matrix --input profiles.tsv --output dist.json

# Allele 热图
gmlst visual heatmap --input profiles.tsv --output heatmap.json

# 比较两次分型结果
gmlst visual compare --left run1.tsv --right run2.tsv

# 两个样本之间的位点差异
gmlst visual locus-diff --input profiles.tsv --left-label s1 --right-label s2
```

## 智能体集成模式

AI 智能体（或脚本）消费 MST 结果时，推荐双层模式：

```
第一层（读 context）: --format summary → 约 7KB，直接读入
第二层（工具处理）:  --format json    → 约 1MB，用 Python 处理
```

典型的智能体工作流：

1. 运行 `gmlst visual mst --format summary` 并将 JSON 读入 context。
2. 仅凭摘要即可分析聚类结构、异常样本、标记位点。
3. 需要某个样本的邻居或某条边的错配位点细节时，写 Python 脚本处理全量 JSON，只返回提取结果。

这种模式在保持 LLM context 精简的同时，不丢失对全分辨率数据的访问能力。

## 布局选项

Web UI 支持两种布局：

- `tree`
- `radial`

### Tree 布局

适合强调分支结构、层次关系和传播链条的场景。

### Radial 布局

适合从中心向外查看整体结构，尤其是更像星状或更密集的数据集。

经验上：

- 中小规模暴发集合往往更适合 `tree`
- 更密集或更放射状的数据集通常更适合 `radial`

## 节点着色

界面可以根据上传表中的元数据列给节点着色。

常见可用字段包括：

- 样本来源
- 病区/科室
- 年份
- 地区
- 暴发标签

节点着色的价值在于：

- 快速判断聚类是否与流行病学信息一致
- 很容易识别混合来源的 cluster
- 让原本只有拓扑结构的图更容易解释

## Missing Token Penalty

可视化工作流提供 missing-token penalty 开关，用于处理 `LNF`、`NIPH`、`NIPHEM` 等特殊值，也就是 profile 表中常见的非精确或缺失类位点标记。

这个设置会影响缺失位点或特殊状态位点在距离计算中的权重。

通常可以对比两种视图：

- 更严格：缺失值也计入惩罚
- 更宽松：弱化缺失值的影响

当数据中混有高质量组装和部分不完整 profile 时，这种比较尤其有帮助。

## 导出

界面支持把当前图导出为 SVG，同时前端还支持导出图结构、会话状态和表格数据的 JSON/TSV。

SVG 的优势在于：

- 可无损缩放，适合论文和报告
- 后续可在矢量图软件中继续调整
- 文本标签通常比截图更清晰

## GrapeTree 导出 CLI

如果你想先从命令行生成适合 MST 工具的 profile 表，可以先导出 GrapeTree 格式：

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

这个文件使用 `#Strain` 表头，可直接进入可视化流程。

示例：

```tsv
#Strain	arcC	aroE	glpF	gmk	pta	tpi	yqiL
ST1	1	1	1	1	1	1	1
STN1	n1	7	3	9	4	2	1
```

## 架构简介

可视化系统由轻量级 Python Web 后端和 Vue 前端组成。

后端路由包括：

- `/`
- `/health`
- `/api/mst`（POST：`{tsv, metadata_tsv?, method?, include_missing?, aggregate_profiles?}`）
- `/api/distance-matrix`
- `/api/allele-heatmap`
- `/api/locus-diff`
- `/api/compare-results`

前端源码目录：

```text
gmlst/web/frontend/
```

构建后的静态资源目录：

```text
gmlst/web/static/visual/dist/
```

整体上可以理解为：

- Flask 负责提供页面和 API
- Vue 3 负责浏览器中的交互界面
- Vite 负责打包前端静态资源

MST 实现文件：

```text
gmlst/visual/mst.py            公共 API: build_mst_from_tsv
gmlst/visual/mst_shared.py     解析、距离计算、验证、共享辅助函数
gmlst/visual/mst_edmonds.py    Edmonds 有向生成树 + 子树重排
gmlst/visual/mst_grapetree.py  GrapeTree v2（复合指标）+ classic（Kruskal）
gmlst/visual/mst_summary.py    面向智能体/context 的紧凑摘要
```

## 构建前端

如果你修改了前端界面，需要重新构建前端资源。

推荐命令：

```bash
pixi run visual-ui-build
```

也可以直接使用 npm：

```bash
npm --prefix gmlst/web/frontend run build
```

如果只是普通用户使用可视化功能，并不需要手动构建前端，因为程序会直接使用 `gmlst/web/static/visual/dist/` 中的预构建资源。
