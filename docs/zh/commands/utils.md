[← 命令参考](../../commands.md)

# gmlst utils

提供提取、拼接、依赖检查和性能基准测试等辅助命令。

## extract

从样本文件或已有分型结果中提取 allele、novel allele 和 novel profile 数据。

### 用法
```bash
gmlst utils extract [OPTIONS]
```

### 三种模式

| 模式 | 输入 | 用途 |
| --- | --- | --- |
| Allele 提取 | 样本 FASTA 或 FASTQ | 从一个样本中提取指定或全部 loci 的 allele 序列 |
| JSON novel 提取 | `typing` 产生的 JSON | 提取 novel allele 和 novel profile |
| TSV 回退提取 | `typing` 产生的 TSV，外加原始样本目录 | 通过重新分型恢复 TSV 中无法直接携带的 novel allele 信息 |

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-i, --input PATH` | 输入文件，可以是分型结果文件 `.json`、`.tsv`，也可以是样本 FASTA。 | 必填 |
| `-s, --scheme TEXT` | 方案名称。allele 提取模式和 TSV 回退提取模式需要它。 | 无 |
| `-p, --provider TEXT` | 指定 provider，省略时自动检测或回退到默认值。 | 无 |
| `--allele TEXT` | 要提取的 loci，使用逗号分隔。省略时提取该方案的全部 loci。 | 全部 loci |
| `-b, --backend TEXT` | 从样本 FASTA 提取 allele，或 TSV 回退重分型时使用的后端。 | `blastn` |
| `--novel-allele` | 把 novel allele 序列写入 `{locus}_novel.fasta`。 | 关闭 |
| `--novel-profile` | 把 novel profile 追加到 `profiles_novel.txt`。 | 关闭 |
| `--data-dir PATH` | novel 数据输出目录。 | 当前目录 |
| `--samples-dir DIRECTORY` | TSV 回退提取时用于定位原始样本文件的目录。 | 无 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst utils extract -i genome.fasta -s ecoli_1 --allele dnaN,tsvA
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel
gmlst utils extract -i typing_results.tsv -s ecoli_1 --novel-allele --novel-profile --samples-dir ./samples --data-dir novel
```

### 注意事项
- 只要启用了 `--novel-allele` 或 `--novel-profile`，命令就会进入 novel 数据提取路径。
- 对 TSV 输入，只有 `--novel-profile` 时可以直接从表格提取。若要提取 `--novel-allele`，必须同时提供 `--scheme` 和 `--samples-dir`。
- allele 提取模式下，如果 `--allele` 留空，会按方案定义提取全部 loci。

---

## concat

把多条 FASTA 记录按顺序拼接成一条序列。

### 用法
```bash
gmlst utils concat [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-i, --input PATH` | 输入 FASTA 文件，通常来自 allele 提取结果。 | 必填 |
| `-o, --output PATH` | 输出 FASTA 路径。 | 标准输出 |

### 示例
```bash
gmlst utils concat -i genome_mlst.fasta -o genome_mlst_concat.fasta
```

### 注意事项
- 拼接顺序与输入 FASTA 中记录出现的顺序一致。
- 输出头部会自动命名为 `<input_stem>_concat`。

---

## check

检查某个后端依赖是否已经正确安装。

### 用法
```bash
gmlst utils check [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-b, --backend [blastn\|kma\|minimap2\|nucmer]` | 指定要检查的后端。 | 必填 |

### 示例
```bash
gmlst utils check -b blastn
gmlst utils check -b minimap2
```

### 注意事项
- 如果依赖缺失，命令会以非零状态退出。

---

## benchmark

对多个后端做性能比较，或执行 cgMLST 预过滤开关的一致性 gate 检查。

### 用法
```bash
gmlst utils benchmark [OPTIONS] SAMPLES...
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定分型方案。 | 必填 |
| `-b, --backends TEXT` | 要测试的后端列表，使用逗号分隔。 | `blastn,kma,minimap2,nucmer` |
| `-r, --repeat INTEGER` | 每个后端重复运行次数，用于稳定计时。 | `1` |
| `-f, --format [table\|tsv\|json]` | 输出格式。 | `table` |
| `--cgmlst-gate` | 不跑常规 benchmark，改为执行 cgMLST prefilter on/off gate 检查。 | 关闭 |
| `--gate-max-mismatches INTEGER` | `--cgmlst-gate` 模式下允许的最大 mismatch 数。 | `0` |
| `--gate-details-output PATH` | 把 gate mismatch 详情写入文件。 | 无 |
| `--gate-details-format [jsonl\|tsv]` | `--gate-details-output` 的输出格式。 | `jsonl` |
| `-o, --output PATH` | 把 benchmark 或 gate 结果写入文件。 | 无 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |
| `--force-reindex` | 重建后端索引。 | 关闭 |

### 示例
```bash
gmlst utils benchmark -s saureus_1 -b blastn,kma,minimap2,nucmer sample.fasta
gmlst utils benchmark -s saureus_1 -b blastn,minimap2 -r 3 samples/*.fasta -f json
gmlst utils benchmark -s vparahaemolyticus_3 -b minimap2 --cgmlst-gate --gate-details-output gate.jsonl samples/*.fasta
```

### 注意事项
- 常规 benchmark 会统计平均时间、标准差、每样本毫秒数、成功率、失败样本数和峰值内存等指标。
- `--cgmlst-gate` 模式要求 `-b/--backends` 里只能有一个后端，因为它比较的是同一后端在 prefilter 开启和关闭时的结果差异。
- 如果 `mismatch_count` 大于 `--gate-max-mismatches`，命令会失败并返回非零状态。
