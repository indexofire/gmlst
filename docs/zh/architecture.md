# gmlst 架构文档

本文说明 `gmlst` 的整体结构、数据流，以及各个主要职责在仓库中的位置。安装和命令用法请参考 [`docs/installation.md`](../en/installation.md)、[`docs/quickstart.md`](../en/quickstart.md)、[`docs/commands.md`](commands.md) 和 [`docs/providers.md`](../en/providers.md)。

## 概览

`gmlst` 是一个分层的 Python CLI 工具，支持 MLST、cgMLST、wgMLST，以及 scheme-free typing。项目把稳定的命令接口、后端无关的比对与 calling 逻辑、可缓存的数据库提供者，以及可选的可视化模块组合在一起。

核心设计目标如下：

- 保持 CLI 足够薄，把核心决策放到可复用的领域代码中
- 用统一的结果模型支持多个比对后端
- 用统一的 provider 接口支持多个远程方案来源
- 缓存 scheme 和 index，让重复运行更快，也支持离线使用
- 明确区分 FASTA、FASTQ 和 cgMLST 特有策略，避免把策略隐藏在某个后端实现里

## 系统架构图

```text
                                +------------------+
                                |  用户 / Shell    |
                                +--------+---------+
                                         |
                                         v
                                +------------------+
                                | gmlst/cli.py     |
                                | Click 入口       |
                                +--------+---------+
                                         |
              +--------------------------+---------------------------+
              |                          |                           |
              v                          v                           v
    +------------------+      +------------------+       +------------------+
    | commands/typing  |      | commands/scheme  |       | visual/cli.py    |
    | commands/utils   |      | catalog/cache UX |       | Flask / 导出     |
    +--------+---------+      +--------+---------+       +--------+---------+
             |                         |                           |
             v                         v                           v
    +------------------+      +------------------+       +------------------+
    | core/ pipeline   |      | database/cache.py|       | visual/app.py    |
    | calling/         |      | providers/*      |       | visual/mst.py    |
    | novel/           |      | download.py      |       | web/* 资源       |
    | schemefree/      |      +------------------+       +------------------+
    +--------+---------+
             |
             v
    +------------------+
    | aligners/*       |
    | readers/*        |
    | 外部工具集成     |
    +--------+---------+
             |
             v
    +------------------+
    | 输出层           |
    | TSV / JSON / UI  |
    +------------------+
```

## 源码结构

下面的目录树展示了主要代码布局。路径都以仓库根目录为基准。

```text
gmlst/
├── __init__.py
├── __main__.py
├── cli.py
├── core_config.py
├── fasta_io.py
├── kmer_prefilter.py
├── metadata_io.py
├── utils.py
├── aligners/
│   ├── base.py
│   ├── blastn.py
│   ├── kma.py
│   ├── minimap2.py
│   └── nucmer.py
├── calling/
│   ├── allele.py
│   ├── chew_policy.py
│   ├── confidence.py
│   └── st_lookup.py
├── commands/
│   ├── common.py
│   ├── config.py
│   ├── typing.py
│   ├── typing_output.py
│   ├── typing_runner.py
│   ├── typing_runtime.py
│   ├── typing_scheme.py
│   ├── scheme.py
│   ├── scheme_common.py
│   ├── scheme_render.py
│   ├── scheme_custom.py
│   ├── utils.py
│   ├── utils_extract.py
│   └── utils_benchmark.py
├── core/
│   ├── config.py
│   ├── pipeline.py
│   ├── gene_predictor.py
│   ├── indexing.py
│   ├── prefilter.py
│   ├── ranking.py
│   ├── refinement.py
│   ├── sequences.py
│   ├── types.py
│   ├── cds.py
│   ├── exact_hash.py
│   ├── adapters_cds.py
│   ├── adapters_exact_hash.py
│   ├── adapters_index_prefilter.py
│   └── adapters_refinement.py
├── data/
│   ├── blocked_schemes.json
│   ├── organism_mapping.json
│   └── catalogs/
├── database/
│   ├── cache.py
│   ├── download.py
│   ├── schema.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       ├── bigsdb.py
│       ├── enterobase.py
│       ├── cgmlst.py
│       └── cgmlst_schemes.py
├── novel/
│   ├── reader.py
│   ├── service.py
│   └── writer.py
├── readers/
│   ├── fasta.py
│   ├── fastq.py
│   └── sample.py
├── schemefree/
│   ├── assembly_engine.py
│   ├── cluster_engine.py
│   ├── config.py
│   ├── gene_predictor.py   # re-export shim (实现在 core/)
│   ├── hasher.py
│   ├── io_handler.py
│   └── typing_engine.py
├── visual/
│   ├── cli.py
│   ├── _cli_helpers.py
│   ├── _cli_export.py
│   ├── app.py
│   └── mst.py
└── web/
    ├── frontend/
    ├── static/
    └── templates/
```

