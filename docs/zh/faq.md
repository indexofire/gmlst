# 常见问题与故障排查

这份文档整理了 `gmlst` 的常见问题和实用排查方法。安装和首次运行流程请先看 [installation.md](installation.md) 和 [quickstart.md](quickstart.md)。命令语法请参考 [commands.md](commands.md)。

## 一般问题

### gmlst 是什么？

`gmlst` 是一个面向细菌基因组分型的 Python CLI，支持传统 MLST、更大规模的 cgMLST 和 wgMLST，以及通过 `gmlst typing tgmlst` 运行的 scheme-free 分型。

### MLST 和 cgMLST 有什么区别？

- MLST 通常只使用少量 housekeeping loci，常见是 7 个
- cgMLST 会使用更大规模的核心基因位点集合
- wgMLST 还会进一步扩展到更多 accessory loci

实际使用时，MLST 更轻量，适合快速分型。cgMLST 分辨率更高，但也更依赖计算资源和较完整的位点回收。

### 为什么 gmlst 要支持多个比对后端？

因为不同输入类型和工作负载适合的工具不同：

- `blastn` 适合 assembly 场景下的基础 MLST
- `kma` 很适合 read-based 工作流，尤其是 cgMLST FASTQ 路径
- `minimap2` 在组装和部分 reads 工作流中速度快、适应性强
- `nucmer` 可用于组装比较和补充证据

项目会把不同后端的结果统一归一化，这样下游 calling 逻辑可以保持一致。

## 安装问题

### `pixi: command not found`

说明 Pixi 还没安装，或者当前 shell 还没有加载新的 PATH。

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

然后重新打开终端，再检查：

```bash
pixi --version
```

### `Python 3.12 is required`

说明当前 Python 版本太低。

先检查版本：

```bash
python --version
python3 --version
```

如果想少踩环境坑，建议直接改用 pixi：

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi run gmlst --version
```

### `pip install gmlst` 失败

常见原因包括：

- Python 版本不是 3.12
- 构建环境不一致
- 外部工具没有安装，后续命令因此失败

可以先试一个干净虚拟环境：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install gmlst
```

如果还是环境问题较多，建议直接用 pixi。

### `blastn` not found

`blastn` 属于 BLAST+。如果你用的是 pixi，请确保命令运行在 pixi 环境里。如果你用的是 pip，需要单独安装 BLAST+。

检查命令：

```bash
gmlst utils check -b blastn
```

或者：

```bash
pixi run gmlst utils check -b blastn
```

### 安装时遇到权限错误

本地开发环境下，不建议使用 `sudo pip` 或 `sudo pixi`。请改用用户自己的环境。

更合适的方式：

- pixi 环境
- Python 虚拟环境
- conda 或 mamba 环境

## 方案管理问题

### `Scheme 'X' not found in catalog`

你传入的必须是规范的 `scheme_name`，不是单纯的物种名。

先列出可用方案：

```bash
gmlst scheme list
gmlst scheme list -p pubmlst
gmlst scheme list -p enterobase -t cgmlst
```

然后使用精确名称，例如：

```bash
gmlst scheme download -s saureus_1
```

### 下载方案失败

常见原因：

- 临时网络故障
- provider 端服务不稳定或限流
- 当前下载工具在你的环境里效果不好

可以尝试切换下载工具：

```bash
gmlst scheme download -s saureus_1 --download-tool curl
gmlst scheme download -s saureus_1 --download-tool requests
gmlst scheme download -s saureus_1 --download-tool wget
```

如果你处在代理或防火墙环境里，也要确认 provider 端地址本身可以访问。

### 缓存目录在哪里？

缓存根目录会自动检测：conda 环境使用 `$CONDA_PREFIX/share/gmlst`，virtualenv 使用 `$VIRTUAL_ENV/.cache/gmlst`，默认回退到 `~/.cache/gmlst`。每个环境拥有独立的缓存。

你也可以覆盖它：

```bash
export GMLST_CACHE_DIR="$HOME/work/gmlst-cache"
gmlst scheme list
```

如果需要在多个 conda 环境间共享缓存：

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### 我想只对单条命令改缓存路径

部分命令支持 `--cache-dir`：

```bash
gmlst scheme list --cache-dir /tmp/gmlst-cache
gmlst scheme download -s saureus_1 --cache-dir /tmp/gmlst-cache
```

