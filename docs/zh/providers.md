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

PubMLST 运行在 BIGSdb 平台上。自 **2025 年 1 月 1 日**起，PubMLST 要求认证后才能访问 2024 年 12 月 31 日之后新增的 allele、profile 和 isolate 数据；此前的历史数据仍可匿名访问。

#### 如何获取 PubMLST API key

1. 在 [pubmlst.org](https://pubmlst.org) 注册账号
2. 登录后进入个人资料页
3. 打开 **Preferences** → **API keys**
4. 点击 **Create new API key**
5. 复制生成的 key（格式：`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`）

- **认证方式**：Personal API Key，通过 `X-API-Key: <key>` 请求头传递（注：BIGSdb 文档同时记载了 `Authorization: Bearer` 和 OAuth，但 PubMLST 实际服务器只接受 `X-API-Key`）

#### 在 gmlst 中使用 API key

```bash
gmlst config set GMLST_PUBMLST_API_KEY your-key-here
source ~/.config/gmlst/env.sh
```

之后所有 PubMLST 请求都会自动携带 `X-API-Key` 请求头。没有 key 时只能访问 2025 年之前的数据（profile 和 allele 会被截断）。

#### 参考链接

- [BIGSdb API 认证文档](https://bigsdb.readthedocs.io/en/latest/rest.html#api-oauth)
- [PubMLST 数据访问政策变更](http://pubmlst.org/change-data-access-policy)

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

### 认证说明

Pasteur 与 PubMLST 运行相同的 BIGSdb 平台，并采用了**相同的数据访问政策**：自 **2025 年 1 月 1 日**起，2024 年 12 月 31 日之后整理的数据需要认证才能访问。认证机制与 PubMLST 一致（`X-API-Key` 请求头）。

#### 如何获取 Pasteur BIGSdb API key

申请过程需要人工审核，比 PubMLST 耗时更长：

**第 1 步：创建账号**

在 [bigsdb.pasteur.fr/register/](https://bigsdb.pasteur.fr/register/) 注册

**第 2 步：注册到具体数据库**

登录后，向你需要的每个物种数据库提交注册（如 Bordetella、E. coli、Listeria）。**只有已注册的数据库才会授予 API key 权限**。

**第 3 步：通过邮件申请 API key**

按你的所属领域联系 Pasteur 团队：

| 你的领域 | 联系邮箱 |
|---|---|
| 学术 / 非营利 / 公共卫生 | [bigsdb@pasteur.fr](mailto:bigsdb@pasteur.fr) |
| 商业 / 营利 | [bigsdb-policy@pasteur.fr](mailto:bigsdb-policy@pasteur.fr) |

邮件模板：

```
Subject: API Key Request for gmlst typing pipeline

BIGSdb-Pasteur Username: <your username>
Affiliation: <your institution>
Email address: <your email>
Sector: Academic / Non-profit
Database(s) you intend to use:
  - <species 1, e.g. Bordetella>
  - <species 2, e.g. E. coli>
Motivation:
  I use gmlst (https://github.com/indexofire/gmlst), a bacterial genome
  typing CLI tool, for automated MLST/cgMLST typing. I need API access
  to download scheme allele sequences and ST profiles for integration
  into our typing pipeline.
```

团队审核后会回复 API key（通常几个工作日内）。

**第 4 步：在 gmlst 中配置 key**

```bash
gmlst config set GMLST_PASTEUR_API_KEY your-pasteur-key
source ~/.config/gmlst/env.sh
```

验证：

```bash
gmlst config get GMLST_PASTEUR_API_KEY
```

之后所有 Pasteur 请求都会自动携带 `X-API-Key` 请求头。没有 key 时只能访问 2025 年之前的数据。

#### 参考链接

- [Pasteur API key 申请页面](https://bigsdb.pasteur.fr/requesting-api-key/)
- [Pasteur 数据访问政策](https://bigsdb.pasteur.fr/news/novel-data-access-policy/)
- [BIGSdb API 认证文档](https://bigsdb.readthedocs.io/en/latest/rest.html#api-oauth)

## Enterobase

### 基本信息

- provider key: `enterobase`
- 实现位置: `gmlst/database/providers/enterobase.py`
- base URL: `https://enterobase.warwick.ac.uk/schemes`

### 交付模型

在本项目里，Enterobase 不是通过 BIGSdb 实现的。`gmlst/database/providers/enterobase.py` 直接从 Enterobase 开放 scheme 目录 `https://enterobase.warwick.ac.uk/schemes/` 进行 HTTP 下载。

### Scheme 发现

`list_schemes()` 会动态扫描 Enterobase `/schemes/` 的 HTTP 目录索引来发现可用的 scheme 目录。这意味着 Enterobase 新增的 scheme 在执行 `gmlst scheme update --force` 后即可自动可见，无需等待代码更新。当网络不可用时，provider 会回退到源码中定义的静态 `_SCHEME_MAP`。

scheme 目录名会直接用作 catalog 中的 `scheme_name`（如 `Salmonella.Achtman7GeneMLST`）。catalog 的 `extra.directory` 字段携带该目录名，并传递给 `download_scheme()` 和 `update_scheme()`，确保下载始终解析到正确的远程路径。

### Scheme 覆盖范围

Enterobase provider 会跨多个物种发现 scheme，包括：

- *Escherichia coli* / *Shigella*
- *Salmonella enterica*
- *Yersinia enterocolitica*
- *Klebsiella pneumoniae*
- *Streptococcus pneumoniae*
- *Vibrio* spp.
- *Moraxella catarrhalis*
- *Clostridium botulinum*
- *Photorhabdus luminescens*

支持的 scheme 类型（MLST、cgMLST、wgMLST、rMLST）取决于服务器上实际存在的目录。

### 下载格式

该 provider 会下载每个 locus 的 `.fasta.gz` 文件，将其解压为 `.tfa`，再下载 `profiles.list.gz`，最后写入 `.meta.json`。

### Token 说明

Enterobase 使用的认证体系与 PubMLST/Pasteur BIGSdb **完全不同**，其 REST API 一直需要认证。

- **认证方式**：API Token，通过 `Authorization: Basic <token>` 请求头传递（注意是 Basic 认证，不是 Bearer，与 BIGSdb 不同）
- **获取方式**：
  1. 在 [enterobase.warwick.ac.uk](https://enterobase.warwick.ac.uk) 注册
  2. **发邮件到 enterobase@warwick.ac.uk**，为所需数据库申请 API 访问权限
  3. Token 会显示在数据库面板的 "Important information" 下
- **API 文档**：[Enterobase API 入门](https://enterobase.readthedocs.io/en/latest/api/api-getting-started.html)
- **使用限制**：
  - API 请求之间应暂停 1–2 秒
  - **不要**通过 API 做大规模批量下载
  - rMLST allele 数据受牛津大学版权保护，**不可下载**
  - 商业使用需获得华威大学明确授权

`gmlst/commands/scheme.py` 暴露了 `--token` 选项，并支持 `ENTEROBASE_TOKEN` 环境变量回退。token 会经由缓存层传给 Enterobase provider，并以 `Authorization: Basic <token>` 请求头附加到所有 HTTP 请求上（目录列表、locus 计数和文件下载）。

> **注意**：部分 Enterobase scheme 目录（如 `Vibrio.Lan7Gene`）即使无认证要求也返回 HTTP 403 —— 这是服务器对特定目录的限制。此时请改用其他 provider 的等价 scheme（如 PubMLST）。

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

- `aria2c`（默认，带重试：`--max-tries=5 --retry-wait=3`）
- `curl`
- `wget`
- Python `httpx`
- Python `requests`

命令层可以显式选择下载工具，provider 代码会沿用这个设置。

### 并行下载

需要下载大量 locus 文件的 provider，尤其是 BIGSdb 和 Enterobase，会通过 `gmlst/database/providers/base.py` 和 `gmlst/database/download.py` 中的 batch helper 进行并行下载。CLI 可通过 `-x` 或 `--connections`（默认 4）控制连接数。每台服务器的连接数上限为 2，以避免触发上游限流（HTTP 429）。

### Catalog 生命周期

catalog 是连接 scheme 名称与 provider 数据的中枢索引，完整生命周期如下：

1. **发现**：各 provider 的 `list_schemes()` 查询自己的上游源：
   - PubMLST/Pasteur：BIGSdb REST API（`GET /db` → schemes → loci）
   - Enterobase：动态抓取 `/schemes/` 目录索引
   - cgMLST.org：`gmlst/database/providers/cgmlst_schemes.py` 中的静态 catalog
2. **屏蔽**：`gmlst/data/blocked_schemes.json` 列出的 scheme 会在 `save_catalog()` 时被过滤，缓存 catalog JSON 中永远不会出现被屏蔽条目。匹配同时作用于 `scheme_name` 和 `extra.directory`。
3. **缓存**：`DatabaseCache.save_catalog()` 写入 `_catalog/<provider>.json`，并保证 scheme 名称全局唯一（跨 provider 后缀去重）。
4. **展示**：`gmlst scheme list` 直接读取缓存的 catalog JSON，列表时不发生网络请求。
5. **刷新**：`gmlst scheme update --force` 重新为所有 provider 执行 `list_schemes()` 并覆盖 catalog JSON。这是获取上游新增 scheme 的唯一方式。

### Scheme 名称全局唯一

仅靠 provider 名称还不够，因为多个 provider 可能都包含同一物种的 scheme。`gmlst/database/cache.py` 中的 `DatabaseCache.save_catalog()` 会先在单个 provider 内标准化名称，再在 provider 之间继续增加数字后缀，保证名称全局唯一。

### Enterobase 认证模型

Enterobase 有两条数据访问路径：

| 路径 | URL | 认证 | 覆盖范围 |
|---|---|---|---|
| `/schemes/` 目录 | `enterobase.warwick.ac.uk/schemes/` | 无（开放） | 24 个 scheme 目录，每日更新 |
| REST API v2.0 | `enterobase.warwick.ac.uk/api/v2.0/` | Token（Basic 认证） | 网站全部数据库（M. tuberculosis、Enterococcus 等） |

当前实现仅使用 `/schemes/` 目录。`--token` 选项和 `ENTEROBASE_TOKEN` 环境变量会以 `Authorization: Basic <token>` 请求头附加到所有 Enterobase HTTP 请求上。提供 token 时，每个请求（目录列表、locus 计数、文件下载）都会携带它。

基于 API 的 scheme 下载（用于不在 `/schemes/` 中的物种）计划在后续版本支持。

### Enterobase 数据新鲜度

`/schemes/` 目录由 Enterobase 的自动化脚本每日更新。所有 allele FASTA 和 profile 文件都携带当日日期，即使该物种未在 Enterobase 网站首页展示（如 Streptococcus、Photorhabdus、Clostridium botulinum）。HTTP 索引中显示的目录级修改时间是目录创建时间，可能已是多年前；目录内的单个文件才是每日重新生成的。

## Blocked schemes

blocked scheme 由 `gmlst/data/blocked_schemes.json` 控制，由 `gmlst/commands/common.py`（CLI 层）和 `gmlst/database/cache.py`（数据层）中的 `_load_blocked_schemes()` 读取。

过滤在两层生效：

1. **catalog 写入时**（`save_catalog`）：屏蔽条目在 catalog JSON 写入前被移除，保证缓存 catalog 始终干净。
2. **CLI 展示时**（`scheme list`、`scheme search`、`scheme download`）：纵深防御过滤器，拦截写入时过滤上线之前遗留的旧缓存 catalog 中的屏蔽条目。

屏蔽匹配同时作用于 `scheme_name`（如 `salmonella_1`）和 `extra.directory`（如 `clostridium.Griffiths_MLST`），因此不受跨 provider 重新编号的影响。

这个机制用于隐藏不应暴露给普通用户的条目，例如：

- 已弃用或停止维护的 scheme（如 `clostridium.Griffiths_MLST` —— 最后一次整理是 2019 年，profile 为空）
- 已知存在数据质量问题的 catalog 条目
- 不适合常规工作流的特殊 scheme

## Scheme 元数据（.meta.json）

每个下载的 scheme 目录都包含一个 `.meta.json` 文件，记录下载元数据：

```json
{
    "scheme": "saureus_1",
    "provider": "pubmlst",
    "scheme_type": "mlst",
    "downloaded_at": "2026-07-10T12:00:00Z",
    "loci": ["arcC", "aroE", "glpF", "gmk", "pta", "tpi", "yqiL"],
    "locus_meta": {
        "arcC": { "records": 458, "last_updated": "2026-07-01" }
    },
    "profile_meta": {
        "records": 5000, "last_updated": "2026-07-01", "last_added": "2026-07-01"
    }
}
```

元数据记录下载/更新时间戳、每个 locus 的 allele 数量、profile 数量，以及用于增量更新检测的远端更新时间戳。

## 增量更新机制

`gmlst scheme update` 采用**增量更新** —— 只重新下载发生变化的数据，而不是整个 scheme。具体机制因 provider 而异：

### PubMLST / Pasteur（BIGSdb）

BIGSdb 通过 REST API 提供每个 locus 的元数据，可实现精确的变更检测：

1. **查询 locus 元数据**：对每个 locus 执行 `GET /loci/{locus}/alleles`，返回 `records`（allele 数）和 `last_updated`（时间戳）。
2. **与本地 `.meta.json` 对比**：满足以下任一条件即标记该 locus 需要重新下载：
   - 本地 `.tfa` 文件不存在
   - 本地 allele 数 < 服务器 allele 数
   - 存储的 `records` 值与服务器不一致
   - 存储的 `last_updated` 时间戳与服务器不一致
3. **只下载变化的 locus**：仅检测到变化的 locus 通过 `alleles_fasta` 重新下载，未变化的 locus 完全跳过。
4. **Profile 检查**：仅当 ST profile 的 `records`、`last_updated` 或 `last_added` 变化时才重新下载。

示例：一个含 2000 个 locus 的 cgMLST scheme，其中 50 个 locus 有新 allele → 只下载 50 个文件（总量的 2.5%）。

**限制**：每个变化的 locus 以**全量 allele FASTA 替换**的方式下载（不是追加）。这是因为 BIGSdb API 只提供 `alleles_fasta`（单文件包含全部 allele），没有"仅新 allele"接口。

### Enterobase

Enterobase 使用 HTTP 头（ETag、Last-Modified）做文件级变更检测：

1. **HEAD 请求**：对每个远程文件（`{locus}.fasta.gz`、`profiles.list.gz`）发送 `HEAD` 请求，将 `ETag` / `Last-Modified` / `Content-Length` 与本地存储值对比。
2. **下载变化的文件**：仅重新下载头部发生变化的文件。
3. **解压并替换**：下载的 `.fasta.gz` 解压为 `.tfa` 并原子替换旧文件。

### cgMLST.org

cgMLST.org 为每个 scheme 提供单一批量 ZIP。当 schema 版本或 locus 数变化时，更新会重新下载整个 ZIP，没有按 locus 的增量 API。

### 更新工作流

```bash
# 增量更新单个 scheme
gmlst scheme update saureus_1

# 更新所有已缓存的 scheme
gmlst scheme update --all

# 先强制刷新所有 provider 的 catalog，再更新已缓存的 scheme
gmlst scheme update --force --all
```

`--force` 会在更新前先从所有 provider 刷新 catalog（scheme 列表）。不加 `--force` 时，只检查已缓存 scheme 数据的更新。

## 相关文档

- [`docs/architecture.md`](./architecture.md)，系统设计与分层
- [`docs/commands.md`](commands.md)，命令语法与选项
- [`docs/quickstart.md`](quickstart.md)，基础上手流程
