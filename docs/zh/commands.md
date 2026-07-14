# 命令参考

本页文档记录 `gmlst` 当前完整的命令行接口。

## 帮助行为

- `-h` 和 `--help` 在所有层级等效。
- 不带子命令运行命令组时打印用法/帮助信息：
  - `gmlst`
  - `gmlst scheme`
  - `gmlst utils`
  - `gmlst visual`

## 顶层 CLI

```bash
gmlst [OPTIONS] COMMAND [ARGS]...
```

全局选项：

- `-V, --version` 版本号
- `-v, --verbose` 启用调试日志
- `-q, --quiet` 抑制非错误日志
- `-h, --help` 帮助信息

顶层命令：

- `typing` — 对 FASTA/FASTQ 样本进行分型
- `scheme` — scheme/provider/缓存管理
- `utils` — 提取与序列工具命令
- `config` — 配置变量管理
- `visual` — 本地 Web 可视化

## typing

```bash
gmlst typing [OPTIONS] COMMAND [ARGS]...
```

子命令：

- `mlst` — 仅 MLST 方案
- `cgmlst` — 仅 cgMLST/wgMLST 方案
- `tgmlst` — 无方案分型模式

示例：

```bash
gmlst typing mlst -s saureus_1 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
gmlst typing tgmlst sample.fna
```

`mlst` 和 `cgmlst` 通用选项：

- `SCHEME`（位置参数，必填）— 方案名称，如 `saureus_1`
- `-s, --scheme TEXT`（已废弃，使用位置参数）
- `-b, --backend [blastn|kma|minimap2|nucmer]`
- `--format [tsv|json|pretty]`
- `-o, --output PATH`
- `-t, --threads INTEGER`
- `--max-workers INTEGER`（样本级并行数）
- `--max-depth INTEGER`（FASTQ 最大深度，默认 100，0=禁用）
- `--detail` — 在 TSV 输出中显示 contig 位置信息（仅 FASTA）
- `-q, --quiet`
- `--novel-allele` — 保存新等位基因序列
- `--novel-profile` — 保存新 ST profile（需要 `--novel-allele`）
- `-h, --help`

`cgmlst` 预过滤选项：

- `--cgmlst-mode [standard|chew-fast|chew-ultrafast|chew-bsr|chew-balanced]`
- `--prefilter-k INTEGER`
- `--prefilter-top-n INTEGER`
- `--prefilter-min-loci-fraction FLOAT`
- `--cds-coordinates-out PATH`（导出预测的 CDS 坐标为 TSV）
- `--call-policy [default|chewbbaca]`（chew 风格输出分类）
- `--chew-cds-gate/--no-chew-cds-gate`（仅 `--call-policy chewbbaca` 时有效）

cgMLST 默认值与性能说明：

- `typing cgmlst` 的默认 backend 是 `minimap2`。
- FASTQ 输入自动切换到 KMA（精度更高）。
- `--cgmlst-mode standard`：保守行为，不强制 chew 风格覆盖。
- `--cgmlst-mode chew-fast`：启用 exact-hash + minimap2 hash 预过滤 + 缺失 locus 的 minimap2 精炼 + blastn 证据回退。
- `--cgmlst-mode chew-ultrafast`：在 `chew-fast` 基础上使用更激进的速度配置 + 严格低置信度补救 + 自适应二轮精炼。
- `--cgmlst-mode chew-bsr`：在 `chew-fast` 基础上增加蛋白级 exact-hash 预解析。
- `--cgmlst-mode chew-balanced`：启用 exact-hash + minimap2 hash 预过滤 + blastn 定向回退。

tgmlst 选项（无方案分型）：

- `--format [tsv|json|pretty]`
- `-o, --output PATH`
- `--no-header`
- `--hash-strategy [safe|fast|ultra|strict|blast]`
- `--save-scheme PATH`
- `--load-scheme PATH`
- `--stats`
- `--max-workers INTEGER`

输出标记说明：

| 标记 | 含义 | ST 判定 |
|---|---|---|
| `23` | 精确匹配，单拷贝 | ✅ 是 |
| `23*` | 精确匹配，相同多拷贝 | ✅ 是（使用 23） |
| `~23` | 最近匹配（非精确） | ❌ Novel |
| `15?` | 部分覆盖 | ❌ 不完整 |
| `1,2` | 冲突多拷贝（不同等位基因） | ❌ 不确定 |
| `1,1` | 显式展开（`--count-same-copy`） | ✅ 是 |
| `-` | 缺失 | ❌ 不完整 |

`--detail` 输出格式（仅 FASTA + TSV）：

```
FILE           ST    dnaE
sample.fasta   19    19;contig1:3153925-3154481:+
```

格式为 `allele_id;contig:start-end:strand`。

配对 FASTQ 自动检测命名模式：`_R1`/`_R2`、`_1`/`_2`、`.1`/`.2`。

## scheme

```bash
gmlst scheme [OPTIONS] COMMAND [ARGS]...
```

子命令：

- `list` — 列出可用 scheme
- `search` — 搜索 scheme
- `show` — 显示 scheme 详情
- `download` — 下载 scheme
- `update` — 更新 scheme 或目录
- `create` — 从新等位基因创建自定义 scheme
- `update-custom` — 更新自定义 scheme
- `export` — 导出 scheme profile

### scheme download

```bash
gmlst scheme download SCHEME [OPTIONS]
```

位置参数：

