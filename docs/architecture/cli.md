# CLI Layer

How Click commands are registered, how `typing` dispatch works, and which policies belong in the command layer rather than in backends.

## CLI layer

### Top-level command registration

`gmlst/cli.py` registers four top-level groups:

- `typing`
- `scheme`
- `utils`
- `visual`

`gmlst/__main__.py` makes the same entrypoint available through `python -m gmlst`.

### Typing command dispatch

Typing commands are implemented in `gmlst/commands/typing.py`. This module handles:

- sample preparation
- scheme type detection
- backend and mode validation
- temporary directory policy
- streaming versus final output
- optional novel allele/profile extraction

`gmlst/commands/typing_runner.py` adds sample-level parallel execution. When `--max-workers` is used, it forces per-sample backend threads to `1` and fans work out across samples.

### Scheme command responsibilities

`gmlst/commands/scheme.py` handles:

- catalog listing and refresh
- downloads and updates
- blocked scheme filtering via `gmlst/commands/common.py`
- local custom scheme creation and update under the `local` provider namespace

### FASTQ cgMLST policy at the command layer

The command layer owns one important policy decision. For cgMLST runs with FASTQ input, the backend is KMA-first. If the user selects `minimap2`, `gmlst/commands/typing.py` detects FASTQ samples and switches to `kma`, then forces `cgmlst_mode=fast`.

This keeps FASTQ cgMLST behavior explicit and avoids pretending that FASTA-only chew-style optimization branches apply to raw reads.

## Command-to-module map

| User command | Entry module | Main collaborators |
| --- | --- | --- |
| `typing mlst` / `typing cgmlst` | `commands/typing.py` | `typing_runner.py`, `typing_output.py`, `core/pipeline.py` |
| `typing tgmlst` | `commands/typing_schemefree.py` | `schemefree/typing_engine.py` |
| `typing mlst --guess` | `commands/typing_guess_run.py` | `commands/typing_options.py`, providers |
| `scheme download` | `commands/scheme.py` | `database/cache.py`, `database/download.py` |
| `scheme update` | `commands/scheme_update.py` | providers, `database/download.py` |
| `scheme update-fingerprints` | `commands/scheme_fingerprints.py` | `data/species_fingerprints.json.gz` |
| `utils extract` | `commands/utils.py` → `utils_extract.py` | `novel/service.py` |
| `visual web` | `visual/cli.py` | `visual/app.py`, `visual/mst.py` |

## Example: tracing the FASTQ policy

```text
gmlst typing cgmlst -b minimap2 reads_R1.fq.gz reads_R2.fq.gz
  commands/typing.py
    -> readers/sample.py: detect FASTQ pair
    -> policy: cgMLST FASTQ is KMA-first
    -> rewrite backend to kma, set cgmlst_mode = fast
    -> core/pipeline.py with KmaAligner
```

The rewrite happens before any index is built, so the run never pays for a
FASTA-only index. To change this rule, change it here rather than inside
`aligners/kma.py` or `aligners/minimap2.py`.

## Policy checklist for new command behaviour

- Is this validation about user input? Keep it in `commands/`.
- Is this an algorithm or data transformation? Put it in `core/` or `calling/`.
- Is this a tool invocation? Put it in `aligners/` or `database/download.py`.
- Does the behaviour differ by input type? Decide once, at the command layer,
  and pass an explicit option downstream.
