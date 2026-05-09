---
status: archived
archived_date: 2026-04-08
archived_from: docs/internal/reports/
archive_reason: "Historical aligner review snapshot; superseded by current implementation state"
---

# gmlst Aligner 代码审查报告

**审查日期**: 2025-03-13
**审查范围**: blastn, minimap2, kmerhash, nucmer 四个aligner实现
**审查重点**: Bug修复、性能优化、数据库/索引优化、比对结果提取优化

---

## 执行摘要

本次审查发现 **1个严重问题**、**3个中等问题** 和 **6个轻微问题/优化机会**。最严重的问题是BLASTN强制使用单线程，可能导致性能下降10-50倍。建议优先修复P0和P1级别的问题。

---

## 一、严重问题 (P0)

### 1.1 BLASTN 强制单线程 [blastn.py:159]

**问题描述**:
```python
"-num_threads", "1"  # 强制使用单线程
```

**影响**: 在多核系统上性能严重受限，相比多线程配置可能慢10-50倍。

**修复建议**:
```python
import os
num_threads = os.cpu_count() or 1
# ...
"-num_threads", str(num_threads),
```

**验证方式**: 对比单线程 vs 多线程在标准数据集上的运行时间。

---

## 二、中等问题 (P1)

### 2.1 kmerhash JSON 序列化内存爆炸 [kmerhash.py:105]

**问题描述**:
```python
idx_file.write_text(json.dumps(payload, separators=(",", ":")))
```

整个k-mer哈希表被序列化为单个JSON字符串，对于大型MLST方案（如大肠杆菌的数千个等位基因）可能导致：
- 内存峰值过高
- 序列化/反序列化速度慢
- 程序崩溃风险

**修复建议**:
```python
# 使用流式写入
with idx_file.open('w') as f:
    json.dump(payload, f, separators=(",", ":"))
```

**更优方案**: 迁移到二进制格式（msgpack）:
```python
import msgpack
with idx_file.open('wb') as f:
    msgpack.dump(payload, f)
```

### 2.2 kmerhash 每次重新加载整个索引 [kmerhash.py:124]

**问题描述**:
```python
payload = json.loads(index_path.read_text())
```

每次比对都要读取和解析整个JSON文件，对于大型scheme这是不必要的开销。

**修复建议**:
- 在进程内缓存已加载的索引
- 或使用内存映射文件（mmap）

```python
# 简单缓存方案
_index_cache: dict[Path, dict] = {}

def align(self, sample, index_path, loci, input_type):
    if index_path not in _index_cache:
        _index_cache[index_path] = json.loads(index_path.read_text())
    payload = _index_cache[index_path]
```

### 2.3 缺少增量更新支持 [所有aligner]

**问题描述**:
所有 `index()` 方法仅检查索引文件是否存在，不检查源文件是否更新：

```python
if not mmi.exists():  # 仅检查存在性
    build_index()
```

**影响**: 当等位基因数据库更新但索引已存在时，不会自动重建索引，导致使用过时的索引。

**修复建议** (以minimap2为例):
```python
def index(self, allele_fastas, index_dir):
    merged = index_dir / "alleles.fasta"
    
    # 检查是否需要重建
    need_rebuild = not merged.exists()
    if not need_rebuild:
        merged_mtime = merged.stat().st_mtime
        need_rebuild = any(
            f.stat().st_mtime > merged_mtime 
            for f in allele_fastas
        )
    
    if need_rebuild:
        with merged.open("w") as out:
            for fasta in sorted(allele_fastas):
                out.write(fasta.read_text())
    
    # 同样检查.mmi文件的新鲜度
    for preset, suffix in [(_FASTA_PRESET, "asm20"), (_FASTQ_PRESET, "sr")]:
        mmi = index_dir / f"alleles.{suffix}.mmi"
        if not mmi.exists() or mmi.stat().st_mtime < merged.stat().st_mtime:
            # 重建索引
```

---

## 三、轻微问题/优化机会 (P2-P3)

### 3.1 nucmer 不必要的磁盘 I/O [nucmer.py:120]

**问题**:
```python
result = run_cmd(["show-coords", "-rcl", "-T", str(delta)], capture=True)
coords.write_text(result.stdout)  # 先写入文件
matches = _parse_coords(coords, loci)  # 再读取
```

**优化**:
```python
result = run_cmd(["show-coords", "-rcl", "-T", str(delta)], capture=True)
matches = _parse_coords_from_string(result.stdout, loci)  # 直接解析字符串
```

### 3.2 kmerhash 内存使用优化

**当前问题**:
```python
def _extract_kmers(seq: str, k: int) -> list[str]:
    kmers: list[str] = []
    for i in range(len(seq) - k + 1):
        # ...
        kmers.append(min(kmer, rc))  # 构建完整列表
    return kmers  # 返回整个列表
```

返回完整列表而不是生成器，对于长序列占用大量内存。

