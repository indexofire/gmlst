# 后端对比指南

`gmlst` 提供多个比对后端，因为 MLST 和 cgMLST 的工作负载并不相同。有的场景更看重组装基因组上的最高置信度，有的场景需要直接处理 FASTQ 原始读段，还有的场景追求超大方案上的最高吞吐量。选什么后端，主要取决于输入类型、方案规模，以及你更在意灵敏度、速度还是读段映射行为。

可以先按这个思路选。组装基因组想走经典参考路径，用 `blastn`。FASTQ 分型想要稳妥的常规后端，用 `kma`。大规模 cgMLST 追求速度，用 `minimap2`。如果样本和等位基因差异较大，或者是非标准物种，用 `nucmer`。

## 后端对比表

| 名称 | 输入类型 | 速度 | 灵敏度 | 最适合的场景 | 外部工具 |
| --- | --- | --- | --- | --- | --- |
| `blastn` | FASTA | 中等 | 最高 | 参考型 MLST、结果验证、组装基因组 | `blastn`, `makeblastdb` |
| `kma` | FASTA, FASTQ | 快 | 高 | FASTQ 分型、常规 MLST、基于读段的 cgMLST | `kma` |
| `minimap2` | FASTA, FASTQ | 很快 | 高 | 大型 cgMLST、高通量分型、快速 FASTA 流程 | `minimap2`（某些 FASTQ 临时输出在可用时会配合 `samtools`） |
| `nucmer` | FASTA | 中等 | 对远缘序列非常高 | 远缘菌株、跨物种比对、分歧较大的等位基因 | `nucmer`, `show-coords` |

## 如何选择

| 场景 | 推荐后端 | 原因 |
| --- | --- | --- |
| 小规模或常规组装基因组 MLST | `blastn` | 经典路径，置信度高，行为直观 |
| FASTQ MLST 或 FASTQ cgMLST | `kma` | 直接支持双端读段，读段映射流程成熟 |
| 大型 FASTA cgMLST | `minimap2` | 吞吐量最高，还有多种加速机制 |
| 想在 FASTQ 上先快速筛选，再做定点确认 | `minimap2` | 两阶段 FASTQ 路径兼顾速度和确认 |
| 序列差异较大或非标准物种 | `nucmer` | 对远缘匹配更敏感 |
| 快速跑完后再做复核 | `blastn` | 很适合作为第二遍确认后端 |

## BLASTN (`blastn`)

`blastn` 是组装基因组场景下最稳妥的参考后端。它只接受 FASTA 输入，使用 BLAST+ 数据库流程，因此很适合做基准分型、结果复核，或者作为其他快速后端的对照。

### 适用场景

- 组装基因组上的参考型 MLST
- 快速流程后的验证
- 更看重灵敏度而不是极致速度的任务
- 边界等位基因调用，需要经典比对路径复核的样本

### 示例命令

```bash
# 组装基因组上的标准 MLST
gmlst typing mlst -s saureus_1 -b blastn sample.fasta

# 多线程批量分型
gmlst typing mlst -s saureus_1 -b blastn -t 8 samples/*.fasta -o results.tsv

# 对标记样本做定向 cgMLST 复核
gmlst typing cgmlst -s vparahaemolyticus_3 -b blastn flagged_sample.fasta
```

### 说明

- 输入类型：仅 FASTA
- 建索引工具：`makeblastdb`
- 线程支持：支持 `-t/--threads`
- 最适合：组装基因组上的高置信度分型

### 性能建议

- 方案较大时建议使用 `-t`。
- 批量运行时建议配合 `-o` 直接写文件。
- 对大型 cgMLST 来说，`blastn` 更适合作为回退后端或复核后端，而不是所有样本的第一遍主流程。

## KMA (`kma`)

`kma` 是 FASTQ 分型最实用的通用后端。它既支持 FASTA，也支持 FASTQ，但真正的优势在于直接处理读段、双端输入，以及日常生产环境中的稳定表现。

### 适用场景

- FASTQ MLST 或 cgMLST
- 需要直接处理双端读段的样本
- 重视速度与稳定映射行为的常规流程
- 更偏好 KMA 行为而不是 minimap2 候选打分路径的 cgMLST 任务

### 示例命令

```bash
# 双端读段 MLST
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz

# FASTQ cgMLST
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz

# 用 KMA 处理 FASTA
gmlst typing mlst -s saureus_1 -b kma sample.fasta
```

### FASTQ 行为

