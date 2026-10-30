# 模块与分层

代码分布、四层架构各自负责什么，以及新增代码应遵循的放置与命名约定。

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
- 中文翻译放在 the same path with a `.zh.md` suffix
- provider 参考文档位于 [`docs/usage/providers.md`](../usage/providers.zh.md)

## 依赖方向

import 只允许单向流动：

```text
commands/ + visual/cli.py  ->  core/ calling/ novel/ schemefree/  ->  aligners/ database/ readers/
```

由此得到的实际约束：

- `gmlst/core/` 不得导入 `click`。
- `gmlst/aligners/` 不得导入 `gmlst/database/`。
- `gmlst/calling/` 只接受标准化的 `AlleleMatch`，不接触后端原始输出。

如果某个改动似乎需要反向 import，通常说明逻辑放错了层。

## 实例：新功能应该放在哪里

| 改动 | 正确位置 | 原因 |
| --- | --- | --- |
| 增加 `--min-depth` 校验 | `gmlst/commands/typing.py` | 属于用户输入策略 |
| 增加一列输出 | `gmlst/commands/typing_output.py` | 属于展示逻辑 |
| 增加一种预过滤启发式 | `gmlst/core/prefilter.py` | 纯领域逻辑 |
| 解析新的比对器输出格式 | `gmlst/aligners/<tool>.py` | 在边界处标准化 |
| 增加 provider HTTP 端点 | `gmlst/database/providers/<name>.py` | 外部集成 |
| 修改方案名称唯一性规则 | `gmlst/database/cache.py` | catalog 归属 |

一个简单的判断方法：需要 `click`、`rich` 或 `sys.exit` 的代码放
`commands/`；需要用 `subprocess` 调外部工具的代码放 `aligners/` 或
`database/download.py`；其余都属于领域逻辑。
