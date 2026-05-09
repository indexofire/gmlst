# 新等位基因工作流指南

本文介绍 `gmlst` 中的私有 MLST 工作流：从分型时检测新等位基因，到构建可重复使用的本地自定义 scheme。命令总览请参见 [../commands.md](../commands.md)，快速示例请参见 [../quickstart.md](../quickstart.md)。

## 概述

所谓新等位基因检测，是指某个 locus 的序列覆盖度足够高，说明这个位点确实存在，但与公共数据库中已知等位基因的相似度又不足以被判定为已知 allele。在本地菌株库、暴发调查或长期监测项目中，这一点非常重要，因为实验室往往会先于公共数据库观察到新的多样性。

这个工作流的核心目标有两个：

1. 从分型结果中提取新等位基因序列和完整的新 profile
2. 把这些结果合并成一个可重复使用的私有 scheme，供后续样本继续分型

## 完整流程

```bash
# 1. 对样本进行分型，并保存机器可读结果
gmlst typing mlst -s saureus_1 --format json *.fasta -o typing_results.json

# 2. 提取新等位基因和完整的新 profile
gmlst utils extract -i typing_results.json --novel-allele --novel-profile \
  --data-dir novel_data/

# 3. 用提取结果创建私有自定义 scheme
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data/ \
  --desc "Lab collection 2024"

# 4. 后续批次继续更新该自定义 scheme
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/

# 5. 导出为 GrapeTree/MST 可用格式
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

完成后，常见目录结构如下：

```text
novel_data/
├── arcC_novel.fasta
├── glpF_novel.fasta
└── profiles_novel.txt

~/.cache/gmlst/local/custom_1/
├── arcC.tfa
├── aroE.tfa
├── glpF.tfa
├── custom_1.txt
└── .meta.json
```

## 第 1 步：分型并启用新等位基因检测

建议先对样本执行分型，并把输出保存为 JSON。因为 JSON 会保留每个 locus 的详细信息，包括后续提取所需的 `novel_sequence`。

```bash
gmlst typing mlst -s saureus_1 --format json *.fasta -o typing_results.json
```

如果希望在分型时直接生成可提取的新数据文件，也可以这样运行：

```bash
gmlst typing mlst -s saureus_1 --format json \
  --novel-allele --novel-profile \
  --data-dir novel_data/ \
  *.fasta -o typing_results.json
```

这些参数的意义是：

- `--novel-allele`：把覆盖度高但与已知 allele 差异较大的序列保存为新等位基因候选
- `--novel-profile`：记录包含这些新等位基因的完整 profile
- `--data-dir`：把输出集中写入指定目录，方便后续管理

新等位基因的一般判定思路是：

- 覆盖度足够高，但 identity 低于 95%

代表性 JSON 结构示例：

```json
{
  "sample_id": "isolate_042",
  "scheme": "saureus_1",
  "st": null,
  "allele_calls": {
    "arcC": {"allele_id": "1", "call_type": "exact"},
    "aroE": {"allele_id": "7", "call_type": "exact"},
    "glpF": {
      "allele_id": "19",
      "call_type": "novel",
      "novel_sequence": "ATGAAACT..."
    }
  }
}
```

## 第 2 步：提取新数据

拿到分型结果后，把新等位基因和完整的新 profile 提取到一个单独目录中。

### 从 JSON 分型结果提取

```bash
gmlst utils extract -i typing_results.json --novel-allele --novel-profile \
  --data-dir novel_data/
```

典型输出：

```text
Novel alleles written:
  glpF: novel_data/glpF_novel.fasta
  gmk: novel_data/gmk_novel.fasta
Novel profiles written: novel_data/profiles_novel.txt
```

### 从 TSV 分型结果提取

如果之前只保留了 TSV，也可以回退到 TSV 路径。但这时需要提供 scheme 名称和原始样本目录，以便 `gmlst` 重新定位并恢复序列信息。

```bash
gmlst utils extract -i typing_results.tsv -s ecoli_1 \
  --novel-allele --novel-profile \
  --samples-dir ./samples \
  --data-dir novel_data/
```

适用场景是：你有旧的分型表，但当时没有保存 JSON。

### 命名规则

- 新等位基因命名为 `{locus}_n{number}`，例如 `dnaN_n1`
- 新 profile 命名为 `N{number}`，例如 `N1`
- allele 编号按 locus 分别递增，profile 编号在输出集合内全局递增

跨多次运行时有一个很重要的区别：

- `profiles_novel.txt` 可以安全追加
- `{locus}_novel.fasta` 每次运行都会重新生成，因此多批次时最好为每批使用不同的 `--data-dir`，或基于合并后的 JSON 重新提取

## 第 3 步：创建自定义 scheme

提取完成后，就可以把公共 scheme 与新等位基因/新 profile 合并成一个私有 scheme。

```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data/ \
  --desc "Lab collection 2024"
