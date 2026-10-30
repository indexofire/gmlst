# 性能优化

后端选择、线程与 worker 调优、分批策略，以及实测的并行加速比。

## 性能优化建议

### 哪个后端通常最快？

没有一个答案适合所有场景，但可以从下面这些经验开始：

- assembly MLST，先试 `blastn` 或 `minimap2`
- FASTQ 分型，先试 `kma`
- FASTA cgMLST，先试 `minimap2` 配合合适的 chew 风格模式
- 大型 FASTQ cgMLST，预期会走 KMA-first 路径

### 线程应该怎么调？

很多独立样本时，优先考虑样本级并行。单样本很重时，再加后端线程。

`--max-workers N` 与 `-t/--threads` 是互补而非可叠加的关系：`--max-workers > 1` 时每样本的后端线程强制为 1 并打印警告。样本多时一律优先 `--max-workers` — 尤其是配合 `kma` 和 `nucmer` 后端：它们的单样本比对完全无法利用多线程（实测 `kma -t 1` 与 `-t 16` 相差仅 ~5%）。

例如：

```bash

## 先选对杠杆

| 场景 | 杠杆 | 示例 |
| --- | --- | --- |
| 多个小样本 | `--max-workers` | `--max-workers 16` |
| 单个大 cgMLST 样本 | `-t` | `-t 8` |
| 反复处理同一批样本 | 缓存复用 | 只下载并建索引一次 |
| FASTQ 批次 | `kma` + worker | `-b kma --max-workers 16` |

用基准测试代替猜测：

```bash
gmlst utils benchmark -s saureus_1 -b blastn,minimap2,nucmer -r 3 samples/*.fna
gmlst utils benchmark -s vparahaemolyticus_3 --cgmlst-gate -b minimap2 samples/*.fna
```

`--max-workers` 与 `-t` 不能叠加：worker 大于 1 时，每样本线程会被强制为 1。
这是有意设计，两者同时设置时 CLI 会给出警告。

## 分阶段调优示例

```bash
# 1. 先用默认值测实际耗时
time gmlst typing mlst -s saureus_1 -t 8 sample.fna

# 2. 样本多？优先 worker
time gmlst typing mlst -s saureus_1 -t 1 --max-workers 16 samples/*.fna

# 3. 大 cgMLST 方案？保留每样本线程
time gmlst typing cgmlst -s vparahaemolyticus_3 -t 8 sample.fna
```
