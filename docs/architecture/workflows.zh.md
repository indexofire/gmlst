# Novel 与无方案工作流

新等位基因如何变成可复用的自定义方案，以及无方案 `tgmlst` 引擎的结构。

## Novel allele 工作流

novel allele 处理横跨 typing 命令和 scheme 命令。

### Typing 阶段

`gmlst/novel/service.py` 会从 typing 结果中收集 novel allele 和 novel profile。`gmlst/novel/writer.py` 中的 writer 负责写出：

- 各 locus 的 `*_novel.fasta`
- `profiles_novel.txt`

### 自定义 scheme 创建阶段

`gmlst/commands/scheme.py` 使用这些文件在 `local` 命名空间下创建 `custom_<n>` 形式的本地 scheme。元数据由 `gmlst/novel/service.py` 中的辅助函数构造，并与 allele FASTA、profile 文件一起写入 `.meta.json`。

因此 novel discovery 是一个可重复闭环：

```text
typing 结果
  -> novel 提取
  -> 创建本地 custom scheme
  -> 以后继续用更多 novel 数据更新 custom scheme
```

## Scheme-free typing, tgMLST

scheme-free typing 位于 `gmlst/schemefree/`，与基于 provider 下载的传统 scheme 路径分离。

主入口是 `gmlst/schemefree/typing_engine.py` 中的 `SchemeFreeTyper`，它负责：

1. 通过 `gmlst/schemefree/assembly_engine.py` 对 FASTQ 做可选组装
2. 通过 `gmlst/core/gene_predictor.py` 做基因预测
3. 通过 `gmlst/schemefree/cluster_engine.py` 做聚类
4. 通过 `gmlst/schemefree/hasher.py` 做 allele 哈希
5. 通过 `gmlst/schemefree/io_handler.py` 做 scheme 导入与导出

这一路径由 `gmlst/commands/typing.py` 暴露，不依赖传统 MLST 和 cgMLST 所使用的 provider cache 模型。

## Novel allele 端到端循环

```bash
# 1. 用 JSON 分型，保留新序列
gmlst typing mlst -s saureus_1 --format json samples/*.fna -o results.json

# 2. 提取新等位基因与 profile
gmlst utils extract -i results.json --novel-allele --novel-profile --data-dir novel

# 3. 查看生成的文件
ls novel/
# arcC_novel.fasta  aroE_novel.fasta  profiles_novel.txt

# 4. 创建本地方案
gmlst scheme create -t mlst -s saureus_1 --data-dir novel --desc "Lab 2026"

# 5. 用新方案分型
gmlst typing mlst -s custom_1 new_sample.fna
```

分型 JSON 中的新等位基因记录会携带提取到的序列：

```json
{
  "locus": "arcC",
  "call": "~23",
  "identity": 98.7,
  "coverage": 1.0,
  "novel_sequence": "ATG..."
}
```

## 无方案分型数据流

```text
reads/组装
  ->（可选）组装
  -> 基因预测
  -> 基因聚类（mmseqs2，缺失时回退哈希）
  -> allele 哈希
  -> profile 表
  -> 可选 --save-scheme JSON
```

复用已发现的方案可以让多次运行的哈希保持稳定：

```bash
gmlst typing tgmlst sample.fna --save-scheme tgmlst_scheme.json
gmlst typing tgmlst other.fna --load-scheme tgmlst_scheme.json --format json
```

## 各步骤所在模块

| 步骤 | 模块 |
| --- | --- |
| 分型期间收集新等位基因 | `gmlst/novel/service.py` |
| 序列与 profile 写出 | `gmlst/novel/writer.py` |
| 自定义方案创建 | `gmlst/commands/scheme_custom.py` |
| 基因预测 | `gmlst/core/gene_predictor.py` |
| 聚类 | `gmlst/schemefree/cluster_engine.py` |
| 哈希 | `gmlst/schemefree/hasher.py` |
| tgmlst 编排 | `gmlst/schemefree/typing_engine.py` |
