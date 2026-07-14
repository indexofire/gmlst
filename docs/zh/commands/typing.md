[← 命令参考](../commands.md)

# gmlst typing

用于按已知方案或 scheme-free 流程对 FASTA、FASTQ 样本进行分型。

## mlst

对样本执行经典 MLST 分型。

### 用法
```bash
gmlst typing mlst [OPTIONS] SAMPLES...
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定 MLST 方案名称，例如 `saureus_1`、`ecoli_1`。 | 必填 |
| `-b, --backend [blastn\|kma\|minimap2\|nucmer]` | 选择比对后端。 | `blastn` |
| `--min-id FLOAT` | 最小百分比 identity。 | `95.0` |
| `--min-cov FLOAT` | 最小 allele 覆盖度，范围 0 到 1。 | `0.95` |
| `--min-depth FLOAT` | 最小 read depth，仅用于 FASTQ。 | `10.0` |
| `--format [tsv\|json\|pretty]` | 输出格式。 | `tsv` |
| `-o, --output PATH` | 把结果写入文件。 | 无 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |
| `--force-reindex` | 重建后端索引。 | 关闭 |
| `--no-header` | 不输出 TSV 表头。 | 关闭 |
| `-t, --threads INTEGER` | 后端使用的线程数。 | `1` |
| `--max-workers INTEGER` | 样本级并行 worker 数。 | `1` |
| `--count-same-copy` | 统计同 allele 的 multicopy 命中，目前主要用于 `blastn`，并显示 `1,1` 这类记法。 | 关闭 |
| `-q, --quiet` | 仅保留错误输出。 | 关闭 |
| `--novel-allele` | 把 novel allele 序列写入 `{locus}_novel.fasta`。 | 关闭 |
| `--novel-profile` | 把 novel ST profile 写入 `profiles_novel.txt`，需要同时启用 `--novel-allele`。 | 关闭 |
| `--data-dir, --output-dir PATH` | novel allele 和 profile 输出目录。 | 当前目录 |

### 示例
```bash
gmlst typing mlst -s saureus_1 sample.fasta
gmlst typing mlst -s saureus_1 -b minimap2 sample_R1.fastq.gz sample_R2.fastq.gz
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

### 注意事项
- `mlst` 会自动识别常见的双端 FASTQ 命名模式，例如 `_R1/_R2`、`_1/_2`、`.1/.2`，并把它们作为 paired-end 输入传给支持的后端。
- 支持 `.fastq`、`.fq` 和 `.gz` 变体。
- `JSON` 输出包含每个位点的结构化调用信息，适合后续 novel 数据提取。

---

## cgmlst

对大型 cgMLST 或 wgMLST 方案执行分型。

