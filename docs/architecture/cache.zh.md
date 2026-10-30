# 缓存管理

方案、catalog 与索引的存放位置，缓存根目录的解析顺序，以及离线运行得以成立的原因。

## 缓存管理

`gmlst/database/cache.py` 是核心缓存管理器。缓存根目录按以下顺序解析：显式参数、`GMLST_CACHE_DIR` 环境变量、`$CONDA_PREFIX/share/gmlst`（conda 环境）、`$VIRTUAL_ENV/.cache/gmlst`（virtualenv）、`~/.cache/gmlst`（默认回退）。每个 conda 或 virtualenv 环境默认拥有独立的缓存。

典型目录结构如下：

```text
~/.cache/gmlst/
├── <provider>/
│   └── <scheme_name>/
│       ├── <locus>.tfa 或 <locus>.fasta
│       ├── <scheme_name>.txt 或 .tsv
│       └── .meta.json
├── _catalog/
│   └── <provider>.json
└── _indexes/
    └── <provider>/
        └── <backend>/
            └── <scheme_name>/
```

### 离线运行

一旦 scheme 及其 index 已缓存，typing 就可以在不重新下载 provider 数据的情况下复用它们。`gmlst/data/catalogs/` 下的内置 catalog 也会在本地 catalog 不存在时复制到缓存中作为默认值。

## 缓存根目录的解析顺序

```bash
# 1. 显式参数优先
gmlst scheme list --cache-dir /data/gmlst

# 2. 其次是 GMLST_CACHE_DIR
export GMLST_CACHE_DIR=/data/gmlst

# 3. 再其次是与环境相关的默认值
conda run -n gmlst env | grep CONDA_PREFIX   # <prefix>/share/gmlst
echo "$VIRTUAL_ENV"                           # <venv>/.cache/gmlst

# 4. 最后回退到 ~/.cache/gmlst
```

查看某条命令实际会使用哪个目录：

```bash
gmlst config get GMLST_CACHE_DIR --format json
```

```json
{"name": "GMLST_CACHE_DIR", "value": "/home/me/.cache/gmlst", "source": "default", "is_default": true}
```

## 各目录的用途

| 路径 | 写入者 | 可以删除吗？ |
| --- | --- | --- |
| `<root>/<provider>/<scheme>/` | `scheme download`、`scheme update` | 可以，之后重新下载 |
| `<root>/_catalog/<provider>.json` | `scheme list` 刷新、`update --force` | 可以，按需重建 |
| `<root>/_indexes/<provider>/<backend>/<scheme>/` | 首次分型、`--force-reindex` | 可以，自动重建 |
| `<root>/species_fingerprints.json.gz` | `scheme update-fingerprints` | 可以，随包副本仍在 |

## 离线运行示例

准备一次，然后断网：

```bash
gmlst scheme download saureus_1
gmlst typing mlst -s saureus_1 sample.fna   # 构建索引
# 之后断网：
gmlst typing mlst -s saureus_1 another.fna  # 复用方案与索引
```

只有方案或索引缺失时，离线分型才会失败。`--force-reindex` 不需要网络，它只重建
本地文件。
