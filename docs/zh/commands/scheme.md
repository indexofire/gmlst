[← 命令参考](../commands.md)

# gmlst scheme

用于管理方案目录、下载缓存、自定义方案和导出结果。

## list

列出提供方中的可用方案，或只查看已经缓存的方案。

### 用法
```bash
gmlst scheme list [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-p, --provider [<registered-provider>\|local\|all]` | 按提供方过滤。 | `all` |
| `-t, --type [mlst\|cgmlst\|wgmlst\|all]` | 按方案类型过滤。 | `all` |
| `-n, --name TEXT` | 按 organism 名称的正则表达式过滤，大小写不敏感。 | 无 |
| `-f, --format [text\|table\|csv\|tsv\|json]` | 输出格式。 | `table` |
| `-a, --available` | 只显示已经下载并缓存的方案。 | 关闭 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme list
gmlst scheme list -p pubmlst -t mlst
gmlst scheme list -p local -a -f json
```

### 注意事项
- `scheme list` 会按 `gmlst/data/blocked_schemes.json` 过滤被隐藏的方案。
- `--name` 使用正则表达式，写错表达式会直接报错。

---

## download

从目录中下载指定方案到本地缓存。

### 用法
```bash
gmlst scheme download [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定要下载的方案名。 | 必填 |
| `--force` | 即使本地已有缓存，也重新下载。 | 关闭 |
| `-q, --quiet` | 仅保留错误输出。 | 关闭 |
| `--download-tool [auto\|aria2c\|curl\|wget\|httpx\|requests]` | 选择下载后端。 | `auto` |
| `-x, --connections INTEGER` | 限制并发连接或下载数量。 | 无 |
| `--token TEXT` | API token，仅主要用于 Enterobase 路径。 | 无 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme download -s saureus_1
gmlst scheme download -s vparahaemolyticus_3 --download-tool aria2c -x 8
```

### 注意事项
- 如果方案已缓存且没有指定 `--force`，命令会直接提示已存在并退出。
- 被 blocked 的方案不能通过 `download` 下载。

---

## update

更新提供方目录，或刷新一个或多个本地缓存方案。

### 用法
```bash
gmlst scheme update [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 只更新指定的已缓存方案。 | 无 |
| `-a, --all` | 更新所有已缓存的方案。 | 关闭 |
| `-f, --force` | 在更新动作前强制刷新提供方目录。 | 关闭 |
| `--token TEXT` | API token，用于需要认证的下载路径。 | 无 |
| `--download-tool [auto\|aria2c\|curl\|wget\|httpx\|requests]` | 选择用于方案刷新时的下载后端。 | `auto` |
| `-x, --connections INTEGER` | 限制并发连接或下载数量。 | 无 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme update
gmlst scheme update -s saureus_1
gmlst scheme update -a -f
```

### 注意事项
- 不带 `-s` 和 `-a` 时，命令会更新所有提供方目录。
- 指定 `-s` 时，命令会根据 catalog 自动判断该方案属于哪个提供方。
- `--scheme` 和 `--all` 不能同时使用。

---

## show

显示某个方案的详细信息。

### 用法
```bash
gmlst scheme show [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定要查看的方案。 | 无 |
| `-f, --format [text\|table\|csv\|tsv\|json]` | 输出格式。 | `table` |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme show -s saureus_1
gmlst scheme show -s saureus_1 -f json
```

### 注意事项
- 带 `-s` 时会显示单个方案的详情。
- 不带 `-s` 时会先提示用法，然后回退为 `scheme list` 的输出。

---

## create

把公开方案和 novel 数据合并成一个新的本地自定义方案。

### 用法
```bash
gmlst scheme create [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-t, --type [mlst]` | 指定方案类型，目前只支持 `mlst`。 | 必填 |
| `-s, --source TEXT` | 指定要扩展的源方案。 | 必填 |
| `--data-dir, --datadir DIRECTORY` | novel 数据目录，需包含 `*_novel.fasta` 和 `profiles_novel.txt`。 | 必填 |
| `--desc TEXT` | 自定义方案描述。 | 空字符串 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection 2024"
```

### 注意事项
- 新方案会自动命名为 `custom_1`、`custom_2` 这类形式。
- 创建前会校验 novel 数据是否和源方案位点集合一致。

---

## update-custom

向已有本地自定义方案追加新的 novel allele 和 novel profile。

### 用法
```bash
gmlst scheme update-custom [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定要更新的自定义方案，例如 `custom_1`。 | 必填 |
| `--data-dir, --datadir DIRECTORY` | 新的 novel 数据目录。 | 必填 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data
```

### 注意事项
- 只支持更新 `custom_*` 形式的本地方案。
- 新增 allele 和 profile 会沿用现有编号继续追加，不会从头重排。

---

## export

把方案 profile 数据导出为原始格式或 GrapeTree 兼容格式。

### 用法
```bash
gmlst scheme export [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `-s, --scheme TEXT` | 指定要导出的方案。 | 必填 |
| `--format [grapetree\|original]` | 导出格式。 | 必填 |
| `-o, --output PATH` | 输出文件路径。 | 必填 |
| `--cache-dir PATH` | 覆盖缓存目录。 | 无 |

### 示例
```bash
gmlst scheme export -s custom_1 --format grapetree -o custom_1_grapetree.tsv
gmlst scheme export -s saureus_1 --format original -o saureus_1.txt
```

### 注意事项
- `grapetree` 会输出带 `#Strain` 风格首列的 TSV，适合后续 MST 可视化。
- `original` 会直接复制方案原始 profile 文件。

---

## 提供方端点环境变量

以下环境变量可用于覆盖内置 provider 端点，或注册私有 BIGSdb 实例。

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `GMLST_PUBMLST_BASE_URL` | 覆盖 PubMLST API 根地址。 | `https://rest.pubmlst.org/db` |
| `GMLST_PASTEUR_BASE_URL` | 覆盖 Pasteur BIGSdb API 根地址。 | `https://bigsdb.pasteur.fr/api/db` |
| `GMLST_PRIVATE_BIGSDB_URL` | 注册一个额外的私有 BIGSdb 提供方。 | 未设置 |
| `GMLST_PRIVATE_BIGSDB_NAME` | 私有 BIGSdb 的 provider 名称。 | `private` |
| `GMLST_PRIVATE_BIGSDB_LABEL` | 私有 BIGSdb 的显示标签。 | `Private BIGSdb` |

### 示例
```bash
export GMLST_PUBMLST_BASE_URL="http://127.0.0.1:8000/api/db"
gmlst scheme list -p pubmlst

export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```