### 用法
```bash
gmlst typing cgmlst [OPTIONS] SAMPLES...
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定 cgMLST 或 wgMLST 方案名称，例如 `vparahaemolyticus_3`。 | 必填 |
| `-b, --backend [blastn\|kma\|minimap2\|nucmer]` | 选择比对后端。 | `minimap2` |
| `--cgmlst-mode [standard\|chew-fast\|chew-ultrafast\|chew-bsr\|chew-balanced]` | 选择 cgMLST 工作流模式。 | `standard` |
| `--min-id FLOAT` | 最小百分比 identity。 | `95.0` |
| `--min-cov FLOAT` | 最小 allele 覆盖度，范围 0 到 1。 | `0.95` |
| `--min-depth FLOAT` | 最小 read depth，仅用于 FASTQ。 | `10.0` |
| `--format [tsv\|json\|pretty]` | 输出格式。 | `tsv` |
| `-o, --output PATH` | 把结果写入文件。 | 无 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |
| `--force-reindex` | 重建后端索引。 | 关闭 |
| `--no-header` | 不输出 TSV 表头。 | 关闭 |
| `-t, --threads INTEGER` | 后端使用的线程数。 | `1` |
| `--max-workers INTEGER` | 样本级并行 worker 数。 | `1` |
| `--count-same-copy` | 统计同 allele 的 multicopy 命中，目前主要用于 `blastn`。 | 关闭 |
| `-q, --quiet` | 仅保留错误输出。 | 关闭 |
| `--prefilter-k INTEGER` | cgMLST 组装预过滤使用的 k-mer 长度。 | `31` |
| `--prefilter-top-n INTEGER` | 预过滤阶段每个位点保留的 Top N 候选数。 | `20` |
| `--prefilter-min-loci-fraction FLOAT` | 信任预过滤结果所需的最小位点比例。 | `0.3` |
| `--no-prefilter` | 关闭 cgMLST 组装预过滤，改用完整位点索引路径。 | 关闭 |
| `--novel-allele` | 把 novel allele 序列写入 `{locus}_novel.fasta`。 | 关闭 |
| `--novel-profile` | 把 novel ST profile 写入 `profiles_novel.txt`，需要同时启用 `--novel-allele`。 | 关闭 |
| `--data-dir, --output-dir PATH` | novel allele 和 profile 输出目录。 | 当前目录 |
| `--cds-coordinates-out PATH` | 把预测到的 CDS 坐标导出为 TSV，便于和 chewBBACA 结果对照。 | 无 |
| `--call-policy [default\|chewbbaca]` | 指定输出分类策略。 | `default` |
| `--chew-cds-gate / --no-chew-cds-gate` | 在 `--call-policy chewbbaca` 下，是否要求证据先通过预测 CDS gate。 | 启用 |

### cgMLST 模式

| 模式 | 说明 | 适合场景 |
| --- | --- | --- |
| `standard` | 保守的基线行为，不强制启用 chew 风格覆盖。 | 需要稳定、通用设置时先从这里开始 |
| `chew-fast` | 启用 exact-hash、minimap2 哈希预过滤、缺失位点 minimap2 精修，以及面向低置信度位点的定向 `blastn` 回退。 | 日常 FASTA 组装分型 |
| `chew-ultrafast` | 基于 `chew-fast`，进一步偏向速度，使用代表序列主比对、严格救援和第二遍定向补救。 | 大批量样本，最看重吞吐量 |
| `chew-bsr` | 在 `chew-fast` 基础上加入 protein 级 exact-hash 预判。 | 需要额外 protein 证据时 |
| `chew-balanced` | 启用 exact-hash、minimap2 哈希预过滤，以及面向低置信度位点的定向 `blastn` 回退。 | 在速度和复核能力之间求平衡 |

### 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `GMLST_MINIMAP2_FASTA_SPEED_PROFILE` | 控制 minimap2 FASTA 速度档位，可选 `default`、`fast`、`ultrafast`。 | `default` |
| `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI` | 控制 `chew-ultrafast` 第二遍的位点预算，可设为 `adaptive` 或整数。 | `adaptive` |
| `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` | 对 FASTQ cgMLST 自动提升 KMA 每样本线程数。设为 `1` 可关闭。 | `8` |
| `GMLST_CGMLST_KMA_FASTQ_MEM_MODE` | 为 FASTQ cgMLST 启用 KMA `-mem_mode`。 | `1` |
| `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI` | `-mem_mode` 后最多对多少个 `closest` 位点执行严格 KMA 复查。 | `64` |
| `GMLST_CGMLST_PREFILTER_MAX_LOCI` | 预过滤自动跳过阈值。设为 `0` 表示总是尝试预过滤。 | `3000` |
| `GMLST_CGMLST_EXACT_HASH_PREFILTER` | 启用 chew 风格 DNA exact-match 预判。 | `0` |
| `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER` | 启用 minimap2 FASTA 的实验性 hash-first 预过滤。 | `0` |
| `GMLST_CGMLST_CDS_PREDICTION_MODE` | 控制 Pyrodigal CDS 模式，可选 `single` 或 `meta`。 | `single` |
| `GMLST_CGMLST_CDS_TRAINING_FILE` | 指定固定的 Pyrodigal 训练文件路径。 | 未设置 |
| `GMLST_CGMLST_CDS_CLOSED_ENDS` | 控制 Pyrodigal closed-end 预测行为。 | `0` |
| `GMLST_CGMLST_CDS_COORDINATES_OUT` | 全局导出预测 CDS 坐标 TSV。 | 未设置 |
| `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` | 控制二次精修阶段允许进入的缺失位点上限。 | `0` |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND` | 为低置信度位点启用定向回退后端，可选 `none`、`blastn`、`kma`、`nucmer`。 | `none` |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI` | 限制进入回退确认阶段的位点数量。设为 `0` 表示不限。 | `300` |
| `GMLST_MINIMAP2_KMER_ENGINE` | 控制 minimap2 的 k-mer 支持打分引擎，可选 `python`、`kmc`、`auto`。 | `python` |
| `GMLST_TMPDIR` | 覆盖临时文件目录。 | 系统临时目录 |

### 示例
```bash
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --prefilter-k 31 --prefilter-top-n 20 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --call-policy chewbbaca --cds-coordinates-out cds.tsv sample.fna
```

### 注意事项
- `typing cgmlst` 的默认后端是 `minimap2`。
- 对 FASTQ 输入，CLI 会把请求的 `-b minimap2` 自动切换到 `-b kma`，并把 `--cgmlst-mode` 当作兼容层选项处理，因为 chew 风格优化主要面向 FASTA 组装输入。
- `--call-policy chewbbaca` 仅支持 FASTA 组装输入，默认启用 `--chew-cds-gate`。
- 对大型 cgMLST 方案，使用 `-b kma` 或默认 `minimap2` 时通常建议显式提高 `-t`。

---

## tgmlst

执行 scheme-free typing，用于在没有预选公共方案时直接从样本中发现 allele 和 profile。

### 用法
```bash
gmlst typing tgmlst [OPTIONS] SAMPLES...
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `--format [tsv\|json\|pretty]` | 输出格式。 | `tsv` |
| `-o, --output PATH` | 把结果写入文件。 | 无 |
| `--no-header` | 不输出 TSV 表头。 | 关闭 |
| `-q, --quiet` | 仅保留错误输出。 | 关闭 |
| `--hash-strategy [safe\|fast\|ultra\|strict\|blast]` | 选择 allele 识别使用的哈希策略。 | `safe` |
| `--save-scheme PATH` | 把发现到的 scheme-free 方案写成 JSON。 | 无 |
| `--load-scheme PATH` | 在分型前加载已有的 scheme-free 方案 JSON。 | 无 |
| `--stats` | 输出 scheme-free 流程的时间和计数统计。 | 关闭 |
| `--max-workers INTEGER` | 覆盖 scheme-free 流程的样本级并行数。 | 无 |
| `-t, --threads INTEGER` | 控制 tgMLST 中 MMseqs 聚类线程数。 | 无 |
| `--assemble-timeout FLOAT` | 覆盖 scheme-free 组装阶段超时时间，单位为秒。 | 无 |
| `--error-report PATH` | 把每个样本的 scheme-free 错误写入 JSON。 | 无 |
| `--fail-on-error` | 只要任一样本失败就返回非零退出码。 | 关闭 |
| `--summary-report PATH` | 把本次 scheme-free 运行摘要写入 JSON。 | 无 |

### 示例
```bash
gmlst typing tgmlst sample.fna --stats
gmlst typing tgmlst sample.fna --save-scheme tgmlst_scheme.json
gmlst typing tgmlst another_sample.fna --load-scheme tgmlst_scheme.json --format json
```

### 注意事项
- `tgmlst` 是 scheme-free 流程，不要求你预先下载或指定公共方案。
- 如果你希望后续复用这次发现出的结果，可以使用 `--save-scheme` 导出 JSON，再用 `--load-scheme` 继续分析其他样本。
- `JSON` 输出适合后续自动化处理，`--summary-report` 和 `--error-report` 适合批处理审计。