### 顶层模块

- `gmlst/__main__.py` 是 `python -m gmlst` 的入口。
- `gmlst/cli.py` 注册顶层 Click 命令组，`typing`、`scheme`、`utils`、`visual`。
- `gmlst/core_config.py` 集中管理基于环境变量的 cgMLST 和后端开关。
- `gmlst/fasta_io.py` 与 `gmlst/metadata_io.py` 提供专用 I/O 辅助函数。
- `gmlst/utils.py` 提供日志初始化和通用工具。

### 领域与编排层

- `gmlst/core/` 包含 typing 流程编排、索引、prefilter、ranking、refinement、序列处理和适配器层。
- `gmlst/calling/` 包含等位基因解释、置信度逻辑、chewBBACA 风格策略，以及 ST 查找。
- `gmlst/novel/` 负责 novel allele 和 novel profile 的提取与写出。
- `gmlst/schemefree/` 负责独立的 tgMLST 工作流。

### 基础设施层

- `gmlst/aligners/` 把 BLAST+、KMA、minimap2、MUMmer4 包装成统一接口。
- `gmlst/database/` 负责 provider 集成、下载、catalog 和缓存布局。
- `gmlst/readers/` 负责输入类型检测和 FASTQ 双端分组。

### 展示层

- `gmlst/commands/` 定义 CLI 命令行为。
- `gmlst/visual/` 提供 MST 和结果比较 API，以及 Flask 应用。
- `gmlst/web/` 存放前端源码、构建产物和模板。

## 架构分层

### 1. CLI 层

CLI 层位于 `gmlst/cli.py` 和 `gmlst/commands/`，负责：

- 通过 Click 解析用户输入
- 校验命令组合是否合法
- 应用命令级策略，例如 FASTQ cgMLST 的后端切换
- 调用领域逻辑
- 将结果格式化为终端输出或文件输出

重要文件：

- `gmlst/cli.py`
- `gmlst/commands/typing.py`
- `gmlst/commands/typing_runner.py`
- `gmlst/commands/typing_output.py`
- `gmlst/commands/typing_scheme.py`
- `gmlst/commands/scheme.py`
- `gmlst/commands/utils.py`
- `gmlst/visual/cli.py`

### 2. 领域层

领域层主要位于 `gmlst/core/`、`gmlst/calling/`、`gmlst/novel/` 和 `gmlst/schemefree/`，负责真正的 typing 行为和结果解释。

例如：

- `gmlst/core/pipeline.py` 负责端到端 typing 编排。
- `gmlst/calling/allele.py` 与 `gmlst/calling/st_lookup.py` 把比对结果转换成 allele call 和 ST。
- `gmlst/novel/service.py` 收集并保存 novel allele 与 novel profile。
- `gmlst/schemefree/typing_engine.py` 协调整个 scheme-free typing。

### 3. 基础设施层

基础设施层位于 `gmlst/aligners/`、`gmlst/database/` 和 `gmlst/readers/`，负责外部工具、远程数据源和本地缓存。

例如：

- `gmlst/aligners/base.py` 定义 aligner 合约。
- `gmlst/database/providers/base.py` 定义 provider 合约。
- `gmlst/database/cache.py` 管理 scheme 和 index 的本地存储。
- `gmlst/readers/sample.py` 负责 FASTA 与 FASTQ 检测，以及 mate pair 自动分组。

### 4. 展示层

展示层位于 `gmlst/visual/` 和 `gmlst/web/`。