- `gmlst` 会自动识别常见的双端命名，例如 `_R1/_R2`、`_1/_2`、`.1/.2`。
- 对 FASTQ cgMLST，CLI 可以通过 `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` 自动把线程数从 `1` 提高到更合理的值。
- `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1` 会启用 KMA 的 `-mem_mode`，让第一遍映射更快。
- `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI` 控制后续严格复查阶段，最多对若干个 `closest` 位点重新确认。

### 说明

- 输入类型：FASTA 和 FASTQ
- 建索引工具：KMA index
- 线程支持：支持 `-t/--threads`
- 最适合：FASTQ cgMLST 和基于读段的常规分型

### 性能建议

- 大型 cgMLST 不要长期使用 `-t 1`，速度会明显下降。
- 想要日常 FASTQ 流程更快，可以保留 `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1`。
- 如果更看重严格确认，可以调大 `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI`。

## minimap2 (`minimap2`)

`minimap2` 是大规模 cgMLST 的高吞吐后端。它同时支持 FASTA 和 FASTQ，但两种输入走的是不同路径。

对 FASTA 组装结果，`gmlst` 会使用快速的等位基因到基因组路径，并可叠加精确哈希预判、代表序列预过滤、自适应补救和速度档位。对 FASTQ 读段，则使用两阶段流程，先生成候选，再对不确定位点做定向重映射验证。

### 适用场景

- 大型 FASTA cgMLST
- 高通量批处理
- 需要快速候选筛选加定向确认的 FASTQ 分型
- 想使用 chewBBACA 风格 cgMLST 模式的 FASTA 工作流

### 示例命令

```bash
# FASTA cgMLST，默认后端就是 minimap2
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta

# 显式指定 minimap2，并使用 chew 兼容模式
gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode fast sample.fasta

# FASTQ 分型，使用 minimap2 候选生成加定向验证
gmlst typing mlst -s saureus_1 -b minimap2 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz

# 面向大规模 cgMLST 的 ultrafast 调优
GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast \
gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode ultrafast samples/*.fasta -o cgmlst.tsv
```

### FASTA 路径

大部分 minimap2 的 cgMLST 加速都发生在 FASTA 路径上。

- `GMLST_MINIMAP2_FASTA_SPEED_PROFILE=default|fast|ultrafast` 控制 minimap2 的速度档位。
- `GMLST_CGMLST_EXACT_HASH_PREFILTER=1` 启用 DNA 精确匹配预判。
- `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1` 启用哈希优先的候选缩减。
- `GMLST_CGMLST_PREFILTER_MAX_LOCI` 控制方案过大时是否自动跳过预过滤。
- `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` 控制缺失位点的二次精修上限。
- `GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N` 控制哈希阶段保留的位点数量。
- `GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT=1` 启用代表序列主比对，适合极致速度模式。
- `GMLST_MINIMAP2_FASTA_EMIT_CIGAR=0` 可关闭 FASTA CIGAR 输出，减少速度导向路径中的额外开销。

### FASTQ 路径

FASTQ 路径分两步。

1. 根据读段比对结果生成候选，并做 k-mer 支持打分。
2. 对不确定位点执行定向重映射验证，再输出最终等位基因调用。

相关参数：

- `GMLST_MINIMAP2_KMER_ENGINE=python|kmc|auto`，控制 k-mer 支持打分引擎。
- `auto` 会在 KMC 可用时优先使用 KMC，否则退回内置 Python 打分器。
- 如果系统安装了 `samtools`，定向验证阶段可以写出 BAM 临时文件。
- `GMLST_TMPDIR` 用来控制临时文件目录。

### chewBBACA 兼容模式

`typing cgmlst` 支持下列模式值：

| 模式 | 常见用途 |
| --- | --- |
| `fast` | 更快的 chew 风格流程，包含 exact-hash、hash prefilter、refinement 和 fallback |
| `ultrafast` | 面向 FASTA 的最高吞吐模式，带代表序列主比对和二次补救 |
| `balanced` | 在速度和确认之间取中间值 |

要注意，这些 chew 风格优化主要针对 FASTA。对于 FASTQ 输入，`typing cgmlst` 会自动把 `-b minimap2` 调整为 `-b kma`，`--cgmlst-mode` 只保留兼容意义。

### 证据回退

低置信度位点可以发送到指定回退后端进一步确认。

- `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=none|blastn|kma|nucmer`
- `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=<int>`

这个机制很适合让 minimap2 负责主流程吞吐，再让少量不确定位点交给更保守的后端确认。