- `SCHEME` — 方案名称（如 `saureus_1`）

选项：

- `--force` — 强制重新下载
- `-q, --quiet`
- `--download-tool [auto|aria2c|curl|wget|httpx|requests]`
- `-x, --connections INTEGER`（默认 4）
- `--token TEXT`（Enterobase API token）
- `--cache-dir PATH`

示例：

```bash
gmlst scheme download saureus_1
gmlst scheme download vparahaemolyticus_3 --force -x 2
```

### scheme search

```bash
gmlst scheme search PATTERN [OPTIONS]
```

跨名称、物种、描述、provider 搜索 scheme。

位置参数：

- `PATTERN` — 不区分大小写的子串

选项：

- `-p, --provider [provider|all]`
- `-t, --type [mlst|cgmlst|wgmlst|rmlst|other|all]`
- `--cache-dir PATH`

示例：

```bash
gmlst scheme search saureus
gmlst scheme search "salmonella" -t cgmlst
```

### scheme list

```bash
gmlst scheme list [OPTIONS]
```

选项：

- `-p, --provider [provider|local|all]`
- `-t, --type [mlst|cgmlst|wgmlst|rmlst|other|all]`
- `-n, --name TEXT`（按物种名正则过滤）
- `-f, --format [text|table|csv|tsv|json]`
- `-a, --available`（仅显示已下载的）
- `--pager`（分页显示）
- `--cache-dir PATH`

### scheme show

```bash
gmlst scheme show SCHEME [OPTIONS]
```

显示 scheme 详细信息。使用 `-a` 查看每个 locus 的等位基因统计。

选项：

- `-a, --all` — 显示等位基因统计（需要已下载）
- `-f, --format [text|table|csv|tsv|json]`
- `--cache-dir PATH`

### scheme update

```bash
gmlst scheme update [OPTIONS]
```

选项：

- `SCHEME`（位置参数）— 更新指定 scheme
- `--all` — 更新所有已缓存的 scheme
- `-f, --force` — 强制刷新 provider 目录
- `--download-tool [auto|aria2c|curl|wget|httpx|requests]`
- `-x, --connections INTEGER`
- `--token TEXT`
- `--cache-dir PATH`

更新机制为**增量更新**：只下载有变化的 locus 和 profile，不是全部重新下载。

### scheme create

```bash
gmlst scheme create [OPTIONS]
```

选项：

- `-t, --type [mlst]`（必填）
- `-s, --source TEXT`（必填，基础方案名）
- `--data-dir DIRECTORY`（必填，新等位基因数据目录）
- `--desc TEXT`
- `--cache-dir PATH`

### scheme update-custom

```bash
gmlst scheme update-custom SCHEME [OPTIONS]
```

位置参数：

- `SCHEME` — 自定义方案名（如 `custom_1`）

选项：

- `--data-dir DIRECTORY`（必填）
- `--cache-dir PATH`

### scheme export

```bash
gmlst scheme export SCHEME [OPTIONS]
```

位置参数：

- `SCHEME` — 方案名（如 `custom_1`）

选项：

- `--format [grapetree|original]`（必填）
- `-o, --output PATH`（必填）
- `--cache-dir PATH`

## config

```bash
gmlst config [OPTIONS] COMMAND [ARGS]...
```

检查和管理配置变量。

子命令：

- `env` — 以 shell 格式打印所有环境变量（可 source）
- `show` — 分组表格显示所有配置变量
- `get NAME` — 获取单个变量值
- `set NAME VALUE` — 写入变量到配置文件

示例：

```bash
gmlst config show                          # 查看所有配置
gmlst config set GMLST_CACHE_DIR /data     # 设置缓存目录
source ~/.config/gmlst/env.sh              # 应用配置
```

## utils

```bash
gmlst utils [OPTIONS] COMMAND [ARGS]...
```

子命令：

- `extract` — 等位基因/新等位基因提取
- `concat` — FASTA 序列拼接
- `benchmark` — 后端性能基准
- `check` — 后端依赖检查

### utils extract

```bash
gmlst utils extract [OPTIONS]
```

主要模式：

```bash
# 1. 从样本提取等位基因
gmlst utils extract -i genome.fasta -s ecoli_1

# 2. 从 typing JSON 提取新等位基因
gmlst utils extract -i results.json --novel-allele --novel-profile --data-dir novel

# 3. TSV 回退模式
gmlst utils extract -i results.tsv -s ecoli_1 --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel
```

## visual

```bash
gmlst visual [OPTIONS] COMMAND [ARGS]...
```

子命令：

- `web` — 启动本地 MST 可视化 Web 应用

### visual web

```bash
gmlst visual web [OPTIONS]
```

选项：

- `--host TEXT`（默认 `127.0.0.1`）
- `--port INTEGER`（默认 `8787`）
- `--open-browser`（自动打开浏览器）

用法：

```bash
gmlst visual web --open-browser
```

然后在 Web 界面中粘贴或上传 cgMLST TSV 文件，点击 **Build MST**。

功能：

- 基于 profile 距离（每 locus 等位基因差异数）构建 MST
- 支持缺失 token 罚分切换（`LNF`、`NIPH`、`NIPHEM` 等）
- 支持 `tree` 和 `radial` 两种布局
- 支持基于元数据的节点着色
- 支持 SVG 导出
- 接受 gmlst TSV 和 GrapeTree 风格 profile（`#Strain` 首列）
