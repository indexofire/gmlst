# 配置参考

`gmlst` 的配置主要分三类，CLI 参数、环境变量、本地缓存。实际使用时，像后端、方案、线程数、输出路径这类单次运行参数，更适合放在 CLI 里。像后端调优、提供方接口地址覆盖、临时文件目录这类跨多次运行都想复用的设置，更适合用环境变量。缓存则负责保存已下载方案和已构建索引，方便重复运行。

本页只记录当前代码中真实实现的配置项。如果你想修改缓存根目录，请使用相关命令的 `--cache-dir`。旧版 README 提到过 `GMLST_CACHE_DIR`，但当前 Python 代码并没有实现这个环境变量。

## 配置模型概览

### CLI 参数

常见示例：

```bash
# 为单次运行选择方案、后端和线程数
gmlst typing mlst -s saureus_1 -b blastn -t 8 sample.fasta

# 仅对当前命令覆盖缓存目录
gmlst scheme list --cache-dir /data/gmlst-cache

# 提高样本级并行度
gmlst typing cgmlst -s vparahaemolyticus_3 --max-workers 4 samples/*.fasta
```

### 环境变量

环境变量适合定义你想在一个 shell 会话里反复复用的默认行为。

```bash
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast
export GMLST_TMPDIR=/scratch/gmlst-tmp
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta
```

### 缓存

缓存中会保存已下载的方案、目录缓存以及后端索引。只要方案和索引已经准备好，常规分型流程就可以在离线状态下重复运行。只有刷新目录、下载新方案这类操作仍然需要联网。

## 环境变量

### 通用

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_TMPDIR` | system temp directory | 覆盖临时文件根目录，目录不存在时会自动创建。适合把大型 FASTQ 验证过程中的临时文件放到更快的 scratch 盘。 | 通用运行时、minimap2 FASTQ 定向验证、输出路径驱动的临时目录处理 |

### 缓存

当前没有已实现的缓存根目录环境变量。如果你要改缓存位置，请在 `scheme`、`typing`、`utils` 等命令中使用 `--cache-dir`。

### BLASTN

当前没有实现专门的 BLASTN 环境变量。BLASTN 主要通过 `-b blastn` 和 `-t/--threads` 这类 CLI 参数控制。

### KMA

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` | `8` | 对 FASTQ cgMLST，如果原本线程数只有 `1`，会自动把每个样本的 KMA 线程提升到更合理的值，并受 CPU 数量限制。设为 `1` 可关闭自动提升。 | `typing cgmlst` 运行时规范化 |
| `GMLST_CGMLST_KMA_FASTQ_MEM_MODE` | `1` | 为 FASTQ cgMLST 启用 KMA `-mem_mode`。这是更快但较宽松的第一遍。 | FASTQ cgMLST with KMA |
| `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI` | `64` | 在 `-mem_mode` 之后，最多对这么多个 `closest` 位点再用严格 KMA 复查，以恢复 `exact` 调用。设为 `0` 可关闭。 | FASTQ cgMLST with KMA |

