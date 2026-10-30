# 分型流水线

从命令到结果的完整路径：方案解析、索引、预过滤、比对、调用、ST 判定，以及 FASTA 与 FASTQ 两条执行路径。

## 核心数据流

主 typing 流程从 CLI 开始，最后生成格式化报告。

```text
用户命令
  -> gmlst/cli.py
  -> gmlst/commands/typing.py
  -> gmlst/commands/typing_scheme.py
  -> gmlst/database/cache.py ensure_scheme()
  -> gmlst/core/pipeline.py run_typing_impl()
  -> gmlst/readers/sample.py detect_sample() / prepare_sample_inputs()
  -> gmlst/core/indexing.py 和 gmlst/core/pipeline.py 的索引逻辑
  -> gmlst/aligners/<backend>.py align()
  -> gmlst/calling/allele.py call_all_loci()
  -> gmlst/core/refinement.py 和适配器层
  -> gmlst/calling/st_lookup.py lookup_st()
  -> gmlst/commands/typing_output.py 输出 TSV / JSON / pretty
```

对于批量样本，`gmlst/commands/typing_runner.py` 会在同一核心流程之外增加样本级并行。

## 核心 pipeline

主运行入口是 `gmlst/core/pipeline.py` 中的 `run_typing_impl()`。

从高层看，它的工作顺序如下：

1. 创建 `DatabaseCache`
2. 解析并缓存请求的 scheme
3. 根据 `cgmlst_mode` 解析 mode override
4. 构建选定的 aligner，并检查外部依赖
5. 使用 `gmlst/readers/sample.py` 检测每个样本
6. 构建或复用 index
7. 判断是否启用 prefilter 和 exact-hash shortcut
8. 对每个样本，或者每个 unresolved locus 集合执行比对
9. 对 locus 进行 calling，并执行 post-alignment refinement
10. 执行 ST lookup
11. 把结果返回给命令层输出

### 索引构建与复用

持久化后端 index 保存在 `gmlst/database/cache.py` 的 `DatabaseCache.index_dir()` 下。`gmlst/core/pipeline.py` 只有在需要时，或者 `force_reindex` 启用时才会重建。

### Prefilter 与候选缩小

面对大型 cgMLST scheme，pipeline 不一定要对完整 allele 数据库做全量比对。`gmlst/core/pipeline.py`、`gmlst/core/prefilter.py`、`gmlst/kmer_prefilter.py` 和 `gmlst/core/adapters_index_prefilter.py` 支持：

- 面向组装序列的 k-mer 候选缩小
- minimap2 representative prefilter
- 在部分 FASTA 路径上使用 representative-only minimap2 主比对

### Ranking 与 refinement

初始最优命中不一定就是最终答案。`gmlst/core/ranking.py`、`gmlst/core/refinement.py` 和 `gmlst/core/adapters_refinement.py` 会在比对之后进一步修正 call，把后端特有证据重新整合进统一的 calling 结果。

## FASTA 与 FASTQ 执行路径

### 输入检测与双端分组

`gmlst/readers/sample.py` 是输入检测的唯一权威来源。

- FASTA 后缀包括 `.fasta`、`.fa`、`.fna`、`.ffn`、`.frn`
- FASTQ 后缀包括 `.fastq`、`.fq`，可带 `.gz`
- mate grouping 识别 `_R1` 和 `_R2`、`_1` 和 `_2`、`.1` 和 `.2` 这几类模式

识别成一对后，会被转换成一个包含 `path` 和 `mate_path` 的 `SampleInput`。

### FASTA 路径

FASTA 路径拥有更完整的优化能力。在 `gmlst/core/pipeline.py` 中，组装后的基因组可使用：

- exact DNA 和 protein hash 预解析
- cgMLST prefilter
- minimap2 representative alignment shortcut
- chewBBACA 风格的 CDS 感知分类
- post-alignment refinement 和 evidence fallback 路径

### FASTQ 路径

FASTQ 支持是刻意收窄的。

