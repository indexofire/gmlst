# 配置

最常用的环境变量，以及临时文件写到哪里。

## 配置问题

### 哪些环境变量最常用？

最常见的是：

- `GMLST_CACHE_DIR`，覆盖缓存根目录（默认从 conda/venv 自动检测）
- `GMLST_TMPDIR`，覆盖临时目录
- 各种 provider URL 覆盖变量，例如 `GMLST_PUBMLST_BASE_URL`

示例：

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

### 临时文件写到哪里？

默认写到系统临时目录。你可以这样覆盖：

```bash
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

## 先查再改

```bash
gmlst config show                         # 分组表格，密钥脱敏
gmlst config get GMLST_CACHE_DIR          # 显示来源：环境变量/文件/默认值
gmlst config get GMLST_CACHE_DIR --format json
gmlst config env                          # 可直接 source 的 export 行
```

| 变量 | 默认值 | 适用场景 |
| --- | --- | --- |
| `GMLST_CACHE_DIR` | 与环境相关的目录 | 跨环境共享同一缓存 |
| `GMLST_TMPDIR` | 系统临时目录 | 大批量任务使用独立 scratch 盘 |
| `GMLST_PUBMLST_API_KEY` | 未设置 | 访问 2024 年后的 PubMLST 数据 |
| `GMLST_PASTEUR_API_KEY` | 未设置 | 访问 2024 年后的 Pasteur 数据 |
| `GMLST_PRIVATE_BIGSDB_URL` | 未设置 | 自托管 BIGSdb provider |

密钥写入 `~/.config/gmlst/env.sh`（权限 600），`config show`/`config get` 默认
掩码显示，只有 `--reveal` 才输出明文。

## 持久化配置

```bash
gmlst config set GMLST_TMPDIR /scratch/gmlst
gmlst config init          # 只需一次：把 source 行加入 shell rc
source ~/.config/gmlst/env.sh
```

provider URL 变量在导入时读取，因此运行 gmlst 前要先 `source` 该文件。
