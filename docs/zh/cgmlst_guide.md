# cgMLST 指南

本文介绍 `gmlst typing cgmlst` 的使用方法，包括模式选择、FASTA 与 FASTQ 行为、预过滤、CDS 预测、调用策略以及性能调优。完整命令请参见 [commands.md](commands.md)，更底层的实现说明可参考 [../en/architecture.md](../en/architecture.md)。

## 概述

cgMLST 可以看作是经典 MLST 的扩展：它不再只关注少数 housekeeping genes，而是覆盖核心基因组中的大量 loci，因此更适合暴发调查、监测和高分辨率比较。

可以简单理解为：

- MLST 位点少、命名稳定、适合快速归类
- cgMLST 位点多、分辨率高、适合精细比较样本差异

在 `gmlst` 中，两者共用同一套 CLI，但 `typing cgmlst` 会增加针对大 scheme、CDS 感知分类和不同后端优化路径的逻辑。

## 快速开始

cgMLST 默认后端是 `minimap2`。

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
```

典型 TSV 输出形式：

```tsv
FILE	SCHEME	ST	dnaA	ftsZ	gyrB	...
sample.fna	vparahaemolyticus_3	-	12	44	109	...
```

对于很多 cgMLST scheme，`ST` 可能是 `-`。这是正常现象，因为 cgMLST 的主要价值在于整套 allele profile，而不是一个紧凑的传统 ST 编号。

## cgMLST 模式

不同模式适合不同数据规模和速度/恢复能力平衡。

### `fast`

在基础流程上增加 exact-hash、minimap2 hash prefilter、自动缺失位点 refine（默认上限 500 loci），以及定向 `blastn` 证据回退（默认上限 500 loci）。

适合场景：

- 使用 FASTA 组装序列
- 想在速度和结果恢复能力之间取得较好平衡

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode fast sample.fna
```

### `ultrafast`

在 `fast` 的基础上进一步启用 representative-only 主比对、关闭 CIGAR 输出、使用 ultrafast minimap2 配置、严格低置信度 rescue（默认 120 loci）和自适应第二轮。

适合场景：

- scheme 很大，例如 1000 个以上 loci
- 优先考虑吞吐量，再用有限的第二轮修复低置信度位点

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode ultrafast sample.fna
```

### `balanced`

启用 exact-hash、minimap2 hash prefilter 和定向 `blastn` fallback，但不走最激进的 ultrafast 路线。

适合场景：

- 希望在 `fast` 与更激进的加速模式之间找到折中

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode balanced sample.fna
```

## FASTA cgMLST

FASTA 组装序列可以获得最完整的优化路径，也是 chew 风格模式真正生效的主要场景。

常见示例：

```bash
# 默认路径
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna

# 自定义 prefilter 参数
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --prefilter-k 31 \
  --prefilter-top-n 20 \
  --prefilter-min-loci-fraction 0.2 \
  sample.fna

# 显式关闭 prefilter
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --no-prefilter sample.fna

# 大 scheme 使用更快模式
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode ultrafast sample.fna
```

为什么 FASTA 选项更多：

- 组装序列更适合 exact-hash 和 CDS 感知逻辑
- minimap2 prefilter 在 contig 上更稳定
- 候选空间变小后，第二轮 rescue 成本更低

## FASTQ cgMLST

FASTQ 模式遵循 KMA-first 策略。

如果你对 FASTQ 输入指定 `-b minimap2`，`gmlst` 会自动切换到 `-b kma`。同时，chew 风格模式在 FASTQ 下只保留兼容意义，最终会被强制视为 `fast`。

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  -b minimap2 reads_R1.fastq.gz reads_R2.fastq.gz
```

实际行为是：

- 后端自动切换为 `kma`
- cgMLST mode 被当作 `fast`
- 可通过 `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` 自动提高每个样本的线程数
- `--call-policy chewbbaca` 会直接拒绝 FASTQ 输入

推荐 FASTQ 命令：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  -b kma -t 8 reads_R1.fastq.gz reads_R2.fastq.gz
```

出现这种行为的原因是：

- chew 风格优化主要围绕 FASTA 组装设计
- KMA 更适合基于 reads 的 cgMLST 映射
- 自动切换能避免用户落入不理想配置

## 预过滤（Prefiltering）

prefilter 的目的是减少后续需要完整比对或补救的 loci 数量。

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --prefilter-k 31 \
  --prefilter-top-n 20 \
  --prefilter-min-loci-fraction 0.15 \
  sample.fna
```

参数含义：

- `--prefilter-k`：prefilter 使用的 k-mer 长度
- `--prefilter-top-n`：每一步保留的候选 loci 数
- `--prefilter-min-loci-fraction`：继续使用 prefilter 所需的最小 loci 比例

重要行为：

- 超过自动跳过阈值的大 scheme 可能会直接跳过 prefilter
- 默认自动跳过阈值是 3000 loci
- 对 `-b kma` 和默认 `-b minimap2`，有时会直接使用持久化 full-index 路径而不是 prefilter

## CDS 预测

`gmlst` 在 cgMLST 的 exact-hash / chew 风格路径中使用 Pyrodigal 进行 CDS 预测。

导出预测到的 CDS 坐标：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cds-coordinates-out cds_coordinates.tsv \
  sample.fna
```

