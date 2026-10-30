# 分型问题

ST 缺失、断裂基因、多拷贝等位基因、locus 缺失、FASTQ 配对，以及 cgMLST 模式选择。

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

### 一个基因被断在两个 contig 之间会怎样？

使用 `blastn` 和 `minimap2` 后端时，gmlst 会对断裂位点的逐 contig 片段比对做联合拼接。
在基因内部重叠且重叠区序列一致的 contigs 会被平铺重构为一条完整比对，可产生 exact 调用；
仅仅是首尾相接（无重叠）的 contigs 无法证明接合区，因此该位点保持 `?` 部分调用 —
但其报告的覆盖度是全部片段的联合覆盖度，且 JSON 输出会列出每个片段
（`contig`、`allele_start`、`allele_end`）。拼接绝不会跨越未采样缺口伪造 exact 调用。
所需最小重叠可用 `--min-join-overlap` 调整（默认 10 bp）。对于频繁干净断裂基因的组装，
回到原始 reads 用 `-b kma` 分型仍是最稳妥的路径 — 读段级共识可由大量重叠读段重构等位基因。

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

更多建议见下方的[性能优化建议](performance.zh.md#性能优化建议)。

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

这是预期设计。对于 FASTQ 输入，CLI 会执行 KMA-first 策略。如果你在 cgMLST FASTQ 场景里请求 `-b minimap2`，`gmlst` 会自动切到 `kma`，并把 `--cgmlst-mode` 当成兼容参数处理，也就是等效为 `fast`。

这个行为在 [分型流水线](../architecture/typing-pipeline.zh.md) 和 [CLI 参考](../usage/cli/index.zh.md) 里都有说明。

### cgMLST 模式应该怎么选？

可以从这些起点开始：

- `fast`，适合常见 FASTA cgMLST 场景
- `ultrafast`，适合更大的 FASTA 批量任务
- `balanced`，适合想保留更多 fallback 复核时

示例：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode ultrafast sample.fna
```

### 大型 cgMLST 方案运行特别慢

对大方案来说，适当提高线程数通常会更好，尤其是 KMA。

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 16 sample.fna
```

## 读懂结果行

```text
FILE        SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample.fna  saureus_1   1   1     1     1     1    1    1    1
sample2.fna saureus_1   -   1     ~2    3?    -    1    1    1
```

- `ST = -` 且出现 `~2`、`3?`，说明目前还没有精确 profile。
- 单个 `-` 通常是组装断裂，而不是方案选错。
- 很多 locus 同时出现 `-`，通常意味着方案或物种不对。

## 何时换后端重跑

| 情况 | 尝试 |
| --- | --- |
| 断裂组装上的 MLST 出现部分调用 | 对原始 reads 用 `-b kma` |
| cgMLST FASTA 出现大量 `~` | `--cgmlst-mode balanced` 或 `-b blastn` |
| 疑似旁系同源/多拷贝 | `-b blastn --count-same-copy` |
| 方案很大、时间有限 | 跨样本使用 `--max-workers` |

## 区分“方案选错”和“组装质量差”

```bash
# 1. 方案是否正确？
gmlst scheme show -s saureus_1

# 2. locus 情况如何？
gmlst typing mlst -s saureus_1 --format json sample.fna -o out.json

# 3. reads 是否优于组装？
gmlst typing mlst -s saureus_1 -b kma sample_R1.fq.gz sample_R2.fq.gz
```

如果 reads 能找回 locus 而组装不能，问题在组装断裂；如果两者都缺同样的 locus，
则应重新检查方案或物种。