### `scheme list` 里缺少某个方案

它可能被 `gmlst/data/blocked_schemes.json` 屏蔽了。

这个文件会影响 list、show、download、update 等流程。如果你是项目维护者，需要调整屏蔽策略，请谨慎编辑这个 JSON。

### 如何连接自托管 BIGSdb？

可以用环境变量指定自定义 BIGSdb 地址：

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```

内置 provider 的 base URL 也可以覆盖：

```bash
export GMLST_PUBMLST_BASE_URL="https://rest.pubmlst.org/db"
export GMLST_PASTEUR_BASE_URL="https://bigsdb.pasteur.fr/api/db"
```

## 分型问题

### ST 显示为 `-`

这表示没有找到 exact profile 匹配。常见原因有：

- 某些 loci 缺失
- 某些 loci 只有 partial 命中
- 某些 loci 是 closest 或 novel 倾向，而不是 exact
- 出现了多拷贝冲突，比如 `1,2`

下一步建议：

```bash
gmlst typing mlst -s saureus_1 --format json sample.fasta -o sample.json
gmlst typing mlst -s saureus_1 --format pretty sample.fasta
```

JSON 输出里会包含更详细的位点信息。

### 结果里出现 `1,2` 这样的 multicopy allele

这表示同一个 locus 找到了多个冲突命中，常见于重复序列、重复位点，或比对不够明确的情况。

如果你在用 assembly 加 `blastn` 复核，可以试试：

```bash
gmlst typing mlst -s saureus_1 -b blastn --count-same-copy sample.fasta
```

这样在支持的情况下可以看到 `1,1` 这类 same-copy 结果。

### 很多 loci 都是 missing

常见原因有：

- 方案选错了
- 组装质量差
- contig 过碎
- FASTQ 输入用了不支持 FASTQ 的后端

先确认方案：

```bash
gmlst scheme show -s saureus_1
gmlst scheme list -n aureus
```

然后根据输入类型选合适后端：

- FASTA：`blastn`、`minimap2`、`nucmer`、`kma`
- FASTQ：`kma` 或 `minimap2`

### 分型速度很慢

可以先试这些命令：

```bash
gmlst typing mlst -s saureus_1 --max-workers 4 samples/*.fasta -o results.tsv
gmlst typing cgmlst -s vparahaemolyticus_3 -t 8 sample.fasta
```

更多建议见下方的[性能优化建议](#性能优化建议)。

### FASTQ 输入用 `blastn` 或 `nucmer` 失败

这是预期行为。当前项目里，`blastn` 和 `nucmer` 面向 assembly 场景。FASTQ 请改用 `kma` 或 `minimap2`。

例如：

```bash
gmlst typing mlst -s saureus_1 -b kma reads_R1.fastq.gz reads_R2.fastq.gz
gmlst typing mlst -s saureus_1 -b minimap2 reads_R1.fastq.gz reads_R2.fastq.gz
```

## FASTQ 相关问题

### 双端 FASTQ 是怎么识别的？

`gmlst` 会识别这些常见命名模式：

- `_R1` 和 `_R2`
- `_1` 和 `_2`
- `.1` 和 `.2`

支持的扩展名包括 `.fastq`、`.fq` 和 `.gz` 变体。

### 我的 FASTQ 没有被识别成一对

请尽量改成标准命名，或者按顺序显式传入成对文件。

例如：

```bash
gmlst typing mlst -s saureus_1 -b kma sample_R1.fastq.gz sample_R2.fastq.gz
```

### 哪些后端支持 FASTQ？

- 支持：`kma`、`minimap2`
- 当前不支持 FASTQ 分型：`blastn`、`nucmer`

## cgMLST 相关问题

### 为什么 `typing cgmlst` 会把我的 FASTQ 任务切到 KMA？

这是预期设计。对于 FASTQ 输入，CLI 会执行 KMA-first 策略。如果你在 cgMLST FASTQ 场景里请求 `-b minimap2`，`gmlst` 会自动切到 `kma`，并把 `--cgmlst-mode` 当成兼容参数处理，也就是等效为 `standard`。

这个行为在 [../en/architecture.md](../en/architecture.md) 和 [commands.md](commands.md) 里都有说明。

### cgMLST 模式应该怎么选？

可以从这些起点开始：

- `standard`，适合想要最保守默认行为时
- `chew-fast`，适合常见 FASTA cgMLST 场景
- `chew-ultrafast`，适合更大的 FASTA 批量任务
- `chew-balanced`，适合想保留更多 fallback 复核时

示例：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode standard sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-ultrafast sample.fna
```

### 大型 cgMLST 方案运行特别慢

对大方案来说，适当提高线程数通常会更好，尤其是 KMA。

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 16 sample.fna
```

## 输出问题

### TSV 中的标记是什么意思？

- `23`，exact allele call
- `~23`，closest 或非 exact 的高覆盖调用
- `15?`，partial call
- `-`，missing locus

### 我该用 JSON 还是 TSV？

如果你想要紧凑表格，选 TSV。如果你需要更完整的结构化信息，比如每个位点的详细元数据和 `novel_sequence`，选 JSON。

例如：

```bash
gmlst typing mlst -s saureus_1 --format tsv sample.fasta -o result.tsv
gmlst typing mlst -s saureus_1 --format json sample.fasta -o result.json
```

### GrapeTree 导出失败怎么办？

GrapeTree 导出面向公共方案，或通过 `gmlst scheme create` 构建的 custom scheme。如果失败，请先确认当前方案确实是下载得到的公共方案，或是按标准流程建立的自定义方案。

例如：

```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection"
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

## 配置问题

### 哪些环境变量最常用？

最常见的是：

- `GMLST_CACHE_DIR`，覆盖缓存根目录（默认从 conda/venv 自动检测）
- `GMLST_TMPDIR`，覆盖临时目录
- `GMLST_MINIMAP2_KMER_ENGINE`，可选 `python`、`kmc`、`auto`
- 各种 provider URL 覆盖变量，例如 `GMLST_PUBMLST_BASE_URL`

示例：

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
export GMLST_MINIMAP2_KMER_ENGINE=auto
```

### 临时文件写到哪里？

默认写到系统临时目录。你可以这样覆盖：

```bash
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

## 性能优化建议

### 哪个后端通常最快？

没有一个答案适合所有场景，但可以从下面这些经验开始：

- assembly MLST，先试 `blastn` 或 `minimap2`
- FASTQ 分型，先试 `kma`
- FASTA cgMLST，先试 `minimap2` 配合合适的 chew 风格模式
- 大型 FASTQ cgMLST，预期会走 KMA-first 路径

### 线程应该怎么调？

很多独立样本时，优先考虑样本级并行。单样本很重时，再加后端线程。

例如：

```bash
gmlst typing mlst -s saureus_1 --max-workers 8 samples/*.fasta -o results.tsv
gmlst typing cgmlst -s vparahaemolyticus_3 -t 8 sample.fna
```

### 是否建议分批处理？

建议，尤其是样本很多时。缓存和索引复用，是最容易获得性能收益的方式之一。

## 常见错误信息

### `Unknown backend 'X'`

说明你请求的 backend 没有注册到 `gmlst/aligners/__init__.py`。可以先查看支持的后端名称：

```bash
gmlst typing mlst --help
gmlst utils check -b blastn
```

### `Unknown provider 'X'`

说明 provider 没有注册到 `gmlst/database/providers/__init__.py`。

可以先用下面的命令查看可用 provider：

```bash
gmlst scheme list
```

### `No typing result produced for input sample`

通常表示在组装出有效结果前就失败了。请重点检查输入格式、后端兼容性、方案是否可用，以及失败前的命令输出。

### `Failed to download` 相关错误

这类错误通常指向网络问题，或 provider 端问题。可以先换一个 `--download-tool` 重试，再确认远端地址是否能访问。

### `--verbose and --quiet cannot be used together`

这两个参数互斥，只能选一个：

```bash
gmlst --verbose scheme list
gmlst --quiet scheme list
```

## 还是没有解决？

如果你要提 issue 或反馈问题，建议附上这些信息：

- 你执行的完整命令
- 安装方式，pixi 还是 pip
- 输入类型，FASTA 还是 FASTQ
- backend 名称
- scheme 名称
- 相关 stderr 输出
- 用 `--format json` 是否还能复现

这样更容易复现问题，也更容易定位原因。