这样做的价值在于：

- 便于比较不同运行中的 coding region 预测
- 有助于调试 chewBBACA 风格分类差异
- 可以明确记录 CDS gate 实际看到的序列区域

示例坐标表：

```tsv
sample	contig	start	end	strand	locus
sample.fna	contig_1	1042	1983	+	dnaA
sample.fna	contig_1	4021	4899	-	gyrB
```

## 调用策略（Call Policy）

call policy 控制每个 locus 的结果如何被分类和输出。

### 默认策略

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy default sample.fna
```

适用于希望保留 `gmlst` 默认解释方式的场景。

### chewBBACA 兼容策略

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chewbbaca sample.fna
```

限制与特点：

- `--call-policy chewbbaca` 只支持 FASTA 组装输入
- 原始 allele call 不会改变，但输出会显示 chew 风格 per-locus class label
- 默认启用 CDS gate

### chew-exact 策略

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chew-exact sample.fna
```

`chew-exact` 为需要与 chewBBACA 数据库最大程度兼容的场景设计：

- 强制 CDS 预测为 **single 模式**（使用 scheme 的 training file）
- 强制启用 **CDS gate**（不可关闭）
- 产出全部 chewBBACA 分类类型：EXC, INF-N, LNF, NIPH, NIPHEM, LOTSC, PLOT3, PLOT5, ASM, ALM

当需要与 chewBBACA 结果的 allele 编号一致时使用 `chew-exact`。

## CDS Gate

CDS gate 用于决定 chewBBACA 风格分类是否只能基于通过 CDS 预测过滤的匹配序列上下文。

```bash
# 使用 chewbbaca 策略时的默认行为
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chewbbaca \
  --chew-cds-gate \
  sample.fna

# 放宽 gate
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chewbbaca \
  --no-chew-cds-gate \
  sample.fna
```

默认 gate 更适合严格、贴近 coding sequence 语境的分类。只有在你明确要检查低置信度或边缘案例时，才建议关闭它。

## 证据回退（Evidence Fallback）

低置信度 loci 可以根据模式和环境变量触发定向 fallback，而不是整批重跑。

支持的 fallback 后端包括：

- `blastn`
- `kma`
- `nucmer`

示例配置：

```bash
export GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=blastn
export GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=300

gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
```

## 性能调优

可以先按以下经验选择：

- 小到中等规模 FASTA scheme：先试 `fast` 或 `balanced`
- 大型 FASTA scheme：优先试 `ultrafast`
- FASTQ：优先使用 `-b kma`，线程数通常设为 `8` 到 `16`
- 批量样本：使用 `--max-workers` 进行样本级并行

示例：

```bash
# 大 scheme，偏向快速的 assembly 路径
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode ultrafast \
  --max-workers 4 \
  samples/*.fna

# FASTQ + 线程调优
gmlst typing cgmlst -s vparahaemolyticus_3 \
  -b kma -t 12 reads_R1.fastq.gz reads_R2.fastq.gz
```

运行层面的注意点：

- `--max-workers > 1` 表示启用样本级并行，此时每个样本的后端线程会降为 `1`
- `--cds-coordinates-out` 更适合单 worker 运行
- `nucmer` 不会使用线程设置

## 大型 Scheme 处理建议

对于 1000 个以上 loci 的 scheme：

- FASTA 组装优先考虑 `ultrafast`
- 规模越大，prefilter 的意义通常越明显
- 但也要注意超过阈值后可能自动跳过 prefilter
- `--max-workers` 不一定越大越快，要结合后端线程一起平衡

对于非常大的 scheme，最快的配置通常不是“worker 越多越好”，而是让样本级并行和每样本线程数达到合理平衡。

## 环境变量

下面这些环境变量会影响 cgMLST 的行为。

### FASTA 与 minimap2 相关

- `GMLST_MINIMAP2_FASTA_SPEED_PROFILE=default|fast|ultrafast`
- `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=adaptive|<int>`
- `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI=<int>`
- `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1`

### FASTQ 与 KMA 相关

- `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1|0`
- `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI=<int>`
- `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=<int>`

### Prefilter 与 exact-hash 相关

- `GMLST_CGMLST_PREFILTER_MAX_LOCI=<int>`
- `GMLST_CGMLST_EXACT_HASH_PREFILTER=1`

### CDS 预测与导出

- `GMLST_CGMLST_CDS_PREDICTION_MODE=single|meta`
- `GMLST_CGMLST_CDS_TRAINING_FILE=/path/to/pyrodigal_training.trn`
- `GMLST_CGMLST_CDS_CLOSED_ENDS=1|0`
- `GMLST_CGMLST_CDS_COORDINATES_OUT=/path/to/cds_coordinates.tsv`

### 证据回退

- `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=none|blastn|kma|nucmer`
- `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=<int>`

### 其他相关设置

- `GMLST_CACHE_DIR=/path/to/cache`
- `GMLST_TMPDIR=/path/to/tmp`
- `GMLST_MINIMAP2_KMER_ENGINE=python|kmc|auto`

### 环境变量示例

```bash
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast
export GMLST_CGMLST_PREFILTER_MAX_LOCI=3000
export GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=8
export GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=blastn

gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
```
