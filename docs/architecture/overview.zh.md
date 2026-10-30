# 架构概览

设计目标、系统架构图，以及主要结构选择背后的取舍。建议先读完本页，再看更细的模块页面。

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

## 阅读指南

| 问题 | 页面 |
| --- | --- |
| 设计目标是什么？ | 本页 |
| 新模块或新文件应该放在哪里？ | [模块与分层](modules.zh.md) |
| 某个参数或策略由哪一层负责？ | [CLI 层](cli.zh.md) |
| 一个样本如何变成一行 TSV？ | [分型流水线](typing-pipeline.zh.md) |
| 如何新增比对后端？ | [比对后端](backends.zh.md) |
| 方案如何被发现和命名？ | [数据 provider](providers.zh.md) |
| 数据缓存在哪里，离线如何运行？ | [缓存管理](cache.zh.md) |
| Novel allele 与 `tgmlst` 如何工作？ | [工作流](workflows.zh.md) |
| MST 如何构建并提供服务？ | [可视化](visualization.zh.md) |

## 追踪一条命令经过的各层

`gmlst typing mlst -s saureus_1 sample.fna` 会依次经过每一层：

| 步骤 | 层 | 代码路径 |
| --- | --- | --- |
| 1. 解析 `typing mlst -s ...` | CLI | `gmlst/cli.py` → `gmlst/commands/typing.py` |
| 2. 解析 `saureus_1`（缺失时下载） | CLI + 基础设施 | `gmlst/commands/typing_scheme.py` → `gmlst/database/cache.py` |
| 3. 检测 FASTA 并规划索引 | 基础设施 | `gmlst/readers/sample.py`、`gmlst/core/indexing.py` |
| 4. 比对等位基因 | 基础设施 | `gmlst/aligners/blastn.py`（MLST 默认） |
| 5. 将命中转为调用 | 领域 | `gmlst/calling/allele.py` |
| 6. 判定 ST | 领域 | `gmlst/calling/st_lookup.py` |
| 7. 渲染 TSV | 展示 | `gmlst/commands/typing_output.py` |

依赖不允许反向：`calling/` 不导入 Click，`aligners/` 也不了解方案与缓存布局。
保持这种单向依赖，才能让 CLI 保持轻薄、让领域层可独立测试。

## 取舍一览

| 选择 | 收益 | 代价 |
| --- | --- | --- |
| 使用 `Protocol` 接口 | 后端与 provider 无需继承基类 | 契约靠文档约束，而非运行时强制 |
| 标准化 `AlleleMatch` | 所有后端共用一条调用路径 | 后端特有证据需要显式映射 |
| FASTQ 策略放在 CLI 层 | 行为可见、易于修改 | 策略无法在 CLI 之外复用 |
| catalog 与索引缓存优先 | 重复运行快、可离线 | 失效需要显式操作（`--force-reindex`、`scheme update`） |
