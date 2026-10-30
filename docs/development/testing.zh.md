# 测试

运行测试套件、编写聚焦测试，以及提 PR 前值得手动验证的场景。

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

## 测试示例

```python
from pathlib import Path

from gmlst.readers.sample import detect_sample


def test_detect_paired_fastq(tmp_path: Path) -> None:
    r1 = tmp_path / "sample_R1.fastq.gz"
    r2 = tmp_path / "sample_R2.fastq.gz"
    r1.write_bytes(b"")
    r2.write_bytes(b"")

    sample = detect_sample(r1)

    assert sample.input_type == "fastq"
    assert sample.mate_path == r2
```

## 优先使用这些 fixture

| Fixture | 用途 |
| --- | --- |
| `tmp_path` | 缓存目录、输出文件、伪造方案 |
| `DummyScheme` / `DummyCache` | 无需网络的 typing 测试 |
| `monkeypatch` | 环境变量与工具查找 |

测试中避免真实下载。需要方案时，在 `tmp_path` 下构造一个两 locus 的 fixture，并
用 `--cache-dir` 指向它。

## 测试目录结构

```text
test/
  conftest.py            共享 fixture
  test_typing.py         核心分型行为
  test_scheme.py         方案命令与 catalog 逻辑
  test_*_provider.py     provider 解析与下载
  test_visual_command.py 可视化命令与 MST 导出
  schemefree/            tgmlst 专用套件
```

测试名应描述行为，而不是函数名：

```python
def test_cgmlst_fastq_forces_kma_backend(...): ...
def test_blocked_scheme_is_hidden_from_list(...): ...
```
