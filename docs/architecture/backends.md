# Alignment Backends

The `Aligner` protocol, `AlleleMatch` normalization, and how BLAST+, KMA, minimap2, and MUMmer4 plug into one calling pipeline.

## Alignment backend architecture

### Protocol pattern

`gmlst/aligners/base.py` defines the `Aligner` `Protocol`. In Python, a `Protocol` is a structural interface. A backend does not need to inherit from one base class. It only needs to provide the required attributes and methods.

In practice, each aligner implementation must behave like this contract:

- `name`
- `supports_fastq`
- `check_dependencies()`
- `index(allele_fastas, index_dir)`
- `align(sample, index_path, loci, input_type)`

This lets `gmlst/core/pipeline.py` choose a backend once and then use it generically.

### `AlleleMatch` normalization

`gmlst/aligners/base.py` also defines `AlleleMatch` and `AlignmentResult`.

Every backend translates its native output into `AlleleMatch`, including:

- locus name
- allele id
- identity
- coverage
- score
- depth for read-based inputs when available
- extracted sequence for novel allele paths when available
- coordinate and copy-count metadata when available

This normalization is the key reason downstream calling can stay backend-agnostic.

### Backend implementations

- `gmlst/aligners/blastn.py` targets BLAST+ and FASTA-heavy workflows.
- `gmlst/aligners/kma.py` supports FASTA and FASTQ, and is the preferred cgMLST FASTQ route.
- `gmlst/aligners/minimap2.py` supports FASTA and FASTQ, plus representative and hash-prefilter driven cgMLST optimizations.
- `gmlst/aligners/nucmer.py` targets MUMmer4 for FASTA alignment.

## Minimal backend skeleton

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
        ...  # write native index files
        return index_dir

    def align(self, sample, index_path, loci, input_type) -> AlignmentResult:
        started = time.monotonic()
        hits = ...  # run the tool and parse its output
        matches = [
            AlleleMatch(
                locus=hit.locus,
                allele_id=hit.allele,
                identity=hit.identity,   # percent, 0-100
                coverage=hit.coverage,   # fraction, 0-1
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

## Choosing a backend

| Backend | Input | Strength | Typical cost |
| --- | --- | --- | --- |
| `blastn` | FASTA | precise, forgiving thresholds | slower on large schemes |
| `minimap2` | FASTA/FASTQ | fast, good for cgMLST | needs tuning for distant alleles |
| `nucmer` | FASTA | sensitive whole-genome comparison | slowest |
| `kma` | FASTA/FASTQ | read consensus, strong for FASTQ | needs k-mer index space |

The pipeline picks `minimap2` for FASTA cgMLST and `kma` for FASTQ; MLST
defaults to `blastn`. See [typing pipeline](typing-pipeline.md) for where those
defaults are applied.

## Normalization rules reviewers check

- One `AlleleMatch` per (locus, allele) hit, including multicopy hits.
- `identity` is a percentage in `[0, 100]`; `coverage` is a fraction in
  `[0, 1]`.
- `sequence` is populated only when the backend can extract the allele.
- `failed_loci` lists loci with no hit, so callers do not have to infer
  missingness from an empty match list.
- `copy_count` and contig coordinates are filled when the backend can report
  them; downstream code treats them as optional.
