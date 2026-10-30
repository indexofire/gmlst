# 一般问题

gmlst 是什么、MLST 与 cgMLST 的区别，以及报告问题时应该附带哪些信息。

### gmlst 是什么？

`gmlst` 是一个面向细菌基因组分型的 Python CLI，支持传统 MLST、更大规模的 cgMLST 和 wgMLST，以及通过 `gmlst typing tgmlst` 运行的 scheme-free 分型。

### MLST 和 cgMLST 有什么区别？

- MLST 通常只使用少量 housekeeping loci，常见是 7 个
- cgMLST 会使用更大规模的核心基因位点集合
- wgMLST 还会进一步扩展到更多 accessory loci

实际使用时，MLST 更轻量，适合快速分型。cgMLST 分辨率更高，但也更依赖计算资源和较完整的位点回收。

### 为什么 gmlst 要支持多个比对后端？

因为不同输入类型和工作负载适合的工具不同：

- `blastn` 适合 assembly 场景下的基础 MLST
- `kma` 很适合 read-based 工作流，尤其是 cgMLST FASTQ 路径
- `minimap2` 在组装和部分 reads 工作流中速度快、适应性强
- `nucmer` 可用于组装比较和补充证据

项目会把不同后端的结果统一归一化，这样下游 calling 逻辑可以保持一致。

## 还是没有解决？

如果你要提 issue 或反馈问题，建议附上这些信息：

- 你执行的完整命令
- 安装方式，pixi 还是 pip
- 输入类型，FASTA 还是 FASTQ
- backend 名称
- scheme 名称
- 相关 stderr 输出
- 用 `--format json` 是否还能复现

这样更容易复现问题，也更容易定位原因。

## 提问前先自查

先收集下面三项输出，它们通常就能回答大部分问题：

```bash
gmlst --version
gmlst config show            # 值与来源，密钥自动脱敏
gmlst utils check -b blastn  # 对你实际使用的后端各跑一次
```

然后用 JSON 复现问题，它保留逐 locus 证据：

```bash
gmlst typing mlst -s saureus_1 --format json sample.fna -o debug.json
```

## 症状与页面对照

| 症状 | 页面 |
| --- | --- |
| `command not found`、Python 版本错误 | [安装](installation.zh.md) |
| `Scheme ... not found`、下载失败 | [方案](schemes.zh.md) |
| `ST = -`、locus 缺失或部分调用 | [分型](typing.zh.md) |
| TSV 标记异常或输出为空 | [输出](output.zh.md) |
| 环境变量或临时文件 | [配置](configuration.zh.md) |
| 运行慢、线程调优 | [性能](performance.zh.md) |
| 退出码与单行报错 | [错误](errors.zh.md) |
