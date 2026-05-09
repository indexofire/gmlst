# Providers 文档

本文说明 `gmlst` 支持的 scheme provider、它们在代码中的实现方式，以及各 provider 的特殊行为。系统整体设计请参考 [`docs/architecture.md`](./architecture.md)。

## 概览

provider 是 `gmlst scheme list`、`gmlst scheme download` 和 `gmlst scheme update` 背后的数据来源。每个 provider 都负责提供 scheme catalog，并下载 typing 所需的 allele FASTA 与 profile 数据。

`gmlst` 支持多个 provider，因为单一上游并不能覆盖所有物种、所有命名方式，也不能覆盖所有 scheme 类型。provider 层让同一套 CLI 和 typing engine 可以统一面对：

- 公共 BIGSdb 实例
- 直接下载型 catalog
- cgMLST 专用的批量 ZIP 来源
- 由 novel allele 工作流产生的本地自定义 scheme
- 自建 BIGSdb 实例

## Provider 对比表

| Provider | 代码路径 | 上游 URL | 主要 scheme 类型 | 覆盖环境变量 |
|---|---|---|---|---|
| PubMLST | `gmlst/database/providers/bigsdb.py` | `https://rest.pubmlst.org/db` | MLST，部分 cgMLST，部分 wgMLST | `GMLST_PUBMLST_BASE_URL` |
| Pasteur | `gmlst/database/providers/bigsdb.py` | `https://bigsdb.pasteur.fr/api/db` | MLST，部分 cgMLST，部分 wgMLST | `GMLST_PASTEUR_BASE_URL` |
| Enterobase | `gmlst/database/providers/enterobase.py` | `https://enterobase.warwick.ac.uk/schemes` | MLST，cgMLST，wgMLST，rMLST | 无 |
| cgMLST.org | `gmlst/database/providers/cgmlst.py` | `https://www.cgmlst.org/ncs/1000` | cgMLST | 无 |
| Local | `gmlst/commands/scheme.py` + `gmlst/database/cache.py` | 仅本地缓存 | 自定义 MLST/cgMLST/wgMLST | 缓存根目录由 `GMLST_CACHE_DIR` 控制 |
| Private BIGSdb | 通过注册表使用 `gmlst/database/providers/bigsdb.py` | 用户自定义 BIGSdb URL | 取决于部署站点 | `GMLST_PRIVATE_BIGSDB_URL` |

## 共享 provider 架构

### Provider 接口

所有 provider 都遵循 `gmlst/database/providers/base.py` 中定义的 `Provider` `Protocol`。每个 provider 都需要定义：

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

同文件中的 `SchemeInfo` 是统一的 scheme 元数据对象，供 CLI 和 catalog cache 使用。

### 注册与运行时选择

`gmlst/database/providers/__init__.py` 创建运行时注册表。`gmlst/database/cache.py` 通过 `get_provider()` 按名称获取具体 provider，并完成列表、下载、更新等动作。

### Catalog 缓存

provider catalog 会被缓存为：

```text
~/.cache/gmlst/_catalog/<provider>.json
```

`gmlst/database/cache.py` 还会在写入 catalog 时重写名称，确保不同 provider 之间的 scheme 名称全局唯一。

## PubMLST

### 基本信息

- provider key: `pubmlst`
- 注册位置: `gmlst/database/providers/__init__.py`
- 实现位置: `gmlst/database/providers/bigsdb.py`
- 默认 base URL: `https://rest.pubmlst.org/db`
- 覆盖变量: `GMLST_PUBMLST_BASE_URL`

### API 模型

PubMLST 通过 `gmlst/database/providers/bigsdb.py` 中的 `BigSdbProvider` 访问 BIGSdb REST 接口。

其流程为：

1. 查询 BIGSdb 根 URL，获取 organism group
2. 发现每个物种下的 `seqdef` 数据库
3. 查询 `/schemes` 获取 scheme 元数据
4. 解析 loci 和 profile URL
5. 从 `<locus_url>/alleles_fasta` 下载 allele FASTA
6. 当存在 `profiles_csv` 时下载 profile 数据

