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
- 🗂️ **多数据提供方**：支持 PubMLST、Pasteur BIGSdb、Enterobase、cgmlst.org 和本地自定义方案。
- 🧠 **灵活的 cgMLST 模式**：可选 `standard`、`chew-fast`、`chew-ultrafast`、`chew-bsr`、`chew-balanced`，适配不同速度与证据需求。
- 🆕 **新等位基因工作流**：支持发现 novel allele、提取 novel profile，并构建实验室自定义 MLST 数据库。
- 🔍 **无方案分型**：通过 `tgmlst` 进行 de novo 等位基因发现，不依赖预先选择的公共方案。
- 📦 **丰富输出格式**：支持 `tsv`、`json`、`pretty`，也支持 GrapeTree 兼容导出。
- 🌐 **本地可视化**：使用 `gmlst visual web` 启动 Flask + Vue 本地网页界面，查看 MST 结果。
- 💾 **缓存优先**：已下载的方案和已构建索引会复用，便于离线运行和重复分析。
- 🧵 **批量处理**：支持样本级并行 worker 和后端线程配置。
- 🧬 **CDS 感知调用**：cgMLST 工作流可结合 Pyrodigal 进行 CDS 预测，并支持 chewBBACA 风格分类路径。

## 安装

### 方式一，使用 pixi，推荐

Pixi 可以同时管理 Python、外部生信工具和可编辑安装的项目环境。

```bash
curl -fsSL https://pixi.sh/install.sh | bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi run gmlst --version
```

### 方式二，使用 pip

如果你已经有自己的 Python 环境和系统级工具管理方式，可以使用 pip 安装。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install gmlst

# 外部工具需单独安装，例如使用 conda 或 mamba
conda install -c bioconda blast minimap2 mummer4 mmseqs2 prodigal kma kmc samtools
```

### 方式三，从源码安装

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
gmlst --help
```

### pixi 环境中的外部工具

- `blast >=2.14`
- `minimap2 >=2.26`
- `mummer4 >=4.0`
- `mmseqs2 >=15`
- `prodigal >=2.6`
- `kma >=1.6.8`
- `kmc >=3.2.4`
- `samtools >=1.23.1`

### Python 依赖

- `click`
- `flask`
- `requests`
- `rich`
- `xxhash`
- `pyyaml`
- `pyrodigal`

## 快速开始

### 1. 浏览并下载方案

```bash
# 查看缓存中和可用的方案
gmlst scheme list

# 只看某一个 provider
gmlst scheme list -p pubmlst

# 下载方案到本地缓存
gmlst scheme download -s saureus_1
```

### 2. 对单个样本分型

```bash
# 对组装基因组做 MLST
gmlst typing mlst -s saureus_1 sample.fasta

# 对双端 reads 做 MLST
gmlst typing mlst -s saureus_1 -b minimap2 sample_R1.fastq.gz sample_R2.fastq.gz

# 对组装结果做 cgMLST
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
```

### 3. 批量处理

