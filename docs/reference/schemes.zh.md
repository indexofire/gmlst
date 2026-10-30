# 方案管理问题

方案名称、下载失败、缓存位置、被屏蔽条目，以及自托管 BIGSdb 端点。

## 方案管理问题

### `Scheme 'X' not found in catalog`

你传入的必须是规范的 `scheme_name`，不是单纯的物种名。

先列出可用方案：

```bash
gmlst scheme list
gmlst scheme list -p pubmlst
gmlst scheme list -p enterobase -t cgmlst
```

然后使用精确名称，例如：

```bash
gmlst scheme download -s saureus_1
```

### 下载方案失败

常见原因：

- 临时网络故障
- provider 端服务不稳定或限流
- 当前下载工具在你的环境里效果不好

可以尝试切换下载工具：

```bash
gmlst scheme download -s saureus_1 --download-tool curl
gmlst scheme download -s saureus_1 --download-tool requests
gmlst scheme download -s saureus_1 --download-tool wget
```

如果你处在代理或防火墙环境里，也要确认 provider 端地址本身可以访问。

### 缓存目录在哪里？

缓存根目录会自动检测：conda 环境使用 `$CONDA_PREFIX/share/gmlst`，virtualenv 使用 `$VIRTUAL_ENV/.cache/gmlst`，默认回退到 `~/.cache/gmlst`。每个环境拥有独立的缓存。

你也可以覆盖它：

```bash
export GMLST_CACHE_DIR="$HOME/work/gmlst-cache"
gmlst scheme list
```

如果需要在多个 conda 环境间共享缓存：

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### 我想只对单条命令改缓存路径

部分命令支持 `--cache-dir`：

```bash
gmlst scheme list --cache-dir /tmp/gmlst-cache
gmlst scheme download -s saureus_1 --cache-dir /tmp/gmlst-cache
```

### `scheme list` 里缺少某个方案

它可能被 `gmlst/data/blocked_schemes.json` 屏蔽了。

这个文件会影响 list、show、download、update 等流程。如果你是项目维护者，需要调整屏蔽策略，请谨慎编辑这个 JSON。

### 如何连接自托管 BIGSdb？

可以用环境变量指定自定义 BIGSdb 地址：

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```

内置 provider 的 base URL 也可以覆盖：

```bash
export GMLST_PUBMLST_BASE_URL="https://rest.pubmlst.org/db"
export GMLST_PASTEUR_BASE_URL="https://bigsdb.pasteur.fr/api/db"
```

## 找到规范名称

```bash
gmlst scheme search aureus
gmlst scheme list -n aureus
```

搜索会匹配方案名、物种、描述与 provider。第一列的值就是 `-s/--scheme` 需要的名称。

## 从下载不完整中恢复

```bash
gmlst scheme remove saureus_1 -y
gmlst scheme download saureus_1 --download-tool curl -x 2
```

`-x 2` 限制并发连接数，可缓解 provider 在高负载下返回 HTTP 429 的问题。

## 查看已缓存的方案

```bash
gmlst scheme show -s saureus_1
gmlst scheme show -s saureus_1 -a          # 每个 locus 的等位基因数
gmlst scheme show -s saureus_1 -f json     # 机器可读
```

## 跨环境共享缓存

默认每个 conda/venv 环境有独立缓存。若要共享下载内容：

```bash
# 写入 ~/.config/gmlst/env.sh
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"

gmlst scheme list            # 所有环境看到同一批方案
```

运行一次 `gmlst config init`，新的 shell 会自动加载该文件。
