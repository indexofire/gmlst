# 扩展 gmlst

新增比对后端、数据提供方与 CLI 命令的分步指南，包括评审时会被问到的问题。

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
5. 如果是用户可见命令行为，更新 `docs/usage/cli/index.md`。
6. 为成功和失败路径都添加测试。

### 建议遵循的模式

- 帮助文本要清楚、具体
- option 命名尽量和现有命令保持一致
- 命令函数尽量不要内联大段业务逻辑

## 后端检查清单

```text
[ ] 类满足 Aligner 协议（name、supports_fastq、check_dependencies、index、align）
[ ] 原生输出标准化为 AlleleMatch（identity 为百分比，coverage 为 0-1）
[ ] 无命中的 locus 填入 AlignmentResult.failed_loci
[ ] 在 gmlst/aligners/__init__.py 中注册
[ ] 通过 AVAILABLE_BACKENDS 暴露给 CLI 选项
[ ] 使用小型 allele 集合的单元测试
```

## Provider 检查清单

```text
[ ] name / label 属性
[ ] list_schemes() 返回 SchemeInfo 对象
[ ] download_scheme() 写入 <locus>.tfa、profile 表与 .meta.json
[ ] 内容变化时 update_scheme() 返回 True
[ ] 在 gmlst/database/providers/__init__.py 中注册
[ ] 不自行分配最终名称（交给 DatabaseCache）
[ ] 手动验证：scheme list / download / update
```

## CLI 命令示例

```python
@utils_group.command("count-loci")
@click.argument("scheme")
def cmd_count_loci(scheme: str) -> None:
    """Print the number of loci in a cached scheme."""
    info = DatabaseCache().get_scheme(scheme)
    click.echo(info.n_loci)
```

然后在 `test/test_utils_commands.py` 中添加测试，并在 `docs/usage/cli/index.md` 与
其 `.zh.md` 版本中补充文档。

## 一图看懂后端协议

```python
class Aligner(Protocol):
    name: str
    supports_fastq: bool

    def check_dependencies(self) -> None: ...
    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path: ...
    def align(self, sample, index_path, loci, input_type) -> AlignmentResult: ...
```

只要类满足这个形状，流水线就能使用它，无需直接 import 你的模块。
