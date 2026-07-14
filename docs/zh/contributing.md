# 参与贡献

`gmlst` 是一个面向细菌基因组分型的 Python 3.12 命令行工具，支持 MLST、cgMLST、wgMLST，以及 scheme-free 工作流。欢迎提交代码、测试、文档、数据提供方集成、后端集成和问题修复。

这份指南会说明仓库结构、开发环境搭建方式，以及如何在不破坏现有架构的前提下扩展项目。命令行为以 [commands.md](commands.md) 为准，执行路径和模块边界请参考 [architecture.md](../en/architecture.md)。

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
| typing 命令 | `gmlst/commands/typing.py` |
| scheme 命令 | `gmlst/commands/scheme.py` |
| utils 命令 | `gmlst/commands/utils.py` |
| visual 命令 | `gmlst/visual/cli.py` |
| 后端协议 | `gmlst/aligners/base.py` |
| 后端注册表 | `gmlst/aligners/__init__.py` |
| provider 协议 | `gmlst/database/providers/base.py` |
| provider 注册表 | `gmlst/database/providers/__init__.py` |
| 缓存与 catalog 命名 | `gmlst/database/cache.py` |
| typing 架构说明 | `docs/architecture.md` |
| CLI 行为参考 | `docs/commands.md` |

## 开发工作流

### 1. 创建分支

建议从本地 `main` 创建一个聚焦的小分支：

```bash
git checkout main
git pull
git checkout -b docs/contributing-faq
```

分支名可以参考下面这种风格：

- `fix/minimap2-fastq-warning`
- `feat/new-provider`
- `docs/faq-cache-behavior`
- `test/cgmlst-fastq-policy`

### 2. 开始修改

常见的本地迭代方式如下：

```bash
pixi shell
pixi run start
pixi run gmlst --help
pixi run gmlst typing --help
```

如果你在做 provider 相关工作，可以先查看 catalog 和方案解析：

```bash
pixi run gmlst scheme list -p pubmlst
pixi run gmlst scheme list -p enterobase -t cgmlst
```

如果你在改 typing 逻辑，建议针对小样本或目标测试进行前后对比，尤其是 TSV 和 JSON 输出。

### 3. 运行格式化和 lint

推荐直接用项目任务：

```bash
pixi run check
```

开发过程中也可以拆开运行：

```bash
pixi run lint
pixi run format
pixi run format-check
```

### 4. 运行测试

提交 PR 前建议至少跑完整测试：

```bash
pixi run test
```

开发时可跑单文件或筛选测试：

```bash
pixi run pytest test/test_typing.py
pixi run pytest test/test_typing.py -k cgmlst
pixi run pytest -v
```

### 5. 文档和前端的额外检查

如果你改了文档结构或内部文档规范：

```bash
pixi run internal-docs-check
```

如果你修改了 `gmlst/web/frontend/`：

```bash
pixi run visual-ui-build
```

### 6. 提交变更

仓库本身没有定义额外的自定义提交格式，但使用 conventional commits 风格会更清楚，也更方便看历史。

示例：

```text
feat: add provider override docs for private BIGSdb
fix: keep cgmlst FASTQ on kma backend
docs: expand contributing guide for backend protocol
test: cover blocked scheme filtering in list command
refactor: split typing output helpers
```

常见提交流程：

```bash
git status
git add docs/contributing.md docs/faq.md docs/zh/contributing.md docs/zh/faq.md
git commit -m "docs: add contributing guide and FAQ"
```

## 代码风格指南

### 格式规则

格式配置来自 `pyproject.toml` 中的 Ruff：

- 行宽：88
- 缩进：4 个空格
- 字符串引号：双引号
- 多行集合保留 trailing comma
- 目标 Python 版本：3.12

运行命令：

```bash
pixi run lint
pixi run format
```

### Import 约定

- 使用绝对导入
- 导入顺序遵循 Ruff 规则，标准库、第三方、本地模块
- 不要使用通配符导入

示例：

```python
from pathlib import Path

import click

from gmlst.database.cache import DatabaseCache
```

### 命名约定

| 构造 | 约定 | 示例 |
| --- | --- | --- |
| 模块 | `snake_case` | `typing_output.py` |
| 函数 | `snake_case` | `prepare_sample_inputs()` |
| 变量 | `snake_case` | `scheme_name` |
| 类 | `PascalCase` | `BlastnAligner` |
| 常量 | `UPPER_SNAKE_CASE` | `HELP_SETTINGS` |

### 类型标注

所有函数签名都应带类型标注。

- 使用 `list[str]`，不要用 `typing.List[str]`
- 使用 `X | Y`，不要用 `Union[X, Y]`
- 文件路径优先使用 `pathlib.Path`

示例：

```python
def download_scheme(
    scheme_name: str,
    dest_dir: Path,
    scheme_type: str = "mlst",
) -> None:
    ...
```

### 错误处理

