# 输出与格式

TSV 标记、JSON 与 TSV 的取舍、版本信封、stdout/stderr 分离、`--stats` 与 GrapeTree 导出。

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

### 为什么警告出现在 stderr，stdout 里只有数据？

这是 0.2.0 起明确的流纪律：stdout 只输出数据，警告、进度条、spinner 以及 "Results written to" 提示全部走 stderr。这样管道和重定向拿到的是纯净的可解析输出，例如：

```bash
gmlst typing mlst -s saureus_1 --format json sample.fasta | jq '.data[0]'
```

如果你想念这些提示信息，它们并没有丢，只是改到了 stderr，用 `2>` 可以单独查看或保存。

### `schema_version` / JSON 信封是什么？

自 0.2.0 起，所有 CLI JSON 输出统一包裹在带版本号的信封中：

```json
{
  "schema_version": "gmlst-typing-v1",
  "data": [ ... ]
}
```

原始数据原样位于 `data` 字段，`schema_version` 标识载荷格式，程序可以在解释数据前先做版本校验。如果未来版本调整了载荷结构，常量也会随之变化，脚本和 AI 智能体可以据此发现格式漂移，而不是误读数据。TSV/CSV/text 输出不使用信封；`utils extract -i <typing json>` 同时接受新信封和旧版裸列表格式。完整常量列表见 [CLI 参考](../usage/cli/index.zh.md#json-输出信封)。

### `--stats` 的输出去哪了？

`typing tgmlst --stats` 的统计 JSON 输出到 stderr（信封常量 `gmlst-tgmlst-stats-v1`），stdout 仍只有分型结果。所以直接在终端运行时两条流会交替出现，重定向 stdout 时统计信息不会混入结果文件。

要把统计保存成纯净的 JSON 文件，可以配合 `-q` 抑制其他日志：

```bash
gmlst typing tgmlst --stats -q sample.fna -o profiles.tsv 2> stats.json
```

### GrapeTree 导出失败怎么办？

GrapeTree 导出面向公共方案，或通过 `gmlst scheme create` 构建的 custom scheme。如果失败，请先确认当前方案确实是下载得到的公共方案，或是按标准流程建立的自定义方案。

例如：

```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection"
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

## 完整输出示例

TSV：

```text
FILE        SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample.fna  saureus_1   1   1     1     1     1    1    1    1
```

JSON（节选）：

```json
{
  "schema_version": "gmlst-typing-v1",
  "data": [
    {
      "file": "sample.fna",
      "scheme": "saureus_1",
      "st": "1",
      "score": 100.0,
      "status": "PERFECT",
      "alleles": {"arcC": {"call": "1", "identity": 100.0, "coverage": 1.0}}
    }
  ]
}
```

在批处理时就地过滤，而不是事后处理：

```bash
gmlst typing mlst -s saureus_1 --minscore 50 --format json *.fna -o qc.json
```

## 标记速查

| 标记 | 含义 | 是否判定 ST |
| --- | --- | --- |
| `23` | 精确、单拷贝 | 是 |
| `23*` | 精确、同等位基因多拷贝 | 是（使用 `23`） |
| `~23` | 最近或新等位基因 | 否 |
| `15?` | 部分覆盖 | 否 |
| `1,2` | 冲突多拷贝 | 否 |
| `-` | 缺失 | 否 |