**优化**:
```python
def _extract_kmers(seq: str, k: int) -> Iterator[str]:
    """Yield canonical k-mers lazily."""
    seq = seq.upper()
    for i in range(len(seq) - k + 1):
        kmer = seq[i:i+k]
        if "N" not in kmer:
            yield min(kmer, _revcomp(kmer))

# 使用时
for kmer in _extract_kmers(seq, k):
    if kmer in table:
        # 处理匹配
```

### 3.3 FASTA 合并优化

**当前实现** (所有aligner):
```python
with merged.open("w") as out:
    for fasta in sorted(allele_fastas):
        out.write(fasta.read_text())  # 读取整个文件到内存再写入
```

**优化方案**:
```python
import shutil

with merged.open("wb") as out:
    for fasta in sorted(allele_fastas):
        with fasta.open("rb") as src:
            shutil.copyfileobj(src, out, length=1024*1024)  # 1MB缓冲区
```

### 3.4 等位基因ID解析健壮性

**当前代码** [blastn.py:239-248]:
```python
def _split_allele_id(qseqid: str) -> tuple[str, str]:
    for sep in ("_", "-"):
        if sep in qseqid:
            locus, allele_id = qseqid.rsplit(sep, 1)
            return locus, allele_id
    return qseqid, "1"  # 默认返回"1"可能不正确
```

**问题**:
- 对于 `locus_sub_locus_allele` 格式会错误分割
- 默认返回"1"可能掩盖解析错误

**建议**:
```python
def _split_allele_id(qseqid: str) -> tuple[str, str]:
    """Split allele ID from header like 'arcC_1' or 'arcC-1'.
    
    Handles edge cases and validates format.
    """
    # 尝试最常见的分隔符
    for sep in ("_", "-"):
        if sep in qseqid:
            parts = qseqid.rsplit(sep, 1)
            if len(parts) == 2 and parts[1].isdigit():
                return parts[0], parts[1]
    
    # 无法解析时发出警告
    logger.warning(f"Could not parse allele ID from '{qseqid}', using as-is")
    return qseqid, ""
```

---

## 四、架构级优化建议

### 4.1 统一身份和覆盖率计算

**当前状态**: 不同backend使用不同的identity/coverage计算方法，可能导致结果不一致。

| Backend | Identity | Coverage |
|---------|----------|----------|
| blastn | pident (来自BLAST) | aln_len / qlen |
| minimap2 | nmatch/blen*100 | (qend-qstart)/qlen |
| kmerhash | 阈值硬编码 | hits/total_kmers |
| nucmer | %IDY (来自show-coords) | covq/100 |

**建议**: 
- 在 `AlleleMatch` 类中标准化计算方法
- 添加文档说明每种backend的近似性

### 4.2 添加 Paralog 检测

**当前实现**: 仅保留每个(locus, allele_id)的最佳匹配。

**建议**: 保留多个匹配供后续分析:
```python
@dataclass
class AlignmentResult:
    # ...
    ambiguous_matches: dict[str, list[AlleleMatch]] = field(default_factory=dict)
    """Loci with multiple high-quality matches (potential paralogs)."""
```

### 4.3 阈值可配置化

**当前**: 阈值在 `base.py` 中硬编码:
```python
if self.identity >= 95.0 and self.coverage >= 0.95:
    return "closest"
```

**建议**: 支持scheme特定的阈值配置:
```python
@dataclass
class Scheme:
    # ...
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "exact_identity": 100.0,
        "exact_coverage": 1.0,
        "closest_identity": 95.0,
        "closest_coverage": 0.95,
    })
```

---

## 五、实施路线图

### Phase 1: 紧急修复 (1-2天)
1. ✅ 修复BLASTN单线程问题
2. ✅ 添加增量更新检查
3. ✅ 修复kmerhash JSON流式写入

### Phase 2: 性能优化 (1周)
1. kmerhash内存优化（生成器、缓存）
2. nucmer避免中间文件
3. FASTA合并优化

### Phase 3: 架构改进 (2-4周)
1. 统一identity/coverage计算
2. 添加paralog检测
3. 阈值可配置化
4. 索引格式优化（JSON→msgpack）

---

## 六、测试建议

针对每项修复/优化，建议以下测试：

1. **性能测试**: 使用标准数据集（如100个金黄色葡萄球菌基因组）对比修复前后的运行时间
2. **正确性测试**: 对比修复前后的ST分型结果一致性
3. **内存测试**: 使用`memory_profiler`监控kmerhash的内存使用峰值
4. **并发测试**: 测试多线程BLASTN在不同CPU核心数下的扩展性

---

## 附录: 代码审查检查清单

- [ ] BLASTN使用多线程
- [ ] 所有aligner支持增量更新
- [ ] kmerhash使用流式JSON写入
- [ ] kmerhash使用生成器而非列表
- [ ] nucmer直接解析stdout
- [ ] FASTA合并使用缓冲区复制
- [ ] 等位基因ID解析添加验证
- [ ] 统一identity/coverage计算标准
- [ ] 添加阈值配置支持
- [ ] 添加paralog检测

---

*报告生成时间: 2025-03-13*
*审查工具: 人工代码审查 + 静态分析*