- `gmlst/visual/app.py` 创建 Flask 应用和 JSON 接口。
- `gmlst/visual/mst.py` 计算 profile distance、MST、heatmap 和结果比较。
- `gmlst/web/frontend/` 存放 Vue 3 + Vite 前端源码。
- `gmlst/web/templates/` 与 `gmlst/web/static/` 提供模板和静态资源。

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

## 比对后端架构

### Protocol 模式

`gmlst/aligners/base.py` 定义了 `Aligner` `Protocol`。在 Python 里，`Protocol` 表示结构化接口。实现类不一定要继承某个基类，只要满足接口要求即可。

在本项目中，每个 aligner 都必须提供以下能力：

- `name`
- `supports_fastq`
- `check_dependencies()`
- `index(allele_fastas, index_dir)`
- `align(sample, index_path, loci, input_type)`

这样 `gmlst/core/pipeline.py` 只需要在一开始选定后端，后续就能用统一方式调用。

### `AlleleMatch` 标准化

`gmlst/aligners/base.py` 还定义了 `AlleleMatch` 和 `AlignmentResult`。

每个后端都必须把自己的原生输出转换成 `AlleleMatch`，其中包括：

- locus 名称
- allele id
- identity
- coverage
- score
- 读段输入时可用的 depth
- novel allele 路径可用的提取序列
- 坐标和 copy count 等附加信息

这一步标准化，是后续 calling 逻辑能够后端无关的关键原因。

### 后端实现

- `gmlst/aligners/blastn.py` 面向 BLAST+，偏 FASTA 工作流。
- `gmlst/aligners/kma.py` 支持 FASTA 和 FASTQ，也是 cgMLST FASTQ 的优先路径。
- `gmlst/aligners/minimap2.py` 支持 FASTA 和 FASTQ，并提供 representative 与 hash-prefilter 相关优化。
- `gmlst/aligners/nucmer.py` 基于 MUMmer4，面向 FASTA 比对。

## 数据 provider 架构

### Provider 协议

`gmlst/database/providers/base.py` 定义了 `Provider` `Protocol`。和 aligner 一样，它也是结构化接口。

每个 provider 需要暴露：

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

每个 scheme 用 `gmlst/database/providers/base.py` 中的 `SchemeInfo` 表示，字段包括：

- `scheme_name`
- `display_name`
- `organism`
- `scheme_type`
- `n_loci`
- `provider`
- `extra`，用于保存 URL、目录名等 provider 特有信息

### Provider 注册表

`gmlst/database/providers/__init__.py` 构建运行时注册表，固定包含：

- `pubmlst`，实现位于 `gmlst/database/providers/bigsdb.py`
- `pasteur`，实现位于 `gmlst/database/providers/bigsdb.py`
- `enterobase`，实现位于 `gmlst/database/providers/enterobase.py`
- `cgmlst`，实现位于 `gmlst/database/providers/cgmlst.py`

如果设置了 `GMLST_PRIVATE_BIGSDB_URL`，注册表还会动态添加一个私有 BIGSdb provider。

### Catalog 管理和全局唯一命名

`gmlst/database/cache.py` 负责 `_catalog/` 下的 provider catalog 缓存，并保证不同 provider 之间的 scheme 名称全局唯一。

这里有两层逻辑：

1. `_normalize_scheme_names()` 在单个 provider 内部先标准化命名。
2. `save_catalog()` 再和其他 provider 的 catalog 对比，必要时继续增加数字后缀。

因此不同 provider 中同一物种的 scheme，仍然可以稳定地得到 `spneumoniae_1`、`spneumoniae_2`、`spneumoniae_3` 这类不冲突的名字。

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

命令层承担一个非常重要的策略决策。对于带 FASTQ 输入的 cgMLST 运行，后端采用 KMA-first。若用户显式选择 `minimap2`，`gmlst/commands/typing.py` 会检测到 FASTQ 样本后切换到 `kma`，并把 `cgmlst_mode` 强制为 `standard`。

这样做可以明确表明，FASTQ cgMLST 不是在走 FASTA 专用的 chew 风格优化路径。

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

- `standard`
- `chew-fast`
- `chew-ultrafast`
- `chew-balanced`

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

对于 FASTQ cgMLST，`gmlst/commands/typing.py` 会把这些模式统一压回 `standard`。

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

## 可视化架构

可视化栈主要分成两层。

### 后端层