### minimap2

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_MINIMAP2_KMER_ENGINE` | `python` | minimap2 FASTQ 分型的 k-mer 支持打分引擎。可选值：`python`、`kmc`、`auto`。 | minimap2 FASTQ |
| `GMLST_MINIMAP2_FASTA_SPEED_PROFILE` | `default` | minimap2 FASTA 路径的速度档位。可选值：`default`、`fast`、`ultrafast`。 | minimap2 FASTA、cgMLST FASTA 流程 |
| `GMLST_MINIMAP2_FASTA_EMIT_CIGAR` | `1` | 在 minimap2 的 FASTA 组装比对中输出 CIGAR。设为 `0` 可以减少速度导向流程中的额外工作。 | minimap2 FASTA |
| `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER` | `0` | 在 minimap2 主比对前启用哈希优先的候选缩减。 | cgMLST FASTA、minimap2 prefilter 路径 |
| `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` | `0` | 在工作流模式没有覆盖时，控制送入 minimap2 精修阶段的缺失位点上限。`0` 表示关闭。 | cgMLST FASTA、minimap2 refinement |
| `GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N` | `0` | 限制哈希阶段保留下来的位点数量。`0` 表示保持默认行为。 | cgMLST FASTA、minimap2 prefilter 路径 |
| `GMLST_CGMLST_MINIMAP2_BSR_CONFIRM_MAX_LOCI` | `0` | 控制 `chew-bsr` 风格流程中的额外严格确认范围。`0` 表示关闭。 | cgMLST FASTA、minimap2 chew-bsr 路径 |
| `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI` | `adaptive` | ultrafast 第二遍的预算。可用 `adaptive`、`auto`、空值，或者非负整数。 | cgMLST FASTA、minimap2 chew-ultrafast 路径 |
| `GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT` | `0` | 在偏重速度的流程中，只对代表序列执行主比对。 | cgMLST FASTA、minimap2 representative alignment 路径 |

### nucmer

当前没有实现专门的 nucmer 环境变量。通过 `-b nucmer` 选择该后端即可。

### cgMLST 工作流

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CGMLST_PREFILTER_MAX_LOCI` | `3000` | cgMLST 预过滤自动跳过阈值。如果方案位点数超过这个值，系统可以自动跳过预过滤。设为 `0` 表示关闭这个阈值。 | cgMLST prefilter 控制 |
| `GMLST_CGMLST_EXACT_HASH_PREFILTER` | `0` | 在比对前启用 chew 风格的 DNA 精确匹配预判。 | cgMLST FASTA exact-hash 路径 |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND` | `none` | 对低置信度位点使用定向回退后端。可选值：`none`、`blastn`、`kma`、`nucmer`。 | cgMLST evidence fallback |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI` | `300` | 限制能被送去回退确认的位点数量。`0` 表示不显式限制。 | cgMLST evidence fallback |

### CDS 预测

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CGMLST_CDS_PREDICTION_MODE` | `single` | Pyrodigal CDS 模式。可选值：`single`、`meta`。 | cgMLST exact-hash 和 chew 风格 CDS 感知流程 |
| `GMLST_CGMLST_CDS_TRAINING_FILE` | unset | 固定 Pyrodigal 训练文件路径。如果未设置且模式为 `single`，gmlst 可以在 exact-hash 流程中自动创建并复用训练文件。 | cgMLST CDS prediction |
| `GMLST_CGMLST_CDS_CLOSED_ENDS` | `0` | 设为真值，例如 `1`、`true`、`yes`、`on` 时，启用 Pyrodigal closed-end 预测行为。 | cgMLST CDS prediction |
| `GMLST_CGMLST_CDS_COORDINATES_OUT` | unset | 把预测得到的 CDS 坐标写到 TSV 文件。作用类似 `--cds-coordinates-out`，但通过环境变量全局生效。 | cgMLST CDS 坐标导出 |

### 提供方

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_PUBMLST_BASE_URL` | `https://rest.pubmlst.org/db` | 覆盖 PubMLST BIGSdb API 根地址，适合镜像或测试实例。 | `scheme list`、`scheme show`、`scheme download`、`scheme update` |
| `GMLST_PASTEUR_BASE_URL` | `https://bigsdb.pasteur.fr/api/db` | 覆盖 Pasteur BIGSdb API 根地址。 | `scheme list`、`scheme show`、`scheme download`、`scheme update` |
| `GMLST_PRIVATE_BIGSDB_URL` | unset | 启动时注册一个额外的私有 BIGSdb 提供方。 | 提供方注册、scheme 命令 |
| `GMLST_PRIVATE_BIGSDB_NAME` | `private` | 私有 BIGSdb 的提供方键名。像 `all`、`local` 这类保留名称会被自动规整。 | 提供方注册 |
| `GMLST_PRIVATE_BIGSDB_LABEL` | `Private BIGSdb` | 私有 BIGSdb 提供方的人类可读标签。 | 提供方注册 |

