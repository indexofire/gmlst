# 数据 provider

`Provider` 协议、运行时注册表，以及保证方案名称全局唯一的 catalog 命名规则。

## 数据 provider 架构

### Provider 协议

`gmlst/database/providers/base.py` 定义了 `Provider` `Protocol`。和 aligner 一样，它也是结构化接口。

每个 provider 需要暴露：

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

每个 scheme 用 `gmlst/database/providers/base.py` 中的 `SchemeInfo` 表示，字段包括：

- `scheme_name`
- `display_name`
- `organism`
- `scheme_type`
- `n_loci`
- `provider`
- `extra`，用于保存 URL、目录名等 provider 特有信息

### Provider 注册表

`gmlst/database/providers/__init__.py` 构建运行时注册表，固定包含：

- `pubmlst`，实现位于 `gmlst/database/providers/bigsdb.py`
- `pasteur`，实现位于 `gmlst/database/providers/bigsdb.py`
- `enterobase`，实现位于 `gmlst/database/providers/enterobase.py`
- `cgmlst`，实现位于 `gmlst/database/providers/cgmlst.py`

如果设置了 `GMLST_PRIVATE_BIGSDB_URL`，注册表还会动态添加一个私有 BIGSdb provider。

### Catalog 管理和全局唯一命名

`gmlst/database/cache.py` 负责 `_catalog/` 下的 provider catalog 缓存，并保证不同 provider 之间的 scheme 名称全局唯一。

这里有两层逻辑：

1. `_normalize_scheme_names()` 在单个 provider 内部先标准化命名。
2. `save_catalog()` 再和其他 provider 的 catalog 对比，必要时继续增加数字后缀。

因此不同 provider 中同一物种的 scheme，仍然可以稳定地得到 `spneumoniae_1`、`spneumoniae_2`、`spneumoniae_3` 这类不冲突的名字。

## 最小 provider 骨架

```python
from pathlib import Path

from gmlst.database.providers.base import SchemeInfo


class MyProvider:
    name = "myprovider"
    label = "My Provider"

    def list_schemes(self, scheme_type: str = "mlst") -> list[SchemeInfo]:
        return [
            SchemeInfo(
                scheme_name="myorg_1",
                display_name="My organism MLST",
                organism="My organism",
                scheme_type="mlst",
                n_loci=7,
                provider=self.name,
                extra={"locus_url": "https://example.org/loci"},
            )
        ]

    def download_scheme(self, scheme_name, dest_dir: Path, **kwargs) -> None:
        ...  # 写入 <locus>.tfa、profile 表与 .meta.json

    def update_scheme(self, scheme_name, dest_dir: Path, **kwargs) -> bool:
        ...  # 远端内容变化时返回 True
```

## catalog 条目示例

`save_catalog()` 之后，provider catalog 是 scheme 对象的 JSON 数组：

```json
[
  {
    "scheme_name": "saureus_1",
    "display_name": "Staphylococcus aureus MLST",
    "organism": "Staphylococcus aureus",
    "scheme_type": "mlst",
    "n_loci": 7,
    "provider": "pubmlst",
    "extra": {
      "scheme_url": "https://rest.pubmlst.org/db/pubmlst_saureus_seqdef/schemes/1"
    }
  }
]
```

## 命名流程

两个 provider 都提供 7 个 locus 的 *S. pneumoniae* 方案：

```text
pubmlst  -> spneumoniae_1
pasteur  -> spneumoniae_2   # save_catalog() 递增后缀
```

名称会写入 `name_history`，因此后续 catalog 刷新即使上游列表顺序变化，也会复用
同名。新方案取下一个空闲编号，退役名称不会再次使用。