- `gmlst/visual/cli.py` 暴露导出和服务命令
- `gmlst/visual/app.py` 创建 Flask 应用并校验 JSON payload
- `gmlst/visual/mst.py` 从 typing 输出表中计算 distance、mismatch loci、聚合节点和 MST edge

### 前端层

- `gmlst/web/frontend/` 存放 Vue 3 + Vite 前端源码
- `gmlst/web/templates/` 存放 Flask 使用的 HTML 模板
- `gmlst/web/static/` 存放构建后的静态资源

可视化模块与 typing pipeline 是解耦的。它消费导出的 TSV 或 JSON 风格 payload，而不是直接调用比对流程。

## 缓存管理

`gmlst/database/cache.py` 是核心缓存管理器。缓存根目录按以下顺序解析：显式参数、`GMLST_CACHE_DIR` 环境变量、`$CONDA_PREFIX/share/gmlst`（conda 环境）、`$VIRTUAL_ENV/.cache/gmlst`（virtualenv）、`~/.cache/gmlst`（默认回退）。每个 conda 或 virtualenv 环境默认拥有独立的缓存。

典型目录结构如下：

```text
~/.cache/gmlst/
├── <provider>/
│   └── <scheme_name>/
│       ├── <locus>.tfa 或 <locus>.fasta
│       ├── <scheme_name>.txt 或 .tsv
│       └── .meta.json
├── _catalog/
│   └── <provider>.json
└── _indexes/
    └── <provider>/
        └── <backend>/
            └── <scheme_name>/
```

### 离线运行

一旦 scheme 及其 index 已缓存，typing 就可以在不重新下载 provider 数据的情况下复用它们。`gmlst/data/catalogs/` 下的内置 catalog 也会在本地 catalog 不存在时复制到缓存中作为默认值。

## 关键设计决策

### 为什么使用 `Protocol`

aligner 和 provider 都使用 `Protocol`，而不是复杂的继承树。这样可以让新实现只需满足接口形状，降低编排代码与具体实现之间的耦合。

### 为什么要标准化后端输出

如果没有 `gmlst/aligners/base.py` 中的 `AlleleMatch`，后续 calling 逻辑就必须充满后端分支判断。标准化之后，`gmlst/calling/` 可以专注于 allele 语义，而不是解析 BLAST、KMA、minimap2 或 nucmer 的原始格式。

### 为什么把 FASTQ 策略放在 CLI 层

FASTQ cgMLST 的 KMA-first 规则，不是某个通用后端属性，而是产品级策略选择。把它放在 `gmlst/commands/typing.py` 中，行为更清晰，也更方便后续调整。

### 为什么缓存 catalog 和 index

provider 列表查询和后端建索引都比普通命令解析更昂贵。持久化 catalog 与 index 可以减少重复网络访问和重复建索引的成本。

### 为什么使用 Click

Click 为项目提供了统一的选项解析、命令分组、Shell 友好的帮助输出，以及在 `typing`、`scheme`、`utils`、`visual` 四个命令族之间易于组合的结构。

## 仓库路径约定

这些约定描述了当前代码如何组织，以及新增代码应当放在哪里。

### 代码放置规则

- CLI 注册放在 `gmlst/cli.py` 或特性相关的 CLI 模块中，例如 `gmlst/visual/cli.py`
- 命令实现放在 `gmlst/commands/`
- 纯 typing 编排逻辑放在 `gmlst/core/`
- allele 与 ST 解释逻辑放在 `gmlst/calling/`
- provider 与缓存逻辑放在 `gmlst/database/`
- 外部比对器集成放在 `gmlst/aligners/`
- 输入检测逻辑放在 `gmlst/readers/`
- 可视化代码放在 `gmlst/visual/` 和 `gmlst/web/`

### 命名规则

- 模块和文件使用 `snake_case`，例如 `typing_runner.py`
- 类使用 `PascalCase`，例如 `DatabaseCache`、`SchemeInfo`、`SchemeFreeTyper`
- 函数和变量使用 `snake_case`
- 常量使用 `UPPER_SNAKE_CASE`

### 文档路径

- 架构和贡献文档放在 `docs/`
- 中文翻译放在 `docs/zh/`
- provider 参考文档位于 [`docs/providers.md`](../en/providers.md)
