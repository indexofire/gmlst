# Output and Formats

TSV markers, JSON versus TSV, versioned envelopes, stdout/stderr separation, `--stats`, and GrapeTree export.

## Output Questions

### What do TSV markers mean?

- `23`, exact allele call
- `~23`, closest or non-exact high-coverage call
- `15?`, partial call
- `-`, missing locus

### Should I use JSON or TSV?

Use TSV when you want compact, table-friendly output. Use JSON when you need full structured details such as per-locus metadata and `novel_sequence` fields.

Example:

```bash
gmlst typing mlst -s saureus_1 --format tsv sample.fasta -o result.tsv
gmlst typing mlst -s saureus_1 --format json sample.fasta -o result.json
```

### What is `schema_version` / the JSON envelope?

Every JSON document gmlst writes to stdout or an output file is wrapped in a versioned envelope:

```json
{
  "schema_version": "gmlst-typing-v1",
  "data": [ "...the actual payload..." ]
}
```

The constant tells you which payload shape to expect before you parse `data`. If a future release changes a payload, the constant changes too, so scripts and AI agents can detect format drift instead of misreading it. TSV, CSV, and plain-text outputs are not enveloped.

The full constant table is in the [Command Reference](../usage/cli/index.md#json-output-envelope). Older gmlst versions emitted bare payloads; `utils extract -i <typing json>` still accepts both forms.

### Why are warnings on stderr and stdout only data?

So you can pipe and parse safely. Everything you need to parse comes out of stdout, and everything meant for a human (warnings, progress bars, spinners, "Results written to" notices) goes to stderr. A command like this keeps working even when gmlst logs warnings mid-run:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 *.fna --format tsv | gmlst visual mst --input - --format summary
```

### Where did `--stats` output go?

`typing tgmlst --stats` prints its statistics JSON to stderr, not stdout. This keeps stdout data-only (see the previous question). To capture it, redirect stderr:

```bash
gmlst typing tgmlst --stats sample.fasta 2> stats.json
```

### GrapeTree export does not work for my scheme

GrapeTree export is intended for public or custom schemes that have the expected profile structure. If export fails, confirm the scheme is a downloaded public scheme or a custom scheme built through `gmlst scheme create`.

Example workflow:

```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection"
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

## Full row example

TSV:

```text
FILE        SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample.fna  saureus_1   1   1     1     1     1    1    1    1
```

JSON (abridged):

```json
{
  "schema_version": "gmlst-typing-v1",
  "data": [
    {
      "file": "sample.fna",
      "scheme": "saureus_1",
      "st": "1",
      "score": 100.0,
      "status": "PERFECT",
      "alleles": {"arcC": {"call": "1", "identity": 100.0, "coverage": 1.0}}
    }
  ]
}
```

Filter during a batch run instead of post-processing:

```bash
gmlst typing mlst -s saureus_1 --minscore 50 --format json *.fna -o qc.json
```

## Marker quick reference

| Marker | Meaning | ST assigned? |
| --- | --- | --- |
| `23` | exact, single copy | yes |
| `23*` | exact, same-allele multicopy | yes (uses `23`) |
| `~23` | closest or novel | no |
| `15?` | partial coverage | no |
| `1,2` | conflicting multicopy | no |
| `-` | missing | no |
