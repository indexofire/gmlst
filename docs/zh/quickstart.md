# 快速开始

本指南会带你完成一次完整的 `gmlst` 初次使用流程，从下载方案，到对 FASTA 和 FASTQ 样本进行分型。

如果你还没有完成安装，请先阅读[安装指南](installation.md)。

## 前置条件

开始之前，请确认：

- `gmlst` 已安装，并且已经加入 `PATH`
- 至少有一个后端可用，例如 `blastn`
- 当前网络可以访问方案下载源
- 样本数据是 FASTA 或 FASTQ 格式

建议先运行这些检查命令：

```bash
gmlst --version
gmlst utils check -b blastn
gmlst scheme list -p pubmlst -t mlst
```

## 第 1 步：下载一个 MLST 方案

先列出可用方案，确认具体的方案名称：

```bash
gmlst scheme list
gmlst scheme list -p pubmlst -t mlst
```

然后使用标准方案名下载。这里以 `saureus_1` 为例：

```bash
gmlst scheme download -s saureus_1
```

这条命令会完成以下事情：

- 自动解析 `saureus_1` 对应的数据提供方
- 下载 allele FASTA 文件和 profile 表
- 把方案缓存到本地，后续可重复使用

下载完成后，可以查看方案详情：

```bash
gmlst scheme show -s saureus_1
```

## 第 2 步：对第一个样本做分型

如果你的输入是组装后的 FASTA 文件，最直接的命令是：

```bash
gmlst typing mlst -s saureus_1 sample.fasta
```

这会使用默认的 `blastn` 后端，对该样本执行 MLST 分型。

常见 TSV 输出如下：

```tsv
FILE	SCHEME	ST	arcC	aroE	glpF	gmk	pta	tpi	yqiL
sample	saureus_1	1	1	1	1	1	1	1	1
```

如果你只是想快速看一个更简洁的结果，也可以使用 `pretty` 格式：

```bash
gmlst typing mlst -s saureus_1 --format pretty sample.fasta
```

示例输出：

```text
sample: ST=1
```

## 第 3 步：尝试不同后端

`gmlst` 支持多个比对后端。具体选择取决于输入数据类型，以及你更看重速度还是敏感性。

### `blastn`

适合组装后的基因组，是比较稳妥的默认选择。

```bash
gmlst typing mlst -s saureus_1 -b blastn sample.fasta
```

### `kma`

支持 FASTA 和 FASTQ，做 read-based 结果比较时也很常用。

```bash
gmlst typing mlst -s saureus_1 -b kma sample.fasta
```

### `minimap2`

同样支持 FASTA 和 FASTQ。对于 FASTQ，程序会对不确定的位点做额外的定向验证。

```bash
gmlst typing mlst -s saureus_1 -b minimap2 sample.fasta
```

### `nucmer`

基于 MUMmer4，更偏向 assembly 场景。

```bash
gmlst typing mlst -s saureus_1 -b nucmer sample.fasta
```

### 一次比较多个后端

如果你想做并排比较，可以使用 benchmark 工具：

```bash
gmlst utils benchmark -s saureus_1 -b blastn,kma,minimap2,nucmer sample.fasta
```

## 第 4 步：批量处理和结果输出

你可以一次处理多个样本。

### 输出为 TSV

```bash
gmlst typing mlst -s saureus_1 samples/*.fasta -o results.tsv
```

这会生成一个制表符分隔的结果表，便于用脚本处理或导入电子表格。

### 输出为 JSON