```

这一步的价值在于：

- 把零散的新数据变成一个真正可分型的 scheme
- 保留原始公共数据库中的 allele 和 ST
- 让后续样本能直接匹配你实验室自己的新 allele

自定义 scheme 会自动命名为 `custom_1`、`custom_2` 等，并作为 `local` provider 出现在 scheme 列表中。

```bash
gmlst scheme list -p local
```

示例输出：

```text
PROVIDER  TYPE  SCHEME     DESCRIPTION
local     mlst  custom_1   Lab collection 2024
```

生成后的目录通常如下：

```text
~/.cache/gmlst/local/custom_1/
├── arcC.tfa
├── aroE.tfa
├── glpF.tfa
├── custom_1.txt
└── .meta.json
```

## 第 4 步：更新自定义 scheme

后续样本如果又发现新的 allele，不需要重新建一个 scheme，而是继续更新已有的 custom scheme。

```bash
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/
```

这能保持编号和元数据的连续性，特别适合同一个实验室项目或同一套长期监测数据。

典型更新流程：

```bash
# 对下一批样本分型
gmlst typing mlst -s saureus_1 --format json batch2/*.fasta -o batch2.json

# 提取新数据
gmlst utils extract -i batch2.json --novel-allele --novel-profile \
  --data-dir more_novel_data/

# 合并进已有 custom scheme
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/
```

更新完成后，`custom_1` 就可以像普通 scheme 一样直接用于分型：

```bash
gmlst typing mlst -s custom_1 new_isolate.fasta
```

## 第 5 步：导出用于可视化

当 custom scheme 中已经包含你需要比较的 profile 集合后，可以导出为 GrapeTree 兼容格式，用于 MST 分析。

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

该文件可直接用于 [visual_guide.md](visual_guide.md) 中的本地可视化工作流。

代表性前几行如下：

```tsv
#Strain	arcC	aroE	glpF	gmk	pta	tpi	yqiL
ST1	1	1	1	1	1	1	1
STN1	n1	7	3	9	4	2	1
```

第一列是由 profile 标识符派生出的 strain 标签。已知 allele 仍然保持数字形式，新 allele 则保持 `nX` 格式。

## 等位基因提取

`utils extract` 也可以直接从单个样本 FASTA 中提取被调用到的 allele 序列。这在你想查看每个样本的 MLST allele FASTA、做后续比对或下游分析时很有用。

```bash
gmlst utils extract -i genome.fasta -s ecoli_1 > genome_mlst.fasta
```

如果只想提取指定 loci：

```bash
gmlst utils extract -i genome.fasta -s ecoli_1 --allele dnaN,tsvA,abcN
```

代表性输出：

```fasta
>dnaN_12 sample=genome
ATGGCTAACAAAGT...
>tsvA_4 sample=genome
ATGCGTATCGGTTA...
>abcN_18 sample=genome
ATGGATTTACCGAA...
```

## 序列拼接

如果你希望为系统发育或距离分析生成拼接后的 allele 序列，可以对提取出的 FASTA 使用 `utils concat`。

```bash
gmlst utils concat -i genome_mlst.fasta -o genome_mlst_concat.fasta
```

这样可以把多个 allele 记录合并为一个更适合下游树构建或比对流程的序列。

## 文件格式

### 新等位基因 FASTA

文件名模式：

```text
{locus}_novel.fasta
```

示例：

```fasta
>dnaN_n1 sample=isolate_A1
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
>dnaN_n2 sample=isolate_B2
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCA
```

### 新 profile 文件

文件名：

```text
profiles_novel.txt
```

示例：

```tsv
ST	sample	dnaN	gyrB	abcZ
N1	isolate_A1	n1	5	12
N2	isolate_B2	n2	5	12
```

### 自定义 scheme 元数据

文件名：

```text
.meta.json
```

代表性结构：

```json
{
  "scheme": "custom_1",
  "provider": "local",
  "based_on": "saureus_1",
  "based_on_provider": "pubmlst",
  "scheme_type": "mlst",
  "description": "Lab collection 2024",
  "loci": ["arcC", "aroE", "glpF", "gmk", "pta", "tpi", "yqiL"],
  "novel_alleles": {"arcC": ["n1"], "glpF": ["n1", "n2"]},
  "novel_profiles": ["N1", "N2"],
  "last_allele_number": {"arcC": 1, "glpF": 2}
}
```

## 最佳实践

- 新等位基因工作流优先使用 JSON 分型结果，因为它保留了 `novel_sequence`，无需重新分型
- 一个项目或一组批次建议使用独立的 `novel_data/` 目录，而不是所有批次共用一个临时目录
- 多批次时，最好为每批使用不同目录保存 novel allele FASTA，或者从合并后的 JSON 重新提取
- 创建 custom scheme 时请填写清晰的 `--desc`，这样本地目录和列表更容易维护
- 如果是在扩展同一套项目数据，请优先使用 `scheme update-custom`
- 只有在 custom scheme 已经包含你想比较的 allele 集合后，再导出 GrapeTree TSV

## 故障排查

### 使用了 `--novel-profile` 但没有生成 profile 文件

`--novel-profile` 依赖 `--novel-allele`，而且只有完整 profile 才能写入。如果样本存在缺失位点或 partial 位点，就不会生成 novel profile。

### 多次运行后新等位基因 FASTA 发生变化

如果你在多次提取时复用了同一个 `--data-dir`，这是预期行为。`profiles_novel.txt` 可以安全追加，但 `{locus}_novel.fasta` 会在每次运行时重写。

建议做法：

```bash
gmlst utils extract -i batch1.json --novel-allele --novel-profile --data-dir novel_batch1/
gmlst utils extract -i batch2.json --novel-allele --novel-profile --data-dir novel_batch2/
```

### 我只有 TSV 分型结果

请使用 TSV 回退路径，并同时提供 `--samples-dir` 和 `-s/--scheme`：

```bash
gmlst utils extract -i typing_results.tsv -s ecoli_1 \
  --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel_data/
```

### `custom_1` 没有出现在 scheme 列表里

请显式查看本地 provider：

```bash
gmlst scheme list -p local
```

自定义 scheme 属于 `local` provider。

### 我想把结果放进树图中比较

先导出 GrapeTree 格式：

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

然后把这个文件加载到 [visual_guide.md](visual_guide.md) 描述的可视化流程中。
