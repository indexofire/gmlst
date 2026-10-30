# 比对后端

`Aligner` 协议、`AlleleMatch` 标准化，以及 BLAST+、KMA、minimap2、MUMmer4 如何接入同一条调用流水线。

## 比对后端架构

### Protocol 模式

`gmlst/aligners/base.py` 定义了 `Aligner` `Protocol`。在 Python 里，`Protocol` 表示结构化接口。实现类不一定要继承某个基类，只要满足接口要求即可。

在本项目中，每个 aligner 都必须提供以下能力：

- `name`
- `supports_fastq`
- `check_dependencies()`
- `index(allele_fastas, index_dir)`
- `align(sample, index_path, loci, input_type)`

这样 `gmlst/core/pipeline.py` 只需要在一开始选定后端，后续就能用统一方式调用。

### `AlleleMatch` 标准化

`gmlst/aligners/base.py` 还定义了 `AlleleMatch` 和 `AlignmentResult`。

每个后端都必须把自己的原生输出转换成 `AlleleMatch`，其中包括：

- locus 名称
- allele id
- identity
- coverage
- score
- 读段输入时可用的 depth
- novel allele 路径可用的提取序列
- 坐标和 copy count 等附加信息

这一步标准化，是后续 calling 逻辑能够后端无关的关键原因。

### 后端实现

- `gmlst/aligners/blastn.py` 面向 BLAST+，偏 FASTA 工作流。
- `gmlst/aligners/kma.py` 支持 FASTA 和 FASTQ，也是 cgMLST FASTQ 的优先路径。
- `gmlst/aligners/minimap2.py` 支持 FASTA 和 FASTQ，并提供 representative 与 hash-prefilter 相关优化。
- `gmlst/aligners/nucmer.py` 基于 MUMmer4，面向 FASTA 比对。

## 最小后端骨架

```python
import shutil
import time
from pathlib import Path

from gmlst.aligners.base import AlleleMatch, AlignmentResult


class MyToolAligner:
    name = "mytool"
    supports_fastq = False

    def check_dependencies(self) -> None:
        if shutil.which("mytool") is None:
            raise RuntimeError("mytool is not installed")

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        index_dir.mkdir(parents=True, exist_ok=True)
        ...  # 写入工具原生索引
        return index_dir

    def align(self, sample, index_path, loci, input_type) -> AlignmentResult:
        started = time.monotonic()
        hits = ...  # 运行工具并解析输出
        matches = [
            AlleleMatch(
                locus=hit.locus,
                allele_id=hit.allele,
                identity=hit.identity,   # 百分比，0-100
                coverage=hit.coverage,   # 比例，0-1
                score=hit.score,
                depth=None,
                sequence=hit.sequence,
            )
            for hit in hits
        ]
        return AlignmentResult(
            sample_id=sample.sample_id,
            matches=matches,
            failed_loci=[],
            backend=self.name,
            runtime_seconds=time.monotonic() - started,
        )
```

## 后端选择

| 后端 | 输入 | 优势 | 典型代价 |
| --- | --- | --- | --- |
| `blastn` | FASTA | 精确、阈值宽容 | 大方案上较慢 |
| `minimap2` | FASTA/FASTQ | 快，适合 cgMLST | 远端等位基因需要调参 |
| `nucmer` | FASTA | 敏感的全基因组比较 | 最慢 |
| `kma` | FASTA/FASTQ | reads 共识，FASTQ 强项 | 需要 k-mer 索引空间 |

流水线为 FASTA cgMLST 选择 `minimap2`，FASTQ 选择 `kma`，MLST 默认
`blastn`。这些默认值在哪里生效见[分型流水线](typing-pipeline.zh.md)。

## 评审会检查的标准化规则

- 每个 (locus, allele) 命中对应一个 `AlleleMatch`，包括多拷贝命中。
- `identity` 是 `[0, 100]` 的百分比；`coverage` 是 `[0, 1]` 的比例。
- 只有后端能够提取序列时才填充 `sequence`。
- `failed_loci` 列出完全没有命中的 locus，避免调用方从空列表推断缺失。
- 后端能报告时填充 `copy_count` 与 contig 坐标；下游按可选字段处理。
