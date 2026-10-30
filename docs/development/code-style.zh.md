# 代码风格

格式、import、命名、类型标注、错误处理与 CLI 模式，均附示例。

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

## 错误处理示例

```python
# 推荐：抛出具体异常，保留上下文
try:
    data = path.read_text()
except FileNotFoundError as exc:
    raise FileNotFoundError(f"Input file not found: {path}") from exc

# 不推荐：吞掉原因
try:
    data = path.read_text()
except Exception:
    return None
```

## CLI 示例

```python
@typing_group.command("mlst")
@click.argument("samples", nargs=-1, required=True)
@click.option("--scheme", "-s", help="Scheme name.")
def cmd_mlst(samples: tuple[str, ...], scheme: str | None) -> None:
    """Type assemblies with classical MLST."""
    if scheme is None and not samples:
        raise click.UsageError("provide at least one sample")
    run_typing(samples=samples, scheme=scheme)
```

解析与校验放在 Click 函数里，工作流由 `run_typing()` 负责。评审者应该能在一屏内
读完命令主体。

## 文档字符串与类型标注示例

```python
def normalise_call(match: AlleleMatch, threshold: float = 0.95) -> str:
    """Render one allele call in tseemann-compatible notation.

    Parameters
    ----------
    match:
        Normalised backend hit for a single locus.
    threshold:
        Minimum coverage for a partial call to be considered complete.

    Returns
    -------
    str
        ``"23"``, ``"~23"``, ``"15?"``, or ``"-"``.
    """
```