- 抛出具体异常
- 不要写 bare `except`
- 用户输入相关错误，优先在 CLI 层转成 Click 友好的报错
- 需要保留上下文时，使用 `raise ... from exc`

可以参考这些文件中的写法：

- `gmlst/commands/scheme.py`
- `gmlst/visual/cli.py`
- `gmlst/database/providers/base.py`

### CLI 模式

项目使用 Click，命令函数应尽量保持轻量。

- group 和 option 定义放在 `gmlst/commands/`，或像 `gmlst/visual/cli.py` 这样和功能放在一起
- 命令层负责参数解析和流程编排
- 业务逻辑放到 `gmlst/core/`、`gmlst/database/`、`gmlst/calling/`、`gmlst/visual/mst.py` 等模块
- 顶层 group 在 `gmlst/cli.py` 注册

建议参考：

- typing group：`gmlst/commands/typing.py`
- scheme group：`gmlst/commands/scheme.py`
- utils group：`gmlst/commands/utils.py`
- visual group：`gmlst/visual/cli.py`

## 添加新的比对后端

比对层使用 protocol 模式。入口定义在 `gmlst/aligners/base.py`。

### 这个协议要求什么

每个后端都要满足 `Aligner` protocol：

- `name`
- `supports_fastq`
- `check_dependencies()`
- `index(allele_fastas, index_dir)`
- `align(sample, index_path, loci, input_type)`

最重要的设计原则是，把后端自己的原生输出归一化成 `AlleleMatch` 和 `AlignmentResult`。这样下游 calling 逻辑就不需要关心具体后端差异。

### 操作步骤

1. 在 `gmlst/aligners/` 下新建模块，例如 `gmlst/aligners/mybackend.py`。
2. 实现一个类，例如 `MyBackendAligner`，并满足 `gmlst/aligners/base.py` 中的 `Aligner` protocol。
3. 把命中结果归一化成 `AlleleMatch`。
4. 返回完整的 `AlignmentResult`，包含 `sample_id`、`matches`、`failed_loci`、后端名和运行时间。
5. 在 `gmlst/aligners/__init__.py` 的 `_REGISTRY` 中注册后端。
6. 如果这个后端需要让 CLI 直接可选，确保它通过 `AVAILABLE_BACKENDS` 暴露出来。`gmlst/commands/typing.py` 和 `gmlst/commands/utils.py` 的 Click 选项会直接使用这个列表。
7. 在 `test/` 下补测试。
8. 如果用户可见行为发生变化，补文档。

### 可以参考的实现

- `gmlst/aligners/blastn.py`
- `gmlst/aligners/minimap2.py`
- `gmlst/aligners/kma.py`
- `gmlst/aligners/nucmer.py`

### 提交 PR 前建议确认

- 它支持 FASTA、FASTQ，还是两者都支持
- 依赖检查怎么做
- `index_dir` 里会生成哪些文件
- low-confidence、partial、missing locus 如何表示
- 如果涉及 multicopy 或深度信息，表现是否合理

## 添加新的数据提供方

Provider 集成也采用类似的 protocol 风格。入口在 `gmlst/database/providers/base.py`。

### 这个协议要求什么

每个 provider 都要满足 `Provider` protocol：

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

共享的元数据结构是 `SchemeInfo`。

### 操作步骤

1. 新建 `gmlst/database/providers/<provider>.py`。
2. 实现一个 provider 类，满足 `Provider` protocol。
3. 在 `list_schemes()` 中返回 `SchemeInfo` 列表。
4. 在 `download_scheme()` 中把 allele FASTA 和 profile 文件下载到目标目录。
5. 实现 `update_scheme()`，支持本地已有数据刷新。
6. 在 `gmlst/database/providers/__init__.py` 中注册 provider。
7. 用 `gmlst scheme list`、`gmlst scheme download`、`gmlst scheme update` 验证整个流程。
8. 添加测试。
9. 更新文档。

### 重要的缓存和命名规则

不要绕过 `gmlst/database/cache.py` 中的 catalog 命名逻辑。`DatabaseCache.save_catalog()` 会先在 provider 内部做命名归一化，再确保跨 provider 全局唯一。如果你新增 provider，应复用现有 cache 层，而不是自己直接定最终 `scheme_name`。

### 可以参考的实现

- `gmlst/database/providers/bigsdb.py`
- `gmlst/database/providers/enterobase.py`
- `gmlst/database/providers/cgmlst.py`

### 建议手动检查的命令

```bash
pixi run gmlst scheme list -p pubmlst
pixi run gmlst scheme list -p pasteur
pixi run gmlst scheme list -p enterobase -t cgmlst
pixi run gmlst scheme download -s saureus_1
pixi run gmlst scheme update -s saureus_1
```

## 添加 CLI 命令

大多数 CLI 修改都应该放进现有命令组里。

### 当前顶层命令组

- `typing`，定义在 `gmlst/commands/typing.py`
- `scheme`，定义在 `gmlst/commands/scheme.py`
- `utils`，定义在 `gmlst/commands/utils.py`
- `visual`，定义在 `gmlst/visual/cli.py`

