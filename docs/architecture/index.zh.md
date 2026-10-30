# 架构

gmlst 如何分层、一次分型如何流经系统，以及各项职责在仓库中的位置。

<div class="grid cards" markdown>

-   **架构概览**

    ---

    设计目标、系统架构图与关键结构决策。

    [架构概览](overview.zh.md)

-   **模块与分层**

    ---

    源码树、四层架构，以及代码放置与命名约定。

    [模块与分层](modules.zh.md)

-   **CLI 层**

    ---

    Click 注册、`typing` 分发与命令层策略。

    [CLI 层](cli.zh.md)

-   **分型流水线**

    ---

    方案解析、索引、预过滤、比对、调用、ST 判定与 FASTA/FASTQ 分流。

    [分型流水线](typing-pipeline.zh.md)

-   **比对后端**

    ---

    `Aligner` 协议、`AlleleMatch` 标准化与四个后端适配器。

    [比对后端](backends.zh.md)

-   **数据 provider**

    ---

    `Provider` 协议、运行时注册表与 catalog 命名规则。

    [数据 provider](providers.zh.md)

-   **缓存管理**

    ---

    缓存布局、根目录解析、索引复用与离线运行。

    [缓存](cache.zh.md)

-   **Novel 与无方案工作流**

    ---

    新等位基因提取、自定义方案与 `tgmlst` 引擎。

    [工作流](workflows.zh.md)

-   **可视化**

    ---

    Flask API、MST 计算与 Vue 前端。

    [可视化](visualization.zh.md)

</div>
