# 可视化指南

本文介绍 `gmlst` 的本地可视化工作流，包括 Web 服务器启动、输入格式、MST 构建、布局切换、元数据着色以及前端构建方式。若要先从 CLI 导出适合可视化的 profile 表，请结合 [novel_workflow.md](novel_workflow.md) 和 [commands.md](commands.md) 一起阅读。

## 概述

`visual` 模块提供一个本地 Web 界面，用于把 MLST 或 cgMLST 的 profile 表构建成 MST（Minimum Spanning Tree，最小生成树）并进行交互式查看。

它特别适合以下场景：

- 查看样本如何按 allele profile 聚类
- 根据元数据列给节点着色
- 比较不同 missing token 处理方式对距离的影响
- 导出适合汇报或论文使用的 SVG 图

## 启动服务器

最常用的启动方式是：

```bash
gmlst visual web --open-browser
```

常见参数：

- `--host`，默认 `127.0.0.1`
- `--port`，默认 `8787`

示例：

```bash
# 使用默认地址并自动打开浏览器
gmlst visual web --open-browser

# 使用自定义端口
gmlst visual web --port 9000

# 明确需要远程访问时绑定所有网卡
gmlst visual web --host 0.0.0.0 --port 8787
```

只有在可信网络环境中才建议这样做。这个可视化服务更适合作为本地便利界面使用，而不是带认证能力的对外服务。

典型启动日志：

```text
Serving MST web app on http://127.0.0.1:8787
```

## 上传数据

界面支持两类常见 profile 表：

1. `gmlst` 生成的 profile 表
2. 第一列为 `#Strain` 的 GrapeTree 风格文件

解析器可以自动识别 tab、逗号和分号分隔，因此 TSV 是最常见形式，但 CSV 风格文件也可以导入。

这意味着你既可以直接上传分型结果表，也可以先从 CLI 导出 GrapeTree 格式再导入。

GrapeTree 风格表头示例：

```tsv
#Strain	dnaA	ftsZ	gyrB	...
ST1	12	44	109	...
ST2	12	44	111	...
```

带元数据列的示例：

```tsv
#Strain	dnaA	ftsZ	gyrB	Source	Ward	Year
ST1	12	44	109	blood	ICU	2024
ST2	12	44	111	wound	WardA	2024
```

元数据既可以直接嵌入同一个表，也可以作为单独的 metadata 文件按样本 ID 关联后上传。

## 构建 MST

加载 profile 表后，界面会根据样本之间的 allele 差异构建最小生成树。

典型流程如下：

1. 启动 `gmlst visual web`
2. 上传或粘贴 profile 表
3. 选择 MST 相关参数
4. 渲染图形
5. 如有需要导出 SVG

MST 在这里有三个主要价值：

- 用紧凑方式展示样本间最近邻关系
- 很适合基于 cgMLST profile 的比较
- 能在进入更复杂系统发育分析之前，先做快速交互式探索

## 布局选项

Web UI 支持两种布局：

- `tree`
- `radial`

### Tree 布局

适合强调分支结构、层次关系和传播链条的场景。

### Radial 布局

适合从中心向外查看整体结构，尤其是更像星状或更密集的数据集。

经验上：

- 中小规模暴发集合往往更适合 `tree`
- 更密集或更放射状的数据集通常更适合 `radial`

## 节点着色

界面可以根据上传表中的元数据列给节点着色。

常见可用字段包括：

- 样本来源
- 病区/科室
- 年份
- 地区
- 暴发标签

节点着色的价值在于：

- 快速判断聚类是否与流行病学信息一致
- 很容易识别混合来源的 cluster
- 让原本只有拓扑结构的图更容易解释

## Missing Token Penalty

可视化工作流提供 missing-token penalty 开关，用于处理 `LNF`、`NIPH`、`NIPHEM` 等特殊值，也就是 profile 表中常见的非精确或缺失类位点标记。

这个设置会影响缺失位点或特殊状态位点在距离计算中的权重。

通常可以对比两种视图：

- 更严格：缺失值也计入惩罚
- 更宽松：弱化缺失值的影响

当数据中混有高质量组装和部分不完整 profile 时，这种比较尤其有帮助。

## 导出

界面支持把当前图导出为 SVG，同时前端还支持导出图结构、会话状态和表格数据的 JSON/TSV。

SVG 的优势在于：

- 可无损缩放，适合论文和报告
- 后续可在矢量图软件中继续调整
- 文本标签通常比截图更清晰

## GrapeTree 导出 CLI

如果你想先从命令行生成适合 MST 工具的 profile 表，可以先导出 GrapeTree 格式：

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

这个文件使用 `#Strain` 表头，可直接进入可视化流程。

示例：

```tsv
#Strain	arcC	aroE	glpF	gmk	pta	tpi	yqiL
ST1	1	1	1	1	1	1	1
STN1	n1	7	3	9	4	2	1
```

## 架构简介

可视化系统由轻量级 Python Web 后端和 Vue 前端组成。

后端路由包括：

- `/`
- `/health`
- `/api/mst`
- `/api/distance-matrix`
- `/api/allele-heatmap`
- `/api/locus-diff`
- `/api/compare-results`

前端源码目录：

```text
gmlst/web/frontend/
```

构建后的静态资源目录：

```text
gmlst/web/static/visual/dist/
```

整体上可以理解为：

- Flask 负责提供页面和 API
- Vue 3 负责浏览器中的交互界面
- Vite 负责打包前端静态资源

## 构建前端

如果你修改了前端界面，需要重新构建前端资源。

推荐命令：

```bash
pixi run visual-ui-build
```

也可以直接使用 npm：

```bash
npm --prefix gmlst/web/frontend run build
```

如果只是普通用户使用可视化功能，并不需要手动构建前端，因为程序会直接使用 `gmlst/web/static/visual/dist/` 中的预构建资源。