## MUMmer4 / nucmer (`nucmer`)

`nucmer` 是面向 FASTA 组装结果的高敏感后端，特别适合序列分歧较大的情况。对于非标准物种、远缘样本、或者跨物种探索分析，这个后端通常比常规 MLST 场景更有价值。

### 适用场景

- 差异较大的组装基因组
- 非标准物种或探索性分析
- 关注敏感匹配而不是经典参考行为的跨物种比较

### 示例命令

```bash
# 对分歧较大的组装结果做敏感 MLST
gmlst typing mlst -s saureus_1 -b nucmer sample.fasta

# 对困难样本做 cgMLST 复核
gmlst typing cgmlst -s vparahaemolyticus_3 -b nucmer flagged_sample.fasta
```

### 说明

- 输入类型：仅 FASTA
- 建索引工具：nucmer reference index 流程
- 线程支持：相对有限，`gmlst` 也会提示线程设置可能被忽略
- 最适合：分歧较大序列的敏感回退分析

## 后端选择建议

### 快速决策表

| 你的输入或需求 | 推荐后端 | 原因 |
| --- | --- | --- |
| 组装基因组，想要最终参考结果 | `blastn` | 经典路径，置信度高 |
| 双端 FASTQ 读段 | `kma` | 直接读段映射，日常流程表现稳 |
| 数千位点的 FASTA cgMLST | `minimap2` | 吞吐量最好，加速机制丰富 |
| 分歧较大的组装结果 | `nucmer` | 对远缘等位基因更敏感 |
| 先快跑一遍，再对少量样本确认 | `minimap2` 或 `kma`，之后用 `blastn` | 先抓吞吐，再做保守复核 |

### 简单决策流程

1. 输入是 FASTQ 吗？
   - 是，优先从 `kma` 开始。
   - 如果是 MLST，而且你明确想用 minimap2 的 FASTQ 验证路径，也可以用 `minimap2`。
   - 如果是 cgMLST FASTQ，CLI 仍会倾向规范到 KMA。
2. 输入是 FASTA 组装结果吗？
   - 追求大型 cgMLST 吞吐量，用 `minimap2`。
   - 想走保守参考路径，用 `blastn`。
   - 如果物种或等位基因差异明显偏大，优先试 `nucmer`。

## 性能建议

- 方案大或样本多时，给 BLASTN、KMA、minimap2 设置 `-t/--threads`。
- 批量处理很多样本时，用 `--max-workers` 做样本级并行。
- 大型 FASTA cgMLST 可以先用 `minimap2` 跑主流程，只对标记位点或标记样本做回退确认。
- FASTQ cgMLST 配合 KMA 时，除非在调试，否则尽量不要长期使用单线程。
- 大批量任务建议用 `-o` 把输出直接写到文件，而不是全部打到终端。
- 重复任务尽量复用已缓存的方案和索引，第一次建索引会慢一些，之后会轻很多。
- 临时空间较慢或较小的时候，可以用 `GMLST_TMPDIR` 把临时文件放到更合适的位置。

## FASTQ 专题说明

### 双端自动识别

`gmlst` 会自动识别常见的双端 FASTQ 命名：

- `sample_R1.fastq.gz` + `sample_R2.fastq.gz`
- `sample_1.fq.gz` + `sample_2.fq.gz`
- `sample.1.fastq.gz` + `sample.2.fastq.gz`

示例：

```bash
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### k-mer 支持打分

对于 minimap2 FASTQ 分型，`GMLST_MINIMAP2_KMER_ENGINE` 控制打分引擎：

- `python`，内置打分器
- `kmc`，使用 KMC/KMC tools
- `auto`，优先使用 KMC，否则回退 Python

### 定向验证

minimap2 的 FASTQ 模式不是单次映射就结束。它会先构建候选等位基因，再做支持打分，然后对不确定位点做定向重映射验证。所以它适合想要高速筛选，同时又不想完全放弃后续确认的场景。

## 相关调用类型

虽然不同后端的取证路径不同，但最终每个位点的调用都会落到同一套五类结果中：

| 调用类型 | 判定规则 |
| --- | --- |
| `exact` | identity `100%`，coverage `>= 1.0` |
| `closest` | identity `>= 95%`，coverage `>= 0.95` |
| `novel` | coverage `>= 0.95`，identity `< 95%` |
| `partial` | coverage `> 0` 且 `< 0.95` |
| `missing` | 没有匹配 |
