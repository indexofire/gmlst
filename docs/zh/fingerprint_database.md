# 物种指纹数据库

指纹数据库支持 `gmlst typing mlst sample.fna`（零参数物种自动检测），通过基因组 k-mer 素描与物种指纹的包含度匹配实现。

## 设计原理

### 仅使用 MLST 方案 (v0.3.2+)

指纹**仅从 MLST 方案构建**（每物种 7 个看家基因）。cgMLST 方案被有意排除：

| 维度 | MLST 来源 | cgMLST 来源 |
|---|---|---|
| 下载时间 | 秒级 | 每方案分钟级 |
| 磁盘占用 | 每方案 KB 级 | 数百 MB |
| 物种区分度 | 足够（看家基因具物种特异性）| 对物种级鉴定无提升 |
| 指纹构建 | 全程 < 5 分钟 | 30+ 分钟（含限流重试）|

**核心洞察**：对于物种*鉴定*（非分型），7 个看家基因与 2000+ 核心基因组基因提供相同的区分度。使用 cgMLST 数据做指纹浪费下载时间和磁盘，且不提升检测精度。

### 物种名称匹配

目录按 organism 字符串精确分组。部分物种在不同 provider 下用了不同名称，可能导致某个物种在目录中显示"无 MLST 方案"，但实际上其他变体名称下存在。改进模糊名称匹配是后续优化方向。

## 覆盖范围

约 140-145 物种（PubMLST + Pasteur + Enterobase 联合目录中的 MLST 方案持有者）。

完整物种列表包含在打包的数据库文件中：`gmlst/data/species_fingerprints.json.gz`（随包分发）。

### 未覆盖物种

目录中无 MLST 方案的物种，包括：

- 仅有 cgMLST/wgMLST 方案的物种（如 Enterobacter hormaechei、Morganella morganii）
- 跨 provider 名称不匹配的物种
- 服务器端数据需要认证或已下线的物种

## 技术参数

| 参数 | 值 | 说明 |
|---|---|---|
| k-mer 长度 | 21 | 规范化（two-bit 编码）k-mer |
| 采样率 | 7 | 每 7 个 k-mer 哈希一次（减小指纹体积）|
| 每物种哈希上限 | 5,000 | 统一上限 |
| 评分方式 | 包含度 | |查询 ∩ 指纹| / |指纹| |
| 唯一判定 | top ≥ 0.3 且 top ≥ 2×第二名 | 歧义时列出候选让用户选择 |

## 文件位置

| 位置 | 路径 | 用途 |
|---|---|---|
| 用户构建 | `<缓存>/species_fingerprints.json.gz` | 最新数据 |
| 随包分发 | `gmlst/data/species_fingerprints.json.gz` | 安装即用（~1 MB）|
| 格式 | zlib 压缩 JSON | 80 MB 原始 → ~1 MB 压缩 |

## 查找顺序

`typing` 省略 `-s`/`-n` 时的优先级：

1. `<缓存>/species_fingerprints.json.gz`（用户构建）
2. `gmlst/data/species_fingerprints.json.gz`（随包分发）
3. 交互式提示是否立即构建（仅 TTY，拒绝则 exit 2）

## 重建

```bash
gmlst scheme update-fingerprints -y [-x N]
gmlst scheme update-fingerprints -o "Bordetella pertussis,Staphylococcus aureus"
```

### 注意事项

- 建议配置 PubMLST API key
- 已缓存的方案自动跳过（增量重建）
- 限流服务器可能导致临时失败；重跑即可