- 在 aligner 合约中，只有 `kma` 与 `minimap2` 声明了 `supports_fastq`
- cgMLST FASTQ 运行在 CLI 层会统一到 KMA-first 路线
- minimap2 FASTQ 仍可用于非 cgMLST 场景
- exact-hash 和基于 assembly 的 cgMLST prefilter 路径，只有在全部样本都是单文件 FASTA 时才会启用

## cgMLST 模式

cgMLST mode 配置由 `gmlst/core_config.py` 加上 `gmlst/core/` 与 `gmlst/core/pipeline.py` 中的 override 逻辑共同驱动。

用户可见模式包括：

- `fast`
- `ultrafast`
- `balanced`

这些模式主要影响偏 FASTA 的 minimap2 与 refinement 路线，例如：

- 是否启用 exact-hash shortcut
- 是否启用 minimap2 hash prefilter
- 是否允许 representative-main alignment
- second-pass rescue 的预算大小
- 是否启用基于 CDS 的 chew 风格分类

相关文件：

- `gmlst/core_config.py`
- `gmlst/core/pipeline.py`
- `gmlst/calling/chew_policy.py`
- `gmlst/core/cds.py`
- `gmlst/core/exact_hash.py`
- `gmlst/core/adapters_cds.py`
- `gmlst/core/adapters_exact_hash.py`

对于 FASTQ cgMLST，`gmlst/commands/typing.py` 会把这些模式统一压回 `fast`。

## 实例：一个 MLST 样本

以 `saureus_1`（7 个 locus）和 `sample.fna` 为例，各阶段如下：

| 阶段 | 输入 | 输出 |
| --- | --- | --- |
| 方案解析 | `saureus_1` | 缓存中的 allele FASTA 与 profile 表 |
| 输入检测 | `sample.fna` | `SampleInput(path=..., input_type="fasta")` |
| 索引 | allele FASTA | 后端索引，后续运行复用 |
| 比对 | 样本 + 索引 | 每个 locus 的 `AlleleMatch` |
| 调用 | 命中 | 每个 locus 的 `23`、`~23`、`15?` 或 `-` |
| ST 判定 | allele profile | `ST = 1`，无精确 profile 时为 `-` |
| 渲染 | 调用结果 | 一行 TSV |

```text
FILE        SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample.fna  saureus_1   1   1     1     1     1    1    1    1
```

## 代码中的流水线顺序

`run_typing_impl()` 刻意保持线性，每一步都可以单独测试：

```python
cache = DatabaseCache(cache_dir)
scheme = cache.ensure_scheme(scheme_name)
aligner = build_aligner(backend)

for sample in samples:
    sample_input = detect_sample(sample)
    index = ensure_index(aligner, scheme, force_reindex)
    result = align_and_call(aligner, sample_input, index, scheme)
    result.st = lookup_st(result.allele_profile, scheme.profiles)
```

真实实现会在比对与 ST 判定之间插入预过滤、exact-hash 与 refinement，但重构时应
保持上述顺序这一契约。

## 阶段故障速查

| 现象 | 可能阶段 | 排查位置 |
| --- | --- | --- |
| `Scheme 'X' not found` | 方案解析 | `database/cache.py` |
| 所有 locus 缺失 | 检测或索引 | `readers/sample.py`、`core/indexing.py` |
| 大量部分调用 | 比对阈值 | `commands/common.py`、`calling/allele.py` |
| 有调用但 `ST = -` | ST 判定 | `calling/st_lookup.py` |
| 输出缺少行 | 渲染或 `--minscore` | `commands/typing_output.py` |

## FASTA/FASTQ 决策在哪里做

分流只在 `commands/typing.py` 决策一次，然后以具体选项传给流水线：

```text
FASTA  -> 允许预过滤、允许 exact-hash、允许 minimap2 代表序列路径
FASTQ  -> cgMLST 走 KMA 优先，禁用组装级捷径
```

如果新增的优化只适用于组装序列，应在同一位置用 `input_type == "fasta"` 门控，
而不是让后端自行猜测。