```bash
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

JSON 适合自动化分析、生成报告，或者后续提取 novel allele。

### 提高样本级并行度

如果你需要处理很多样本，可以并行运行多个样本：

```bash
gmlst typing mlst -s saureus_1 --max-workers 4 samples/*.fasta -o results.tsv
```

## 第 5 步：FASTQ 双端输入

`gmlst` 能自动识别常见的双端测序文件命名规则，并把它们作为真正的 paired-end reads 传给支持的后端。

支持的命名模式包括：

- `sample_R1.fastq.gz` 和 `sample_R2.fastq.gz`
- `sample_1.fq.gz` 和 `sample_2.fq.gz`
- `sample.1.fastq.gz` 和 `sample.2.fastq.gz`

### 使用 `kma` 处理双端 MLST

```bash
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### 使用 `minimap2` 处理双端 MLST

```bash
gmlst typing mlst -s saureus_1 -b minimap2 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

说明：

- 双端 reads 不会先被预合并成一个临时文件
- `kma` 和 `minimap2` 直接支持 FASTQ 输入
- `blastn` 和 `nucmer` 更偏向组装序列场景

## 第 6 步：运行 cgMLST 分型

对于位点数很多的大型方案，可以使用 `typing cgmlst`：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta
```

`typing cgmlst` 的默认后端是 `minimap2`。

根据速度和敏感性的需求，你还可以选择不同的 cgMLST 运行模式：

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fasta
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode ultrafast sample.fasta
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode balanced sample.fasta
```

如果输入是 FASTQ，`typing cgmlst` 会自动偏向 `kma` 路径，即使你请求了 `minimap2`，因为 chew 风格优化主要是为 FASTA 场景设计的。

## 第 7 步：运行无方案分型（scheme-free typing）

如果你不想先选定一个预定义方案，可以使用 `tgmlst`：

```bash
gmlst typing tgmlst sample.fasta
```

常见的相关选项包括：

```bash
gmlst typing tgmlst --format json sample.fasta -o tgmlst.json
gmlst typing tgmlst --stats sample.fasta
gmlst typing tgmlst --save-scheme discovered_scheme.json sample.fasta
```

这种模式适合探索性分析，或者希望直接从数据中推导 typing scheme 的场景。

## 结果解读

### TSV 输出格式

`typing mlst` 和 `typing cgmlst` 默认输出 TSV：

```tsv
FILE	SCHEME	ST	arcC	aroE	glpF	gmk	pta	tpi	yqiL
sample1	saureus_1	1	1	1	1	1	1	1	1
sample2	saureus_1	-	1	1	~2	1	1	15?	-
```

各列含义如下：

- `FILE`：样本标识
- `SCHEME`：分型所用方案名
- `ST`：序列型，如果无法明确解析则显示为 `-`
- 后续各列：每个位点的 allele 调用结果

### Call type 标记说明

`gmlst` 在 allele 列中使用简洁标记来表达调用类型：

| 标记 | 含义 |
|---|---|
| `23` | 与 allele 23 精确匹配 |
| `~19` | 最接近的已知 allele，或者以最近 allele ID 表示的 novel 调用 |
| `15?` | 部分命中，覆盖度不完整 |
| `-` | 未找到该位点 |

可以这样理解：

- 没有前后缀，表示 exact call
- `~` 表示不是完全干净的 exact match
- `?` 表示覆盖度不足
- `-` 表示该位点缺失或未检出

只要任意位点不是 exact，或者结果存在冲突，`ST` 就可能显示为 `-`。

### 多拷贝位点（multicopy loci）

有些物种的 housekeeping gene 可能存在多拷贝信号，这时你会看到逗号分隔的 allele 记法。

### `1,2`

表示同一个位点出现了多个高置信度但彼此冲突的 allele 命中。

### `1,1`

表示同一个 allele 似乎出现了多个拷贝。只有开启 same-copy counting 后才会显示这种记法。

### 启用 same-copy counting

```bash
gmlst typing mlst -s vparahaemolyticus_1 -b blastn --count-same-copy sample.fna
```

当前行为如下：

- `1,2` 这类冲突型 multicopy 调用无需额外参数就可能出现
- `1,1` 这类同 allele 多拷贝统计当前主要适用于 `blastn`
- 只要出现冲突型 multicopy 位点，`ST` 会被置为 `-`，避免过度自信的分型

### 针对多拷贝高发物种的推荐流程

对于容易出现 multicopy 信号的物种或方案，更稳妥的做法是采用两轮流程。

### 第一轮：常规分型

先用较快的默认流程，不启用 same-copy counting：

```bash
gmlst typing mlst -s vparahaemolyticus_1 -b minimap2 samples/*.fna -o pass1.tsv
```

### 第二轮：针对可疑样本做复查

只对有问题的样本重新运行，并使用 `blastn` 加显式 copy counting：

```bash
gmlst typing mlst -s vparahaemolyticus_1 -b blastn --count-same-copy flagged_sample.fna
```

这样既能保证日常批处理速度，也能对模糊位点做更谨慎的检查。

## 下一步

- 阅读完整的[命令参考](commands.md)
- 如果还需要配置后端工具，请回到[安装指南](installation.md)
- 了解项目整体情况，请见[仓库首页](https://github.com/indexofire/gmlst#readme)