```bash
# 批量处理多个组装文件并输出 TSV
gmlst typing mlst -s saureus_1 --max-workers 8 samples/*.fasta -o results.tsv

# 保存 JSON，便于后续 novel 提取
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

### 4. 理解输出结果

默认输出为 TSV，风格与 `tseemann/mlst` 兼容。

```text
FILE            SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample1.fasta   saureus_1   1   1     1     1     1    1    1    1
sample2.fasta   saureus_1   -   1     ~2    3?    -    1    1    1
```

- 纯数字，表示 exact 已知等位基因匹配
- `~23`，表示非 exact 但高覆盖的调用，通常对应 closest 或 novel 倾向位点，具体可结合 identity 判断
- `15?`，表示 partial 命中，覆盖度不足
- `-`，表示该位点未找到

如果想看更适合人工阅读的输出，可使用 `--format pretty`。如果要做自动化分析，推荐使用 `--format json`。

## 比对后端

| 后端 | 是否可直接作为 CLI 后端 | FASTA | FASTQ | 适用场景 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `blastn` | 是 | 是 | 否 | 经典组装基因组 MLST | 适合做精确等位基因调用和重点复核 |
| `kma` | 是 | 是 | 是 | FASTQ 分型和 cgMLST FASTQ 路径 | 对 reads 映射型等位基因调用很实用 |
| `minimap2` | 是 | 是 | 是 | 快速组装分型和灵活的 reads 工作流 | cgMLST 优化路径中使用很多 |
| `nucmer` | 是 | 是 | 否 | 组装级敏感比对 | 适合较远距离匹配和补充证据 |

### 后端说明

- `typing mlst` 和 `typing cgmlst` 会自动识别常见双端 FASTQ 命名模式，例如 `_R1/_R2`、`_1/_2`、`.1/.2`。
- `typing cgmlst` 在 FASTA 组装输入时默认使用 `minimap2`。
- 对于 FASTQ cgMLST，CLI 采用 KMA-first 策略，chew 风格 cgMLST 模式主要面向 FASTA 场景。
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
gmlst scheme list -p pubmlst
gmlst scheme list -p enterobase -t cgmlst
gmlst scheme list -p local
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
| `standard` | 保守的基础行为 | 想先得到稳定默认行为时 |
| `chew-fast` | 结合 exact-hash 与 minimap2 预过滤，并做定向补救 | 日常组装 cgMLST |
| `chew-ultrafast` | 更激进的速度配置，带有受限第二轮补救 | 大批量样本追求更快周转 |
| `chew-bsr` | 在 `chew-fast` 基础上增加蛋白层面的精确解析 | 需要蛋白证据时 |
| `chew-balanced` | hash-first 路径加定向 `blastn` fallback | 想兼顾速度与低置信度复核 |

示例：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode standard sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-ultrafast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-bsr sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-balanced sample.fna
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

## 配置

关键环境变量：

| 变量 | 作用 |
| --- | --- |
| `GMLST_CACHE_DIR` | 覆盖默认缓存目录，通常为 `~/.cache/gmlst` |
| `GMLST_TMPDIR` | 覆盖分型与精修阶段使用的临时目录 |
| `GMLST_MINIMAP2_KMER_ENGINE` | 选择 minimap2 的 k-mer 支持评分引擎，取值为 `python`、`kmc` 或 `auto` |
| `GMLST_PUBMLST_BASE_URL` | 覆盖 PubMLST API 基础地址 |
| `GMLST_PASTEUR_BASE_URL` | 覆盖 Pasteur BIGSdb API 基础地址 |
| `GMLST_PRIVATE_BIGSDB_URL` | 注册私有 BIGSdb 实例为额外 provider |
| `GMLST_PRIVATE_BIGSDB_NAME` | 私有 BIGSdb provider 的名称 |
| `GMLST_PRIVATE_BIGSDB_LABEL` | 私有 BIGSdb provider 的显示标签 |

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

| 标记 | 含义 |
| --- | --- |
| `23` | exact 等位基因调用 |
| `~23` | 非 exact 但高覆盖的调用，可表示 closest 命中或 novel 倾向位点 |
| `15?` | partial 调用，覆盖度低于置信阈值 |
| `-` | 位点缺失 |

如果要保留结构化字段，例如每个位点的调用元数据和 `novel_sequence` 信息，建议使用 JSON 输出。

## 多拷贝位点说明

- 冲突性的多拷贝调用会以 `1,2` 这种逗号格式表示。
- 一旦存在冲突性多拷贝位点，ST 会输出为 `-`，避免过度自信的 profile 判定。
- 像 `1,1` 这样的同等位基因拷贝计数是可选功能，目前可通过 `blastn` 工作流中的 `--count-same-copy` 启用。

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
- [docs/installation.md](docs/installation.md) 查看安装说明
- [docs/quickstart.md](docs/quickstart.md) 查看快速上手指南
- [docs/commands.md](docs/commands.md) 查看 CLI 命令参考
- [README.md](README.md) 返回英文根文档

## 许可证

项目基于 [MIT License](LICENSE) 发布。

## 致谢

- 项目思路受到 [tseemann/mlst](https://github.com/tseemann/mlst) 启发
- 公共方案数据来源于 [PubMLST](https://pubmlst.org/)
