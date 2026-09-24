# gmlst

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Bioinformatics](https://img.shields.io/badge/domain-bioinformatics-green.svg)](https://github.com/indexofire/gmlst)

`gmlst` 是一个面向细菌基因组分型的高速 Python 3.12 命令行工具，支持传统多位点序列分型（MLST, Multi-Locus Sequence Typing）、大规模 cgMLST 和 wgMLST 方案，以及无预定义方案的发现型工作流。它同时支持组装基因组 FASTA 和原始测序 reads FASTQ，整合多种比对后端、多个公共数据库来源、本地自定义方案、离线缓存复用，以及本地 MST 可视化能力。

[English](README.md) | 简体中文

## 功能概览

- 🧬 **统一分型入口**：通过同一套 CLI 运行 `gmlst typing mlst`、`gmlst typing cgmlst` 和 `gmlst typing tgmlst`。
- ⚡ **多后端支持**：支持 BLAST+、KMA、minimap2、MUMmer4，内置 exact-hash 预解析用于 cgMLST 工作流。
- 🧫 **支持 FASTA 与 FASTQ**：既能处理组装完成的基因组，也能处理双端原始 reads。
- 🗂️ **支持 GenBank/EMBL 输入**：`.gbk`、`.gb`、`.gbff`、`.embl`（可 gzip 压缩）直接输入，记录即时转换，无需预处理。
- 🗂️ **多数据提供方**：支持 PubMLST、Pasteur BIGSdb、Enterobase、cgmlst.org 和本地自定义方案。
- 🧠 **灵活的 cgMLST 模式**：可选 `fast`、`ultrafast`、`balanced`，适配不同速度与证据需求。
- 🆕 **新等位基因工作流**：支持发现 novel allele、提取 novel profile，并构建实验室自定义 MLST 数据库。
- 🔍 **无方案分型**：通过 `tgmlst` 进行 de novo 等位基因发现，不依赖预先选择的公共方案。
- 📦 **丰富输出格式**：支持 `tsv`、`json`、`pretty`，也支持 GrapeTree 兼容导出。
- 📊 **质量评分**：每个样本获得 0-100 分与状态码（PERFECT/NOVEL/MIXED/MISSING/BAD），随 JSON 输出；`--minscore` 支持批量质控过滤。
- 🌐 **本地可视化**：使用 `gmlst visual web` 启动 Flask + Vue 本地网页界面，查看 MST 结果。
- 🐳 **流水线就绪**：内置全部后端的 Docker 镜像与 Nextflow/Snakemake 示例，可直接接入监测流水线。
- 💾 **缓存优先**：已下载的方案和已构建索引会复用，便于离线运行和重复分析。
- 🧵 **批量处理**：支持样本级并行 worker 和后端线程配置。
- 🧬 **CDS 感知调用**：cgMLST 工作流可结合 Pyrodigal 进行 CDS 预测，并支持 chewBBACA 风格分类路径。
- 🤖 **AI 智能体友好**：stdout 只输出数据、JSON 带版本信封、退出码语义稳定，方便脚本和 AI 智能体程序化解析。

## 安装

### 快速安装

推荐使用 conda 虚拟环境安装 gmlst 工具。

```bash
conda create -n gmlst
conda activate gmlst
conda install python=3.12
pip install gmlst
```

要让gmlst能开展工作，还需要安装生信比对软件，目前 fasta 数据支持的后端有 blast, minimap2, nucmer 和 kma。fastq 数据支持的后端是 kma。可以根据自己的数据源需要进行安装

```bash
# 让 gmlst 发挥所有功能，安装所有的依赖软件
conda install blast, minimap2, mummer4, kma
```

其他安装方法参见文档/安装部分。

## 快速开始

### 1. 浏览并下载方案

```bash
# 零配置：完全跳过方案选择 — gmlst 从基因组识别物种，
# 自动挑选匹配方案、下载并分型
gmlst typing mlst sample.fna

# 知道物种但记不住方案名？用 -n 解析
# （唯一命中自动选择；多个命中打印候选表）
gmlst typing mlst -n bordetella sample.fna

# 物种指纹库为自动检测提供支持；可按需构建
gmlst scheme update-fingerprints

# 查看缓存中和可用的方案
gmlst scheme list

# 分页查看缓存中和可用的方案（交互式终端专用）
gmlst scheme list --pager

# 只看某一个 provider，比如pubmlst.org的scheme
gmlst scheme list -p pubmlst

# 下载方案到本地缓存
gmlst scheme download -s saureus_1

# 更新所有已缓存的方案：先列出清单，再请求 Y/N 确认
gmlst scheme update -a
gmlst scheme update -a --yes     # 跳过确认，适合脚本

# 从缓存中删除方案（删除前同样会请求确认）
gmlst scheme remove saureus_1
```

### 2. 对样本分型

```bash
# 对基因组组装子做 MLST
gmlst typing mlst -s saureus_1 sample.fasta

# 对双端 reads 做 MLST，前提条件是安装了 kma 作为后端
gmlst typing mlst -s saureus_1 sample_R1.fastq.gz sample_R2.fastq.gz
# 软件支持使用通配符，能识别 _1/_2, _R1/_R2 的双端数据文件
gmlst typing mlst -s saureus_1 sample*.fastq.gz

# 对组装结果做 cgMLST
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fasta
```

### 3. 批量处理

`--max-workers N` 让 N 个样本并行分型，是批量运行的主要提速手段。它与 `-t/--threads` 不同：`-t` 并行化单次后端调用，`--max-workers` 在样本间展开（此时每样本的后端线程强制为 1）。`kma` 和 `nucmer` 后端无法有效利用 `-t`，因此 `--max-workers` 是它们唯一的提速方式。

```bash
# 16 个样本并行批量分型
gmlst typing mlst -s saureus_1 -t 1 --max-workers 16 -o results.tsv samples/*.fasta

# FASTQ 批量：配合 kma 后端
gmlst typing mlst -s saureus_1 -b kma -t 1 --max-workers 16 -o results.tsv samples/*_R1.fastq.gz

# 保存成 JSON 格式，便于后续 novel 提取，或者投喂数据给AI
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

在 639 个百日咳杆菌组装上实测（16 workers，结果与串行完全一致）：

| 后端 | 串行（`-t 16`） | `--max-workers 16` |
| --- | --- | --- |
| minimap2 | 55 s | **9 s** |
| blastn | 97 s | **31 s** |
| nucmer | 270 s | **76 s** |
| kma | 330 s | **48 s** |

### 4. 理解输出结果

默认输出为 TSV，风格与 `tseemann/mlst` 兼容。

```text
FILE            SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample1.fasta   saureus_1   1   1     1     1     1    1    1    1
sample2.fasta   saureus_1   -   1     ~2    3?    -    1    1    1
```

- 纯数字，表示 exact 已知等位基因匹配
- `23*`，表示同一等位基因出现在多个拷贝上（如基因在两条染色体上重复），不影响 ST 判定
- `~23`，表示非 exact 但高覆盖的调用，通常对应 closest 或 novel 倾向位点，具体可结合 identity 判断
- `15?`，表示 partial 命中，覆盖度不足
- `-`，表示该位点未找到

如果想看更适合人工阅读的输出，可使用 `--format pretty`。如果要做自动化分析，推荐使用 `--format json`。

## 比对后端

| 后端 | 是否可直接作为 CLI 后端 | FASTA | FASTQ | 适用场景 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `blastn` | 是 | 是 | 否 | 经典组装基因组 MLST | 适合做精确等位基因调用和重点复核 |
| `kma` | 是 | 是 | 是 | FASTQ 分型和 cgMLST FASTQ 路径 | 对 reads 映射型等位基因调用很实用 |
| `minimap2` | 是 | 是 | 否 | 快速组装分型和灵活的工作流 | cgMLST 优化路径中使用很多 |
| `nucmer` | 是 | 是 | 否 | 组装级敏感比对 | 适合较远距离匹配和补充证据 |

### 后端说明

- `typing mlst` 和 `typing cgmlst` 会自动识别常见双端 FASTQ 命名模式，例如 `_R1/_R2`、`_1/_2`、`.1/.2`。
- `typing cgmlst` 在 FASTA 组装输入时默认使用 `minimap2`。
- 对于 FASTQ cgMLST，CLI 采用 KMA-first 策略，chew 风格 cgMLST 模式主要面向 FASTA 场景。
- FASTQ 输入会自动切换到 KMA 后端（`mlst` 和 `cgmlst` 均如此）。
- `--max-depth` — 对 FASTQ 进行最大读深子采样（默认 100x，仅限 FASTQ）
- `GMLST_MINIMAP2_KMER_ENGINE=python|kmc|auto` 可控制 minimap2 的 k-mer 支持评分引擎。

## 数据提供方

| Provider | 数据来源 | 常见用途 |
| --- | --- | --- |
| `pubmlst` | PubMLST REST catalog | 常用公共 MLST 方案 |
| `pasteur` | Pasteur BIGSdb API | BIGSdb 托管的物种方案集合 |
| `enterobase` | Enterobase scheme downloads | 大型整理后的方案集 |
| `cgmlst` | cgmlst.org | 偏向 cgMLST 的公共方案 |
| `local` | 本地缓存与自定义方案 | 实验室私有数据库和自定义导出方案 |

示例：

```bash
# 查看 pubmlst 网站提供的 schemes
gmlst scheme list -p pubmlst

# 查看 enterobase 网站提供的类型是 cgmlst 的 schemes
gmlst scheme list -p enterobase -t cgmlst

# 查看用户建立的本地 scheme 
gmlst scheme list -p local

# 查看具体一个 scheme 的信息：saureus_1
gmlst scheme show -s saureus_1
```

## Novel 数据工作流

你可以把日常分型中发现的 novel 结果整理成一个本地自定义方案。

```bash
# 1. 对样本分型并保存 JSON
gmlst typing mlst -s saureus_1 --format json *.fasta -o typing_results.json

# 2. 提取 novel allele 和 novel profile
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel_data

# 3. 创建本地自定义方案
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection 2024"

# 4. 后续追加更多 novel 数据
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data

# 5. 导出到 GrapeTree 或 MST 下游分析
gmlst scheme export -s custom_1 --format grapetree -o custom_1_grapetree.tsv
```

如果你只有 TSV 分型结果，但仍保留原始样本文件，也可以走 TSV fallback：

```bash
gmlst utils extract -i typing_results.tsv -s saureus_1 --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel_data
```

## cgMLST 模式

`gmlst typing cgmlst` 支持多种模式，用于平衡速度和证据强度。

| 模式 | 作用 | 适合场景 |
| --- | --- | --- |
| `fast` | 结合 exact-hash 与 minimap2 预过滤，并做定向补救 | 日常组装 cgMLST |
| `ultrafast` | 更激进的速度配置，带有受限第二轮补救 | 大批量样本追求更快周转 |
| `balanced` | hash-first 路径加定向 `blastn` fallback | 想兼顾速度与低置信度复核 |

示例：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode ultrafast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode balanced sample.fna
```

## 无方案分型（`tgmlst`）

当你希望在没有预选公共方案的情况下进行等位基因发现时，可以使用 `tgmlst`。

```bash
# 运行 scheme-free typing
gmlst typing tgmlst sample.fna --stats

# 保存发现到的方案，供后续复用
gmlst typing tgmlst sample.fna --save-scheme tgmlst_scheme.json

# 载入已保存方案再次分析
gmlst typing tgmlst another_sample.fna --load-scheme tgmlst_scheme.json --format json
```

常用参数包括 `--hash-strategy`、`--summary-report`、`--error-report` 和 `--fail-on-error`。

`--stats` 的运行统计 JSON 输出到 stderr（信封常量 `gmlst-tgmlst-stats-v1`），不会混入 stdout 的分型结果，重定向和管道可以放心使用。

## 可视化

通过本地 Web 应用从 cgMLST 或 GrapeTree 风格表格构建 MST。

```bash
gmlst visual web --open-browser
```

也可以绑定自定义地址：

```bash
gmlst visual web --host 0.0.0.0 --port 8787
```

网页界面接受 TSV 数据，构建最小生成树，并通过本地 Flask API 提供 Vue 前端。

也可以不启动 Web 界面，直接从管道构建 MST。`visual mst/matrix/heatmap/locus-diff` 的 `--input -` 以及 `visual compare` 的 `--left -`/`--right -` 都支持从 stdin 读取：

```bash
# 分型结果直接通过管道送入 MST 摘要，无需临时文件
gmlst typing cgmlst -s vparahaemolyticus_3 *.fna --format tsv | gmlst visual mst --input - --format summary
```

`--format summary` 会输出面向 AI 智能体的紧凑摘要，并附带 `method`、`include_missing`、`aggregate_profiles`、`cluster_edge_threshold`、`outlier_weight` 等溯源字段。更多 CLI 可视化命令见[可视化指南](docs/zh/visual_guide.md)。

## 配置

自 2025 年 1 月起，PubMLST 和 Pasteur 要求对 2024 年 12 月 31 日之后新增的数据进行认证。获取 API key 后配置：

```bash
# PubMLST：在 pubmlst.org → Preferences → API keys 注册
gmlst config set GMLST_PUBMLST_API_KEY your-key-here
gmlst config init     # 每个新 shell 自动加载（只需运行一次）
source ~/.config/gmlst/env.sh   # 当前 shell 立即生效
```

使用 `gmlst config show` 查看所有配置变量及当前值：

```bash
gmlst config show                          # 分组表格视图
gmlst config env                           # shell 可 source 的格式
gmlst config get GMLST_CACHE_DIR           # 查看单个变量
gmlst config set GMLST_CACHE_DIR /data     # 写入 ~/.config/gmlst/env.sh
gmlst config init                          # 在 shell rc 文件中添加 source 行（只需运行一次）
```

`config show` 会对敏感值做掩码处理：`GMLST_*_API_KEY` 和 token 类变量只显示前 4 位和后 4 位（如 `abcd****ef01`），未设置的变量不会被假掩码填充，方便区分"已设置"和"未设置"。

`config get --format json` 返回带版本号的信封（`gmlst-config-get-v1`），`data` 中包含 `name`、`value`、`source` 和 `is_default`。`source` 表示取值来源：`file`（来自 env.sh 配置文件）、`env`（来自当前 shell 环境）或 `default`（未设置，使用内置默认值，此时 `is_default` 为 `true`）：

```bash
gmlst config get GMLST_CACHE_DIR --format json
```

关键环境变量：

| 变量 | 作用 |
| --- | --- |
| `GMLST_CACHE_DIR` | 覆盖缓存根目录（自动检测：conda 环境使用 `$CONDA_PREFIX/share/gmlst`，venv 使用 `$VIRTUAL_ENV/.cache/gmlst`，默认 `~/.cache/gmlst`） |
| `GMLST_TMPDIR` | 覆盖分型与精修阶段使用的临时目录 |
| `GMLST_MINIMAP2_KMER_ENGINE` | 选择 minimap2 的 k-mer 支持评分引擎，取值为 `python`、`kmc` 或 `auto` |
| `GMLST_PUBMLST_BASE_URL` | 覆盖 PubMLST API 基础地址 |
| `GMLST_PASTEUR_BASE_URL` | 覆盖 Pasteur BIGSdb API 基础地址 |
| `GMLST_PRIVATE_BIGSDB_URL` | 注册私有 BIGSdb 实例为额外 provider |
| `GMLST_PRIVATE_BIGSDB_NAME` | 私有 BIGSdb provider 的名称 |
| `GMLST_PRIVATE_BIGSDB_LABEL` | 私有 BIGSdb provider 的显示标签 |
| `GMLST_PUBMLST_API_KEY` | PubMLST API key（用于 2024 年后数据访问） |
| `GMLST_PASTEUR_API_KEY` | Pasteur BIGSdb API key（用于 2024 年后数据访问） |
| `ENTEROBASE_TOKEN` | Enterobase API 认证令牌 |

示例：

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
export GMLST_MINIMAP2_KMER_ENGINE=auto
export GMLST_PUBMLST_BASE_URL="https://rest.pubmlst.org/db"
export GMLST_PASTEUR_BASE_URL="https://bigsdb.pasteur.fr/api/db"
```

私有 BIGSdb 示例：

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```

## 输出格式说明

默认 TSV 格式会用紧凑标记表示每个位点的调用状态。

| 标记 | 含义 | ST 分配 |
| --- | --- | --- |
| `23` | exact 等位基因调用，单拷贝 | ✅ 是 |
| `23*` | exact 等位基因调用，**同等位基因多拷贝**（如基因在两条染色体上重复） | ✅ 是（使用 `23`） |
| `~23` | 非 exact 但高覆盖的调用，可表示 closest 命中或 novel 倾向位点 | ❌ Novel |
| `15?` | partial 调用，覆盖度低于置信阈值 | ❌ 不完整 |
| `1,2` | **冲突性**多拷贝——不同等位基因出现在不同拷贝上 | ❌ 模糊 |
| `1,1` | 同等位基因拷贝展开（使用 `--count-same-copy` 标志） | ✅ 是 |
| `-` | 位点缺失 | ❌ 不完整 |

### 基因断裂横跨 contigs

碎片化组装常把看家基因断在两个 contig 之间。对 `blastn` 和 `minimap2` 后端，gmlst 会对该位点的逐 contig 片段比对做联合拼接：

- **重叠断裂**（contigs 在基因内部重叠且重叠区序列一致）会被平铺重构为一条完整比对，可产生正常的 exact 调用。
- **衔接断裂**（无重叠）绝不产生 exact 调用 — 接合处不可见的 indel 无法排除 — 但 `?` 部分调用会报告全部片段的联合覆盖度，JSON 输出并列出每个片段（`contig`、`allele_start`、`allele_end`）。

触发拼接所需的最小等位基因坐标重叠默认 10 bp，可用 `--min-join-overlap` 调整（`0` = 最宽松；重叠区序列仍须完全一致）。

如果要保留结构化字段，例如每个位点的调用元数据和 `novel_sequence` 信息，建议使用 JSON 输出。

分型结果中的每个样本还携带 `score`（0-100：exact 调用计 100 分，novel/partial 按调用置信度缩放，缺失或冲突位点计 0 分，取所有基因座平均）与 `status` 状态码——`PERFECT`、`NOVEL`、`MIXED`、`MISSING`、`BAD`、`NONE`。使用 `--minscore <float>` 可将低于质量阈值的样本从 TSV 和 JSON 输出中一并剔除（批量质控）：

```bash
# 只报告得分不低于 50 的样本
gmlst typing mlst -s saureus_1 --minscore 50 --format json *.fasta -o qc_passed.json
```

### JSON 输出信封（0.2.0 起）

自 0.2.0 起，所有 CLI JSON 输出（stdout 或 `-o` 输出文件）统一包裹在带版本号的信封中，程序可以在解释 `data` 之前先校验 `schema_version`：

```json
{
  "schema_version": "gmlst-typing-v1",
  "data": [
    { "sample_id": "sample1.fasta", "scheme": "saureus_1", "st": 1 }
  ]
}
```

原来的数据原样移入 `data` 字段。TSV/CSV/text 输出不使用信封；`utils extract` 仍兼容旧版 gmlst 输出的裸数组格式。完整信封常量列表见[命令参考](docs/zh/commands.md#json-输出信封)。

与之配套的流纪律：stdout 只输出数据，警告、进度条、spinner 和 "Results written to" 提示全部走 stderr，管道和重定向不会被污染。

### 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功（包括未加 `--fail-on-error` 的 tgmlst 部分样本失败） |
| `1` | 运行时失败（包括 `scheme update` 中任一 provider 或方案失败） |
| `2` | 用法错误，例如非法参数，或 `scheme list --name` 传入非法正则 |
| `3` | tgmlst 输入阶段失败 |
| `4` | tgmlst 组装阶段失败 |
| `5` | tgmlst 预测阶段失败 |
| `6` | tgmlst 未知阶段失败 |

tgmlst 的阶段退出码从 3 开始编号，避免与 click 的用法错误退出码 2 冲突。

## 多拷贝位点说明

- **同等位基因多拷贝**（`23*`）：同一个等位基因在多个基因组拷贝上被检测到（如副溶血弧菌等物种的双染色体上的管家基因重复）。这是正常生物学现象，**不影响 ST 分配**。`*` 标记仅用于提示，ST 查找使用不带 `*` 的等位基因编号。
- **冲突性多拷贝**（`1,2`）：不同等位基因出现在同一位点的不同拷贝上（可能是旁系同源或混合感染）。ST 报告为 `-`，因为无法分配可信的 profile。
- **显式拷贝计数**（`1,1`）：使用 `--count-same-copy` 展开同等位基因多拷贝为逗号格式，供下游工具使用。

推荐复核流程：

```bash
# 第一轮快速筛查
gmlst typing mlst -s vparahaemolyticus_1 *.fna -o pass1.tsv

# 对可疑样本进行定向复核
gmlst typing mlst -s vparahaemolyticus_1 -b blastn --count-same-copy flagged_sample.fna
```

## 开发

开发环境初始化：

```bash
pixi install
pixi run install-dev
```

常用任务：

```bash
pixi run lint
pixi run format-check
pixi run test
pixi run check
```

也可以直接运行 Ruff：

```bash
pixi run ruff check .
pixi run ruff format .
```

贡献流程见 [docs/contributing.md](docs/contributing.md)，模块边界与分型路径说明见 [docs/architecture.md](docs/architecture.md)。

## 文档索引

- [docs/README.md](docs/README.md) 查看完整文档地图
- [docs/zh/installation.md](docs/zh/installation.md) 查看安装说明
- [docs/zh/quickstart.md](docs/zh/quickstart.md) 查看快速上手指南
- [docs/zh/commands.md](docs/zh/commands.md) 查看 CLI 命令参考
- [docs/zh/configuration.md](docs/zh/configuration.md) 查看配置参考
- [docs/zh/pipelines.md](docs/zh/pipelines.md) 查看流水线集成（Docker/Nextflow/Snakemake）
- [README.md](README.md) 返回英文根文档

## 许可证

项目基于 [MIT License](LICENSE) 发布。

## 致谢

- 项目思路受到 [tseemann/mlst](https://github.com/tseemann/mlst) 启发
- 公共方案数据来源于 [PubMLST](https://pubmlst.org/)