## 缓存配置

### 默认缓存布局

默认缓存根目录：

```text
~/.cache/gmlst/
```

典型结构：

```text
~/.cache/gmlst/
├── pubmlst/
│   └── saureus_1/
│       ├── *.tfa
│       ├── saureus_1.txt
│       └── .meta.json
├── pasteur/
├── enterobase/
├── cgmlst/
├── local/
│   └── custom_1/
│       ├── *.tfa
│       ├── custom_1.txt
│       └── .meta.json
├── _catalog/
│   ├── pubmlst.json
│   └── pasteur.json
└── _indexes/
    └── pubmlst/
        └── blastn/
            └── saureus_1/
```

### 覆盖缓存位置

当你需要改缓存目录时，请使用 `--cache-dir`。

```bash
gmlst scheme list --cache-dir /data/gmlst-cache
gmlst scheme download -s saureus_1 --cache-dir /data/gmlst-cache
gmlst typing mlst -s saureus_1 --cache-dir /data/gmlst-cache sample.fasta
```

### 离线使用

- 已缓存的方案和索引可以支持重复分型，不需要再次下载。
- `scheme list` 可以读取本地目录缓存。
- `scheme update` 和下载新方案仍然需要网络。

## Provider Endpoints

### 内置默认地址

| Provider | Default URL |
| --- | --- |
| PubMLST | `https://rest.pubmlst.org/db` |
| Pasteur BIGSdb | `https://bigsdb.pasteur.fr/api/db` |

### 自建 BIGSdb 示例

```bash
export GMLST_PUBMLST_BASE_URL="http://127.0.0.1:8000/api/db"
gmlst scheme list -p pubmlst
```

### 私有提供方示例

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"

gmlst scheme list -p labdb
gmlst scheme update -s saureus_1 --cache-dir /data/gmlst-cache
```

## CLI 参数和环境变量怎么选

如果一个设置只属于某一次命令，优先用 CLI 参数。如果一个设置想在多个运行之间重复生效，优先用环境变量。

| 更适合 CLI 参数的情况 | 更适合环境变量的情况 |
| --- | --- |
| 本次运行要选方案、后端、输出路径、线程数 | 想把临时目录、提供方地址、minimap2 或 KMA 调优作为默认值 |
| 这一次命令需要单独指定 `--cache-dir` | 想在很多次运行中统一使用某个 speed profile 或 fallback backend |
| 你正在并排比较不同流程 | 你正在维护一个稳定的批处理环境 |

示例：

```bash
# 适合 CLI，单次运行参数
gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 -t 16 sample.fasta

# 适合环境变量，会话级默认值
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=fast
export GMLST_TMPDIR=/scratch/gmlst
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta
```

## 配置示例

### 使用 minimap2 ultrafast 处理大型 cgMLST

```bash
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast
export GMLST_CGMLST_EXACT_HASH_PREFILTER=1
export GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1
export GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=adaptive

gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode chew-ultrafast -t 16 samples/*.fasta -o cgmlst.tsv
```

### 使用 KMA 处理 FASTQ cgMLST

```bash
export GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=8
export GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1
export GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI=64

gmlst typing cgmlst -s vparahaemolyticus_3 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### 自建 BIGSdb

```bash
export GMLST_PUBMLST_BASE_URL="http://bigsdb.local/api/db"
gmlst scheme list -p pubmlst
gmlst scheme download -s saureus_1
```

### 自定义临时目录

```bash
export GMLST_TMPDIR=/scratch/gmlst-tmp
gmlst typing mlst -s saureus_1 -b minimap2 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### 使用 minimap2 加回退确认做性能调优

```bash
export GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=blastn
export GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=120
export GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI=500

gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode chew-fast -t 12 sample.fasta
```