这些 group 都在 `gmlst/cli.py` 注册。

### 操作步骤

1. 判断你的命令应该属于 `typing`、`scheme`、`utils`，还是 `visual`。
2. 用 `@cmd_typing.command(...)`、`@scheme_group.command(...)`、`@utils_group.command(...)` 或 `@visual_group.command(...)` 添加新的 Click 命令。
3. 把参数解析和输入校验留在 Click 层。
4. 把复杂逻辑下沉到 helper 或领域模块。
5. 如果是用户可见命令行为，更新 `docs/commands.md`。
6. 为成功和失败路径都添加测试。

### 建议遵循的模式

- 帮助文本要清楚、具体
- option 命名尽量和现有命令保持一致
- 命令函数尽量不要内联大段业务逻辑

## 测试指南

项目使用 pytest，测试根目录在 `test/`，配置见 `pyproject.toml`。

### 运行测试

```bash
pixi run test
pixi run test-v
pixi run pytest test
pixi run pytest test/test_scheme.py
pixi run pytest -k provider
```

### 编写新测试

- 测试放在 `test/` 下
- 一个文件尽量聚焦一个区域
- 修 bug 时尽量补回归测试
- fixture 保持小而明确
- 如果你改了用户可见输出，记得断言输出标记和字段

如果你修改的是这些区域，建议顺手补上对应测试：

- 后端，测试后端选择和结果归一化
- provider，测试方案列出和下载行为
- 命令层，测试 help、参数校验和错误退出
- cache，测试命名和跨 provider 交互

### 值得手动跑的基础命令

```bash
pixi run gmlst --help
pixi run gmlst typing --help
pixi run gmlst scheme --help
pixi run gmlst utils --help
pixi run gmlst visual --help
```

## 文档规则

不同类型的文档应该放在不同位置：

- 用户和开发者文档：`docs/`
- 内部活跃文档：`docs/internal/stable/`
- 内部归档文档：`docs/internal/archive/`
- 命令行为权威说明：`docs/commands.md`

如果你改了命令行为，就更新 `docs/commands.md`。如果你新增或重组文档，也记得检查 `docs/README.md`，确保索引页仍然准确。

常用交叉引用文档：

- `docs/installation.md`
- `docs/quickstart.md`
- `docs/commands.md`
- `docs/architecture.md`

## Visual Web Frontend

可视化功能由 Flask 和 Vue 共同组成：

- 命令入口：`gmlst/visual/cli.py`
- Flask app：`gmlst/visual/app.py`
- MST 逻辑：`gmlst/visual/mst.py`
- 前端源码：`gmlst/web/frontend/`
- 构建产物：`gmlst/web/static/visual/dist/`

### 前端相关工作流

```bash
pixi run visual-ui-build
pixi run gmlst visual web --help
pixi run gmlst visual web --open-browser
```

如果你修改了前端，提交 PR 前请先重新构建静态资源。

## Pull Request 流程

分支准备好后，就可以在 GitHub 上发起 Pull Request。PR 描述最好完整到让 reviewer 不需要额外猜背景。

### PR 描述建议包含的内容

- 问题是什么
- 你的处理方式是什么
- 你跑了哪些验证命令
- CLI 输出、provider 行为、backend 选择是否有变化
- 如果改了 visual web UI，再附截图

### 评审通常会关注什么

- 是否符合现有架构，尤其是 protocol 和 registry 一致性
- CLI 行为和帮助文本是否稳定
- 改动是否有测试覆盖
- 用户可见变化是否补了文档
- 命令层和领域逻辑之间是否保持合理边界

### 提交 PR 前建议运行

```bash
pixi run check
pixi run test
pixi run internal-docs-check
```

如果 PR 涉及 `gmlst/web/frontend/`，还应运行：

```bash
pixi run visual-ui-build
```

## 发布流程

如果你在准备发布版本，需要保证版本号和发布说明同步。

### 版本相关位置

- `pixi.toml`，workspace 版本
- `pyproject.toml`，Python 包版本
- `gmlst/__init__.py`，运行时版本号，前提是当前发布流程使用这里
- `CHANGELOG.md`，发布说明

### 常见发布清单

1. 更新版本号
2. 更新 `CHANGELOG.md`
3. 运行检查和测试
4. 创建 release commit
5. 打 Git tag，例如 `v0.1.0`
6. 在 GitHub 上发布 release

示例命令：

```bash
pixi run check
pixi run test
git add pyproject.toml pixi.toml CHANGELOG.md gmlst/__init__.py
git commit -m "chore: prepare release v0.1.0"
git tag v0.1.0
```

如果当前发布流程并不需要修改其中某个文件，不要为了凑清单而强行改动。以仓库的真实状态为准。

## 获取帮助

如果你不确定改动应该放在哪里，先看同一目录下最接近的现有实现，再沿用那个模式。对于用户可见行为，最好把代码、测试和文档放在同一个 PR 里一起更新。
