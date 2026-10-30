# 开发工作流

分支策略、编辑循环、lint、测试、文档与前端检查，以及提交约定。

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
git add docs/development/setup.md docs/reference/installation.md \
  docs/development/setup.zh.md docs/reference/installation.zh.md
git commit -m "docs: add contributing guide and FAQ"
```

## 完整工作流示例

```bash
git checkout main && git pull
git checkout -b fix/minimap2-fastq-warning

# 修改代码与测试
pixi run check                 # ruff lint + 格式检查
pixi run pytest test/test_typing.py -q
pixi run test                  # 提 PR 前跑完整套件

git status
git add gmlst/commands/typing.py test/test_typing.py
git commit -m "fix: keep cgmlst FASTQ on kma backend"
git push -u origin fix/minimap2-fastq-warning
```

## 不同改动类型对应的检查

| 改动 | 最低检查 |
| --- | --- |
| 仅文档 | `pixi run mkdocs build --strict` |
| 仅 Python | `pixi run check && pixi run test` |
| 前端 | `pixi run visual-ui-build` |
| CLI 行为 | 测试 + 更新 `docs/usage/cli/` |
| Provider | 手动跑 `scheme list/download/update` + 测试 |

## 提交信息示例

```text
feat: add private BIGSdb provider label
fix: keep cgmlst FASTQ on kma backend
docs: split architecture guide by topic
test: cover blocked scheme filtering
refactor: extract typing run helpers
```
