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
gmlst typing mlst sample.fna                     # 物种自动检测
gmlst typing mlst --guess assemblies/*.fna       # 无人值守混合物种批处理
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --prefilter-k 31 --prefilter-top-n 20 sample.fna
gmlst typing tgmlst sample.fna
```

旧版兼容：

```bash
gmlst typing -s saureus_1 sample.fna
gmlst typing -s schemefree sample.fna
```

`mlst` 和 `cgmlst` 通用选项：

- `-s, --scheme TEXT` — 方案名称，如 `saureus_1`。可省略：gmlst 会从基因组自动检测物种、挑选匹配方案、下载并分型；歧义情况回退到交互式选择
- `-n, --organism TEXT` — 按物种或方案名子串解析方案（如 `bordetella`）；唯一匹配自动选择，多匹配打印候选表
- `-g, --guess` — 无人值守混合物种分型：检测每个组装的物种，按“内置偏好顺序 → 唯一缓存候选 → 自然顺序”为每个物种选一个方案，缺失自动下载，全程零提示。与 `-s`/`-n` 及 novel 参数互斥。TSV 输出按方案分节；JSON 为单一信封；无法解析的样本跳过并给出原因
- `-b, --backend [blastn|kma|minimap2|nucmer]`
- `--minscore FLOAT` — 丢弃质量分（0-100，见 JSON `score` 字段）低于阈值的样本；`0` 表示全部保留
- `--min-id FLOAT` — 最小比对一致性百分比（默认 95.0）
- `--min-cov FLOAT` — 最小等位基因覆盖度 0-1（默认 0.95）
- `--min-depth FLOAT` — 最小读深度，仅 FASTQ（默认 10.0）
- `--min-join-overlap INTEGER`（拼接断裂基因所需的最小等位基因重叠碱基数，默认 10；0 = 最激进）
- `--format [tsv|json|pretty]`
- `-o, --output PATH`
- `--no-header` — 省略 TSV 表头
- `--cache-dir PATH` — 覆盖缓存目录
- `--force-reindex` — 重建比对器索引
- `-t, --threads INTEGER`
- `--max-workers INTEGER`（样本级并行数）
- `--max-depth FLOAT` — FASTQ 重采样到此深度（默认 100，`0` = 禁用，仅 FASTQ）
- `--count-same-copy` — 将同等位基因多拷贝（`23*`）展开为逗号记法
- `--detail` — 在 TSV 输出中显示 contig 位置信息（仅 FASTA）
- `-q, --quiet`
- `--data-dir, --output-dir PATH`（推荐使用 `--data-dir`）
- `--novel-allele` — 保存新等位基因序列
- `--novel-profile` — 保存新 ST profile（需要 `--novel-allele`）
- `-h, --help`

物种自动检测说明：

- 唯一检测且同类型方案有多个时，唯一已缓存候选自动选择；否则列出候选（标注已缓存项）供交互选择
- 每物种的偏好顺序随包内置（`gmlst/data/scheme_preferences.json`），同时驱动 `--guess` 与自动检测

`cgmlst` 预过滤选项：

- `--cgmlst-mode [fast|ultrafast|balanced]`
- `--prefilter-k INTEGER`
- `--prefilter-top-n INTEGER`
- `--prefilter-min-loci-fraction FLOAT`
- `--cds-coordinates-out PATH`（导出预测的 CDS 坐标为 TSV）
- `--call-policy [default|chewbbaca]`（chew 风格输出分类）
- `--chew-cds-gate/--no-chew-cds-gate`（仅 `--call-policy chewbbaca` 时有效）

cgMLST 默认值与性能说明：

- `typing cgmlst` 的默认 backend 是 `minimap2`。
- `--cgmlst-mode fast`：启用 exact-hash + minimap2 hash 预过滤，加缺失 locus 的 minimap2 自动精炼（默认上限 500 个 locus），再对低置信度 locus 执行定向 blastn 证据回退（默认上限 500 个 locus）。
- `--cgmlst-mode ultrafast`：与 `fast` 相同，但主比对只用代表序列、禁用 minimap2 FASTA CIGAR 输出、应用 ultrafast minimap2 FASTA 速度配置、执行严格的低置信度补救（默认上限 120 个 locus），然后用自适应预算对剩余 partial/closest locus 做第二轮定向补扫。
- `--cgmlst-mode balanced`：启用 exact-hash + minimap2 hash 预过滤 + 低置信度 locus 的定向 `blastn` 回退。
- FASTQ 输入时，`typing cgmlst` 自动将 `-b minimap2` 切换为 `-b kma`，并将 `--cgmlst-mode` 视为仅兼容用途（`fast`），因为 chew 风格模式优化面向 FASTA。
- `--call-policy chewbbaca` 要求 FASTA 组装，保持原始调用不变，仅在输出中渲染 chew 风格的逐 locus 分类标签。
- 默认情况下 `--call-policy chewbbaca` 启用 CDS 门控分类（`--chew-cds-gate`）；用 `--no-chew-cds-gate` 允许从任意匹配序列上下文分类。

架构约束：

- FASTA：chew 风格模式分支处于激活状态并正常解释。
- FASTQ：CLI 层强制 KMA-first 策略；与模式相关的 chew 分支不会按 FASTQ 特性解释。
- 完整契约与流程图见 `docs/architecture.md`。

额外调优（环境变量）：

- `GMLST_MINIMAP2_FASTA_SPEED_PROFILE=default|fast|ultrafast`
  - `default`：现有 minimap2 行为
  - `fast`：中等程度的 seed/链接加速（`-w 15 -e 1000 -K 1G`）
  - `ultrafast`：激进速度配置（`fast` + `-f 0.001 -U 50,1000`）
- `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=adaptive|<int>`
  - `adaptive`（默认）：按剩余 partial/closest 负载自动缩放第二轮预算
  - `<int>`：为 ultrafast 第二轮强制固定预算
- `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=<int>`
  - 默认：`8`
  - FASTQ cgMLST + KMA 时，每样本线程自动从 `1` 提升到该值（不超过 CPU 数）
  - 设为 `1` 禁用自动提升
- `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1|0`
  - 默认：`1`
  - FASTQ cgMLST 启用 KMA `-mem_mode` 加速单线程比对
- `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI=<int>`
  - 默认：`64`
  - mem_mode 过后，用严格 KMA（不带 `-mem_mode`）复检最多这么多个 `closest` locus 以找回精确调用
- 预过滤自动跳过阈值由 `GMLST_CGMLST_PREFILTER_MAX_LOCI` 控制（默认 `3000`）；设为 `0` 禁用自动跳过、总是尝试预过滤。
- `-b kma` 与默认 `-b minimap2` 时 cgMLST 预过滤被跳过，走持久化全量索引路径。
- `GMLST_CGMLST_EXACT_HASH_PREFILTER=1` 启用 chewBBACA 风格的 DNA 精确匹配预解析（优先 CDS hash）。
- `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1` 启用实验性的 minimap2 FASTA hash 优先预过滤。
- `GMLST_CGMLST_CDS_PREDICTION_MODE=single|meta` 控制 cgMLST exact-hash 预解析的 Pyrodigal CDS 模式（默认 `single`）。
- `GMLST_CGMLST_CDS_TRAINING_FILE=/path/to/pyrodigal_training.trn` 使用固定训练文件；未设置且模式为 `single` 时，gmlst 首次运行会自动创建并复用 `pre_computed/pyrodigal_training.trn`。
- `GMLST_CGMLST_CDS_CLOSED_ENDS=1|0` 控制 Pyrodigal 闭合端预测行为（默认 `0`）。
- `GMLST_CGMLST_CDS_COORDINATES_OUT=/path/to/cds_coordinates.tsv` 导出预测的 CDS 坐标，用于 chewBBACA 坐标对比。
- `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` 控制第二轮精炼的最大缺失 locus 数（模式覆盖未设置时生效；默认 `0`，禁用）。
- `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND` 为低置信度 locus 启用基于证据的定向回退（`none`/`blastn`/`kma`/`nucmer`，默认 `none`）。
- `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI` 按 locus 数限制回退范围（默认 `300`，设 `0` 不限制）。
- 大 cgMLST scheme 配 `-b kma` 时建议设置 `-t`（如 `-t 8` 到 `-t 16`）；`-t 1` 可能显著变慢。

tgmlst 选项（无方案分型）：

- `--format [tsv|json|pretty]`
- `-o, --output PATH`
- `--no-header`
- `--hash-strategy [safe|fast|ultra|strict|blast]`
- `--save-scheme PATH`
- `--load-scheme PATH`
- `--stats`
- `--max-workers INTEGER`
- `--assemble-timeout FLOAT`
- `--error-report PATH`
- `--fail-on-error`
- `--summary-report PATH`

补充说明：

- JSON 输出包含每个 locus 的 `novel_sequence` 数据，可供下游提取。
- `--count-same-copy` 将同等位基因多拷贝（`23*`）展开为逗号记法（`23,23`）。默认情况下同等位基因多拷贝以 `*` 后缀显示（如 `23*`），不影响 ST 判定。
- `mlst`/`cgmlst` 模式下，命名符合常见配对模式时 FASTQ 配对文件自动检测并作为成对输入（不预先合并）：
  - `_R1` / `_R2`
  - `_1` / `_2`
  - `.1` / `.2`
  - 支持 `.fastq`、`.fq` 及 `.gz` 变体。
- `minimap2` FASTQ 模式使用候选扫描 + 对不确定 locus 的定向验证。
- `GMLST_TMPDIR` 可控制临时文件的创建位置。

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
- `update-fingerprints` — 重建/增量合并物种指纹数据库
- `remove` — 从本地缓存删除 scheme
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

- `-s, --scheme TEXT`（已弃用，请使用位置参数）
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
- `-l, --limit INTEGER`（最多显示 N 条，默认不限制）
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
- `-l, --limit INTEGER`（最多显示 N 条，默认不限制）
- `--pager`（分页显示；交互式，需要终端）
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

- `-s, --scheme TEXT` — 更新单个指定的已缓存 scheme
- `-a, --all` — 更新所有已缓存的 scheme 数据库
- `-y, --yes` — 更新全部 scheme 时跳过确认提示
- `-f, --force` — 先从 provider 强制刷新 catalog，再执行更新
- `--download-tool [auto|aria2c|curl|wget|httpx|requests]`（默认 `auto`）
- `-x, --connections INTEGER`（默认 4）
- `--token TEXT`（环境变量回退：`ENTEROBASE_TOKEN`）
- `--format [text|json]` — 完成摘要的输出格式（默认 `text`）
- `--cache-dir PATH`

行为：

- 不带 `-s`：刷新 provider catalog。
- 带 `-s`：针对单个已缓存 scheme 的增量刷新/更新（只下载有变化的 locus 和 profile；详见 [数据源文档](providers.md#增量更新机制)）。

Provider 端点覆盖（用于自建 BIGSdb）：

- `GMLST_PUBMLST_BASE_URL`（默认：`https://rest.pubmlst.org/db`）
- `GMLST_PASTEUR_BASE_URL`（默认：`https://bigsdb.pasteur.fr/api/db`）
- `GMLST_PRIVATE_BIGSDB_URL`（注册私有 BIGSdb provider）
- `GMLST_PRIVATE_BIGSDB_NAME`（可选，默认：`private`）
- `GMLST_PRIVATE_BIGSDB_LABEL`（可选的显示标签）

示例：

```bash
export GMLST_PUBMLST_BASE_URL="http://127.0.0.1:8000/api/db"
gmlst scheme list -p pubmlst

export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
gmlst scheme list -p labdb
```

### scheme remove

```bash
gmlst scheme remove SCHEME [OPTIONS]
```

从本地缓存删除已下载的 scheme。

位置参数：

- `SCHEME` — 方案名称（如 `saureus_1`、`custom_1`）

选项：

- `-s, --scheme TEXT`（已弃用，请使用位置参数）
- `-p, --provider TEXT`（默认从缓存自动检测）
- `-y, --yes`（跳过确认提示）
- `-f, --format [text|json]`（默认 `text`）
- `--cache-dir PATH`

行为：

- 删除前显示 scheme 名称、provider、路径和大小，并请求确认。
- 本地自定义 scheme（`custom_*`，provider 为 `local`）会同时从本地 catalog 中移除。
- `--format json` 在删除成功后输出 `gmlst-scheme-op-v1` 信封：`{"scheme", "provider", "path", "removed": true}`。

示例：

```bash
gmlst scheme remove saureus_1 --yes
gmlst scheme remove custom_1 --format json
```

### scheme create

```bash
gmlst scheme create [OPTIONS]
```

选项：

- `-t, --type [mlst]`（必填）
- `-s, --source TEXT`（必填，基础方案名）
- `--data-dir, --datadir DIRECTORY`（必填，新等位基因数据目录；推荐 `--data-dir`）
- `--desc TEXT`
- `--cache-dir PATH`

### scheme update-custom

```bash
gmlst scheme update-custom SCHEME [OPTIONS]
```

位置参数：

- `SCHEME` — 自定义方案名（如 `custom_1`）

选项：

- `-s, --scheme TEXT`（已弃用，请使用位置参数）
- `--data-dir, --datadir DIRECTORY`（必填；推荐 `--data-dir`）
- `--cache-dir PATH`

### scheme export

```bash
gmlst scheme export SCHEME [OPTIONS]
```

位置参数：

- `SCHEME` — 方案名（如 `custom_1`）

选项：

- `-s, --scheme TEXT`（已弃用，请使用位置参数）
- `--format [grapetree|original]`（必填）
- `-o, --output PATH`（必填）
- `--cache-dir PATH`

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
gmlst utils extract -i genome.fasta -s ecoli_1 [--allele dnaN,tsvA]

# 2. 从 typing JSON 提取新等位基因
gmlst utils extract -i results.json --novel-allele --novel-profile --data-dir novel

# 3. TSV 回退模式（重新分型提取新等位基因）
gmlst utils extract -i results.tsv -s ecoli_1 --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel
```

主要选项：

- `-i, --input PATH`（必填）
- `-s, --scheme TEXT`（等位基因提取与 TSV 回退重分型时必填）
- `-p, --provider TEXT`
- `--allele TEXT`（逗号分隔的 locus 列表，默认方案全部 locus）
- `-b, --backend TEXT`（默认 `blastn`）
- `--novel-allele`
- `--novel-profile`
- `--data-dir PATH`
- `--samples-dir DIRECTORY`（TSV 回退 + `--novel-allele` 时使用）
- `--cache-dir PATH`

### utils concat

```bash
gmlst utils concat -i genome_mlst.fasta [-o genome_mlst_concat.fasta]
```

行为：

- 将输入 FASTA 记录按顺序拼接为一条 FASTA 序列。

### utils check

```bash
gmlst utils check -b blastn
```

行为：

- 运行后端依赖检查并报告可用性。
- 依赖缺失时以非零状态码退出。

### utils benchmark

```bash
gmlst utils benchmark [OPTIONS] SAMPLES...
```

选项：

- `-s, --scheme TEXT`（必填）
- `-b, --backends TEXT`（逗号分隔的 backend 列表，默认全部）
- `-r, --repeat INTEGER`（重复运行次数，用于稳定计时，默认 1）
- `-f, --format [table|tsv|json]`
- `--cgmlst-gate`（改为运行 cgMLST 预过滤开/关基准，而非 backend 基准）
- `--gate-max-mismatches INTEGER`（`--cgmlst-gate` 模式下允许的最大错配数，默认 0）
- `--gate-details-output PATH`
- `--gate-details-format [jsonl|tsv]`（默认 `jsonl`）
- `-o, --output PATH`
- `--cache-dir PATH`
- `--force-reindex`
- `-h, --help`

## config

```bash
gmlst config [OPTIONS] COMMAND [ARGS]...
```

检查和管理 gmlst 配置变量。

子命令：

- `env` — 以 shell 格式打印所有环境变量（可 source）
- `show` — 分组表格显示所有配置变量（密钥自动脱敏）
- `get NAME` — 获取单个变量当前值
- `set NAME [VALUE]` — 将变量写入配置文件

### config env

```bash
gmlst config env
```

为当前环境中已设置的每个变量打印 `export NAME="value"` 行，可直接 source：

```bash
eval "$(gmlst config env)"
```

### config show

```bash
gmlst config show
```

以分组表格（Cache、Provider、Security、Auth、cgMLST）显示全部 29 个配置变量：当前值（未设置时显示默认值）及说明。

### config get

```bash
gmlst config get NAME
```

打印单个变量的当前值，未设置时打印默认值。

```bash
gmlst config get GMLST_CACHE_DIR
```

凭证类值（API key、token）默认脱敏显示，避免密钥进入日志和终端记录。加 `--reveal` 才输出明文（显式、可审计的选择）；JSON 输出附带 `is_masked` 字段。

### config set

```bash
gmlst config set NAME VALUE
```

将 `export NAME="VALUE"` 写入 `~/.config/gmlst/env.sh`（权限 600）。在 shell 配置中 source 该文件即可生效：

```bash
gmlst config set GMLST_CACHE_DIR /data/gmlst-cache
source ~/.config/gmlst/env.sh   # 可选：gmlst 也会自动读取该文件
```

省略 VALUE 时改为提示输入 —— 密钥类使用隐藏输入并二次确认，值不会进入 shell 历史，确认输出只显示脱敏形式。

**注意**：provider URL 变量（`GMLST_PUBMLST_BASE_URL`、`GMLST_PRIVATE_BIGSDB_URL` 等）在导入时读取。必须先 `source` 配置文件再运行 gmlst，修改才会生效。

示例：

```bash
gmlst config show                          # 查看所有配置
gmlst config set GMLST_CACHE_DIR /data     # 设置缓存目录
gmlst config set GMLST_PUBMLST_API_KEY     # 隐藏输入提示录入密钥
source ~/.config/gmlst/env.sh              # 可选：gmlst 也会自动读取该文件
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

实现：

- 后端：Flask 路由（`/`、`/health`、`/api/mst`）
- 前端：Vue 3 应用，由 Vite 构建并以静态资源方式提供
  （`gmlst/web/frontend` -> `gmlst/web/static/visual/dist`）

功能：

- 基于 profile 距离（每 locus 等位基因差异数）构建 MST
- 支持缺失 token 罚分切换（`LNF`、`NIPH`、`NIPHEM` 等）
- 支持 `tree` 和 `radial` 两种布局
- 支持基于元数据的节点着色
- 支持 SVG 导出
- 接受 gmlst TSV 和 GrapeTree 风格 profile（`#Strain` 首列）

## JSON 输出信封

gmlst 写入 stdout 或输出文件的每个 JSON 文档都包裹在带版本号的信封中，
便于程序（以及 AI agent）在解析前进行版本校验：

```json
{
  "schema_version": "<常量>",
  "data": <原始 payload>
}
```

TSV/CSV/text/jsonl 输出不使用信封。

信封常量（定义在 `gmlst/schema_versions.py`）：

| 常量 | 适用范围 |
| --- | --- |
| `gmlst-typing-v1` | `typing mlst` / `typing cgmlst --format json`（样本结果列表） |
| `gmlst-tgmlst-profiles-v1` | `typing tgmlst --format json`（profile 列表） |
| `gmlst-tgmlst-stats-v1` | `typing tgmlst --stats`（stderr 统计文档） |
| `gmlst-scheme-list-v1` | `scheme list` / `scheme search --format json` |
| `gmlst-scheme-show-v1` | `scheme show --format json` |
| `gmlst-scheme-op-v1` | `scheme download` / `update` / `create` / `update-custom` / `remove --format json` 摘要 |
| `gmlst-benchmark-v1` | `utils benchmark --format json` |
| `gmlst-visual-mst-v1` | `visual mst --format json` |
| `gmlst-visual-mst-summary-v1` | `visual mst --format summary` |
| `gmlst-visual-matrix-v1` | `visual matrix --format json` |
| `gmlst-visual-heatmap-v1` | `visual heatmap --format json` |
| `gmlst-visual-compare-v1` | `visual compare --format json` |
| `gmlst-visual-locus-diff-v1` | `visual locus-diff --format json` |

`visual export` 使用自己已有的信封（`gmlst-visual-export-v1`，字段为
`kind`/`payload` 而非 `data`）。

往返兼容：`utils extract -i <typing json>` 同时接受新信封格式
（`gmlst-typing-v1`，读取 `data`）和旧版本 gmlst 输出的裸列表格式。
