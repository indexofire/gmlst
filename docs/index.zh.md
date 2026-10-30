# gmlst 文档

`gmlst` 是一个快速的 Python 3.12 命令行工具，用于细菌基因组分型，支持经典
MLST、大规模 cgMLST/wgMLST 方案以及无方案发现流程。它可以对组装基因组和双端
原始 reads 分型，驱动多种比对后端，从多个公共数据源下载方案，并内置本地 MST 可视化。

## 从这里开始

| 我想… | 阅读 |
| --- | --- |
| 安装 gmlst 并跑第一个样本 | [快速开始](installation/quick-start.zh.md) |
| 一次性安装全部外部工具 | [安装指南](installation/guide.zh.md) |
| 配置缓存、数据源地址与 API key | [配置参考](installation/configuration.zh.md) |
| 在 Docker、Nextflow 或 Snakemake 中使用 | [流水线集成](installation/pipelines.zh.md) |
| 查所有 CLI 参数 | [CLI 参考](usage/cli/index.zh.md) |
| 理解 `typing` 命令 | [分型](usage/cli/typing.zh.md) |
| 选择比对后端 | [比对后端](usage/backends.zh.md) |
| 浏览或下载方案 | [数据源](usage/providers.zh.md) |
| 调优大规模 cgMLST 运行 | [cgMLST 指南](usage/cgmlst.zh.md) |
| 提取新等位基因并构建自定义方案 | [Novel 工作流](usage/novel-workflow.zh.md) |
| 在浏览器中构建 MST | [可视化](usage/visualization.zh.md) |
| 不指定 `-s` 自动检测物种 | [指纹数据库](usage/fingerprint-database.zh.md) |
| 安全消费 JSON 输出 | [JSON 输出信封](usage/cli/index.zh.md#json-输出信封) |
| 排查问题 | [常见问题](reference/faq.zh.md) |

## gmlst 做什么

```text
FASTA 组装 / 双端 FASTQ
        │
        ▼
   k-mer 预过滤 ── blastn · minimap2 · nucmer · kma
        │
        ▼
   等位基因调用（精确 · 新 · 部分）── ST 判定 ── TSV / JSON
```

两个分型入口共用同一套引擎：

- `gmlst typing mlst|cgmlst` —— 基于方案分型，可使用公共、缓存或自定义方案。
- `gmlst typing tgmlst` —— 无方案等位基因发现，可保存为可复用方案。

## 安装一览

```bash
pip install gmlst                 # Python 3.12

# 或在仓库内一次性安装全部外部工具
conda env create -f environment.yml
```

四个比对后端（`blastn`、`minimap2`、`nucmer`、`kma`）都是外部工具，完整列表与
平台说明见[安装指南](installation/guide.zh.md)。

## 设计原则

- **后端无关的调用。** 所有比对器共用一套归一化结果模型，调用与 ST 判定不依赖后端。
- **以证据为先。** 精确、新、部分、冲突调用分别呈现，每个样本附带 0–100 质量分。
- **缓存优先。** 方案与索引会被复用，重复运行和离线运行都不需要网络。
- **面向自动化。** JSON 带版本信封、stdout 只输出数据、退出码语义稳定，便于脚本和
  AI 智能体驱动。
- **尽量无人值守。** `--guess` 可以在零交互的情况下完成混合物种批处理。

## 项目结构

```text
gmlst/
  cli.py            Click 入口
  commands/         typing、scheme、utils、config、visual 命令
  core/             流水线、预过滤、精确哈希、精炼、排序
  aligners/         blastn、minimap2、nucmer、kma 适配器
  calling/          等位基因调用、置信度、ST 判定
  database/         数据源、catalog 缓存、下载
  schemefree/       tgmlst 引擎
  visual/           MST 构建器与 Flask API
  web/              Vue 前端与模板
docs/               中英文档
test/               单元与集成测试
```

## 许可证

MIT。项目概览与[更新日志](https://github.com/indexofire/gmlst/blob/main/CHANGELOG.md)
见仓库首页。