### Scheme 覆盖范围

PubMLST 是经典 MLST 最主要的来源，同时也包含不少 cgMLST 与 wgMLST 项目。`gmlst/database/providers/bigsdb.py` 会根据 BIGSdb 的描述文字和 locus 数量来推断 scheme type。

### 命名行为

在 provider 内部，`BigSdbProvider.list_schemes()` 会先基于标准化物种名生成短名称。之后 `gmlst/database/cache.py` 中的 `DatabaseCache.save_catalog()` 再负责跨 provider 的全局唯一命名。

### 认证说明

当前源码将 PubMLST 作为公开 BIGSdb REST provider 处理。`gmlst/database/providers/bigsdb.py` 中目前没有专门的 PubMLST token 配置路径。如果需要认证式 BIGSdb 访问，目前代码库支持的方式是后文的 private BIGSdb 机制。

## Pasteur

### 基本信息

- provider key: `pasteur`
- 注册位置: `gmlst/database/providers/__init__.py`
- 实现位置: `gmlst/database/providers/bigsdb.py`
- 默认 base URL: `https://bigsdb.pasteur.fr/api/db`
- 覆盖变量: `GMLST_PASTEUR_BASE_URL`

### API 模型

Pasteur 与 PubMLST 共用 `BigSdbProvider` 实现，因为两个站点都提供相同结构的 BIGSdb REST 接口。

### Scheme 覆盖范围

Pasteur 提供 MLST，以及部分更大的 scheme。`gmlst/database/providers/bigsdb.py` 仍然会根据描述关键词把它们归类为 `mlst`、`cgmlst` 或 `wgmlst`。

### 名称映射

`gmlst/database/providers/bigsdb.py` 会从 `gmlst/data/organism_mapping.json` 读取物种名映射，以便不同 provider 的 catalog 使用更一致的物种标签。

## Enterobase

### 基本信息

- provider key: `enterobase`
- 实现位置: `gmlst/database/providers/enterobase.py`
- base URL: `https://enterobase.warwick.ac.uk/schemes`

### 交付模型

在本项目里，Enterobase 不是通过 BIGSdb 实现的。`gmlst/database/providers/enterobase.py` 采用已知目录结构上的直接 HTTP 下载。

provider 内部维护了 `_SCHEME_MAP`，把 `ecoli_1`、`senterica_2` 这样的公开 scheme 名，映射到上游目录名。

### Scheme 覆盖范围

当前实现包含一些常见 Enterobase 物种和 scheme，例如：

- *Escherichia coli*
- *Salmonella enterica*
- *Yersinia enterocolitica*
- *Klebsiella pneumoniae*
- *Streptococcus pneumoniae*
- *Vibrio* spp.

它支持 MLST、cgMLST、wgMLST，以及部分 rMLST 风格的条目，具体取决于映射目录。

### 下载格式

该 provider 会下载每个 locus 的 `.fasta.gz` 文件，将其解压为 `.tfa`，再下载 `profiles.list.gz`，最后写入 `.meta.json`。

### Token 说明

`gmlst/commands/scheme.py` 为 Enterobase 相关命令暴露了 `--token` 选项，并支持环境变量 `ENTEROBASE_TOKEN`。不过当前 `gmlst/database/providers/enterobase.py` 的实现仍然以直接 HTTP 下载为主，所以 token 支持在实际流程中的作用比较有限。

## cgMLST.org

### 基本信息

- provider key: `cgmlst`
- 实现位置: `gmlst/database/providers/cgmlst.py`
- catalog 定义: `gmlst/database/providers/cgmlst_schemes.py`
- base URL: `https://www.cgmlst.org/ncs/1000`

### 交付模型

`gmlst/database/providers/cgmlst.py` 不使用 REST catalog API。它先读取 `gmlst/database/providers/cgmlst_schemes.py` 中定义的本地 catalog，再从 schema 页面下载批量 ZIP 并提取 locus FASTA。

### Scheme 覆盖范围

这个 provider 专注于 cgMLST。scheme 元数据包含 `schema_id`、显示名称、物种名和预期 locus 数量。

