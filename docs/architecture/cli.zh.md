# CLI 层

Click 命令如何注册、`typing` 如何分发，以及哪些策略应该留在命令层而不是后端实现里。

## CLI 层

### 顶层命令注册

`gmlst/cli.py` 注册四个顶层命令组：

- `typing`
- `scheme`
- `utils`
- `visual`

`gmlst/__main__.py` 让同一个入口也能通过 `python -m gmlst` 使用。

### Typing 命令分发

typing 相关命令实现位于 `gmlst/commands/typing.py`，主要负责：

- 样本准备
- scheme type 检测
- 后端和 mode 校验
- 临时目录策略
- 流式输出与最终输出
- 可选的 novel allele 与 novel profile 提取

`gmlst/commands/typing_runner.py` 则提供样本级并行执行。启用 `--max-workers` 时，它会把每个样本的后端线程数强制为 `1`，再按样本进行并行。

### Scheme 命令职责

`gmlst/commands/scheme.py` 负责：

- catalog 列表与刷新
- scheme 下载与更新
- 通过 `gmlst/commands/common.py` 进行 blocked scheme 过滤
- 在 `local` 命名空间下创建和更新本地自定义 scheme

### FASTQ cgMLST 的命令层策略

命令层承担一个非常重要的策略决策。对于带 FASTQ 输入的 cgMLST 运行，后端采用 KMA-first。若用户显式选择 `minimap2`，`gmlst/commands/typing.py` 会检测到 FASTQ 样本后切换到 `kma`，并把 `cgmlst_mode` 强制为 `fast`。

这样做可以明确表明，FASTQ cgMLST 不是在走 FASTA 专用的 chew 风格优化路径。

## 命令与模块对照

| 用户命令 | 入口模块 | 主要协作者 |
| --- | --- | --- |
| `typing mlst` / `typing cgmlst` | `commands/typing.py` | `typing_runner.py`、`typing_output.py`、`core/pipeline.py` |
| `typing tgmlst` | `commands/typing_schemefree.py` | `schemefree/typing_engine.py` |
| `typing mlst --guess` | `commands/typing_guess_run.py` | `commands/typing_options.py`、providers |
| `scheme download` | `commands/scheme.py` | `database/cache.py`、`database/download.py` |
| `scheme update` | `commands/scheme_update.py` | providers、`database/download.py` |
| `scheme update-fingerprints` | `commands/scheme_fingerprints.py` | `data/species_fingerprints.json.gz` |
| `utils extract` | `commands/utils.py` → `utils_extract.py` | `novel/service.py` |
| `visual web` | `visual/cli.py` | `visual/app.py`、`visual/mst.py` |

## 实例：追踪 FASTQ 策略

```text
gmlst typing cgmlst -b minimap2 reads_R1.fq.gz reads_R2.fq.gz
  commands/typing.py
    -> readers/sample.py：识别 FASTQ 双端
    -> 策略：cgMLST FASTQ 走 KMA 优先
    -> 后端改写为 kma，cgmlst_mode = fast
    -> core/pipeline.py 使用 KmaAligner
```

改写发生在构建索引之前，因此这次运行不会为 FASTA 专用索引付出代价。要调整这条
规则，请改这里，而不是 `aligners/kma.py` 或 `aligners/minimap2.py`。

## 新命令行为检查清单

- 属于用户输入校验？留在 `commands/`。
- 属于算法或数据变换？放到 `core/` 或 `calling/`。
- 需要调用外部工具？放到 `aligners/` 或 `database/download.py`。
- 行为随输入类型变化？在命令层统一决策，并把显式选项传下去。
