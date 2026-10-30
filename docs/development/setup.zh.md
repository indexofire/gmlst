# 开发环境

如何安装工具链、验证环境，并找到负责你想修改的行为的模块。

## 欢迎

这个项目的目标，是在同一套 CLI 下统一多种分型模式、多种比对后端和多种公共方案来源。好的贡献通常有这些特点：

- 保持 CLI 行为稳定、可预测
- 让 Click 命令层保持轻薄
- 复用现有 protocol 和 registry，而不是新增临时分支逻辑
- 保持 TSV、JSON 等机器可读输出稳定
- 行为变化时补上测试
- 用户可见变化时同步更新文档

如果你是第一次参与，不一定要从大功能开始。下面这些切入点都很适合：

- 改进 `docs/` 下的文档
- 在 `test/` 下补一个回归测试
- 优化 `gmlst/commands/` 中的报错信息
- 改进 `gmlst/database/providers/` 中的 provider 解析逻辑
- 改进 `gmlst/aligners/` 中的后端结果归一化

## 开发环境搭建

### 推荐使用 pixi

Pixi 是这个仓库的标准开发环境，因为它会同时管理 Python 依赖和外部生信工具。

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi shell
```

然后在 pixi 环境里把项目以 editable 模式安装：

```bash
pixi run install-dev
```

### 验证环境

开始改代码前，建议先跑一遍这些检查：

```bash
pixi run gmlst --version
pixi run gmlst --help
pixi run gmlst utils check -b blastn
pixi run gmlst utils check -b minimap2
pixi run gmlst utils check -b kma
pixi run gmlst utils check -b nucmer
```

### 常用开发任务

这些任务定义在 `pixi.toml` 中：

```bash
pixi run start
pixi run lint
pixi run format
pixi run check
pixi run test
pixi run test-v
pixi run internal-docs-check
pixi run visual-ui-build
```

### Python 与打包信息

- Python 版本：3.12
- 包管理：pixi
- 构建后端：hatchling，见 `pyproject.toml`
- CLI 入口：`gmlst.cli:main`
- 代码格式化与 lint：Ruff
- 测试框架：pytest

## 项目结构

下面是贡献时最常接触的目录：

```text
gmlst/
├── aligners/          # 后端适配层，把原生比对结果归一化为 AlleleMatch
├── calling/           # 等位基因调用、置信度评估、ST 查找
├── commands/          # typing、scheme、utils 等 Click 命令组
├── core/              # 索引、预过滤、排序、精修等核心流程
├── data/              # 打包进项目的静态数据、catalog、blocked schemes
├── database/          # 缓存、下载、provider 实现
├── novel/             # novel allele 提取与自定义方案工作流
├── readers/           # FASTA、FASTQ、样本输入读取
├── schemefree/        # tgmlst 工作流及相关工具
├── visual/            # Flask 侧可视化入口与 MST 逻辑
├── web/               # Vue + Vite 前端源码和构建产物
test/                  # pytest 测试目录
scripts/               # 开发、分析、验证脚本
docs/                  # 用户和开发者文档
```

按任务找入口时，可以从这些文件开始：

| 贡献目标 | 入口文件 |
| --- | --- |
| 顶层 CLI 注册 | `gmlst/cli.py` |
| typing 命令 | `gmlst/commands/typing.py`（tgmlst：`typing_schemefree.py`，`--guess`：`typing_guess_run.py`） |
| scheme 命令 | `gmlst/commands/scheme.py`（`update`：`scheme_update.py`，`update-fingerprints`：`scheme_fingerprints.py`） |
| utils 命令 | `gmlst/commands/utils.py` |
| visual 命令 | `gmlst/visual/cli.py` |
| 后端协议 | `gmlst/aligners/base.py` |
| 后端注册表 | `gmlst/aligners/__init__.py` |
| provider 协议 | `gmlst/database/providers/base.py` |
| provider 注册表 | `gmlst/database/providers/__init__.py` |
| 缓存与 catalog 命名 | `gmlst/database/cache.py` |
| typing 架构说明 | `docs/architecture/typing-pipeline.md` |
| CLI 行为参考 | `docs/usage/cli/index.md` |

## 备选：使用 conda 环境文件

如果更习惯 conda，仓库自带的 `environment.yml` 会安装同样的工具链：

```bash
conda env create -f environment.yml
conda activate gmlst
pip install -e .            # 以可编辑模式安装当前 checkout
```

## 第一次贡献示例

```bash
git checkout -b docs/installation-notes
# 编辑 docs/installation/guide.md 与 docs/installation/guide.zh.md
pixi run mkdocs build --strict
pixi run check
git add docs/installation/guide.md docs/installation/guide.zh.md
git commit -m "docs: clarify pixi install steps"
```

在改动流水线之前，从文档和小测试入手最容易熟悉代码布局。

## 环境检查清单

| 检查项 | 命令 | 期望结果 |
| --- | --- | --- |
| Python 版本 | `pixi run python --version` | `Python 3.12.x` |
| CLI 入口 | `pixi run gmlst --version` | 输出包版本 |
| 后端可用性 | `pixi run gmlst utils check -b blastn` | `[OK]` |
| 可编辑安装 | `pixi run pip show gmlst` | 位置指向当前 checkout |