### 完整性检查

提取后，provider 会读取 schema 状态页面上的 locus 数量，并与本地提取结果对比。如果下载不完整，会直接失败。

## Local provider

### 它是什么

`local` provider 不是一个远程 provider 类。它是由 `gmlst/commands/scheme.py` 管理、由 `gmlst/database/cache.py` 存储的本地 catalog 命名空间。

### 数据存放位置

自定义 scheme 会创建在缓存根目录下，通常是：

```text
~/.cache/gmlst/local/custom_<n>/
```

每个本地 scheme 目录包含：

- 每个 locus 的 allele FASTA 文件
- 类似 `custom_1.txt` 的 profile 文件
- `.meta.json`

### 本地 scheme 如何创建

`gmlst/commands/scheme.py` 中的 `gmlst scheme create` 会使用 novel allele 与 novel profile 数据创建本地 scheme。元数据辅助逻辑位于 `gmlst/novel/service.py`。

### 如何列出本地 scheme

当 catalog 查询包含 `local` 时，本地 scheme 会被纳入检索范围，例如 `gmlst/commands/typing_scheme.py` 和 `gmlst/commands/scheme.py` 的部分路径。

## Private BIGSdb

### 目的

private BIGSdb 支持让 `gmlst` 可以连接自建 BIGSdb 实例，而不需要专门新增一个 provider 模块。

### 配置方式

`gmlst/database/providers/__init__.py` 会在以下条件满足时动态创建 provider：

- 设置了 `GMLST_PRIVATE_BIGSDB_URL`

相关可选变量还有：

- `GMLST_PRIVATE_BIGSDB_NAME`
- `GMLST_PRIVATE_BIGSDB_LABEL`

### 行为

private provider 仍然复用 `gmlst/database/providers/bigsdb.py` 中的 `BigSdbProvider`。因此它继承了与 PubMLST、Pasteur 相同的 scheme 发现、类型分类和下载流程。

## Provider 特定说明

### 下载后端

`gmlst/database/download.py` 支持多种下载工具，provider 层可使用：

- `aria2c`
- `curl`
- `wget`
- Python `httpx`
- Python `requests`

命令层可以显式选择下载工具，provider 代码会沿用这个设置。

### 并行下载

需要下载大量 locus 文件的 provider，尤其是 BIGSdb 和 Enterobase，会通过 `gmlst/database/providers/base.py` 和 `gmlst/database/download.py` 中的 batch helper 进行并行下载。CLI 可通过 `-x` 或 `--connections` 控制连接数。

### Catalog 新鲜度

provider catalog 会被缓存。`gmlst scheme update` 会通过 `gmlst/database/cache.py` 中的 `DatabaseCache.update_catalog()` 刷新这些缓存。

### Scheme 名称全局唯一

仅靠 provider 名称还不够，因为多个 provider 可能都包含同一物种的 scheme。`gmlst/database/cache.py` 中的 `DatabaseCache.save_catalog()` 会先在单个 provider 内标准化名称，再在 provider 之间继续增加数字后缀，保证名称全局唯一。

### Enterobase 与认证

CLI 确实暴露了 Enterobase token 相关选项，但当前 provider 实现依旧以直接 HTTP 下载为中心。如果你的环境依赖受保护的 Enterobase 工作流，建议先确认远端接口的认证要求。

## Blocked schemes

blocked scheme 由 `gmlst/data/blocked_schemes.json` 控制，并通过 `gmlst/commands/common.py` 中的 `_load_blocked_schemes()` 读取。

`gmlst/commands/scheme.py` 会在 scheme 列表、下载和更新时应用这一过滤逻辑。

这个机制用于隐藏不应暴露给普通用户的条目，例如：

- 已弃用 scheme
- 已知存在问题的 catalog 条目
- 不适合常规工作流的特殊 scheme

## 相关文档

- [`docs/architecture.md`](./architecture.md)，系统设计与分层
- [`docs/commands.md`](../commands.md)，命令语法与选项
- [`docs/quickstart.md`](../quickstart.md)，基础上手流程
