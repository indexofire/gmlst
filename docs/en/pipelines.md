# Pipeline Integration

gmlst ships a container image and ready-to-adapt workflow snippets so it drops into large-scale surveillance pipelines (Nextflow, Snakemake, or plain Docker) without local conda setup.

## Docker

The image (`indexofire/gmlst` on Docker Hub) bundles gmlst plus all four alignment backends (BLAST+, minimap2, MUMmer4, KMA), KMC, pyrodigal dependencies, and samtools:

```bash
# Pull the release image
docker pull indexofire/gmlst:latest

# Type one sample (mount the working directory; schemes cache in /home/mambauser/.cache/gmlst)
docker run --rm -v "$PWD:/data" indexofire/gmlst:latest \
    typing mlst -s saureus_1 /data/sample.fna -o /data/result.tsv

# Batch with 16 parallel samples and reuse a persistent scheme cache
docker run --rm -v "$PWD:/data" -v "$PWD/.gmlst-cache:/home/mambauser/.cache/gmlst" \
    indexofire/gmlst:latest \
    typing mlst -s saureus_1 -t 1 --max-workers 16 /data/assemblies/*.fna -o /data/batch.tsv
```

Version-pinned images are tagged per release (`indexofire/gmlst:0.3.3`, `0.3`, …). The image build is smoke-tested (`gmlst --version`, `blastn`, `minimap2`, `kma`) before push — see `.github/workflows/docker.yml`.

Build locally from a checkout:

```bash
docker build -t gmlst:local .
# Or pin an exact PyPI version:
docker build --build-arg GMLST_VERSION=0.3.3 -t gmlst:0.3.3 .
```

## Nextflow

See [`examples/pipelines/gmlst_mlst.nf`](../examples/pipelines/gmlst_mlst.nf):

```bash
nextflow run gmlst_mlst.nf \
    --samples "assemblies/*.fna" \
    --scheme saureus_1 \
    -profile docker \
    -resume
```

The process emits per-sample TSV + JSON and a `versions.yml` for provenance. Pass extra CLI flags via `--args "--minscore 50"`. On cloud executors let Nextflow fan out per sample; inside each task gmlst stays single-sample (no `--max-workers` needed).

## Snakemake

See [`examples/pipelines/Snakefile`](../examples/pipelines/Snakefile):

```bash
snakemake -j 16 --use-singularity --config scheme=saureus_1 sample_dir=data/assemblies
```

## Parallelism guidance

- `--max-workers N` is the main speed lever for **single-host batch runs** (see the measured table in the README).
- In workflow engines, prefer **task-level fan-out** (one sample per task) — each task then runs gmlst with a single sample and default threading, which keeps resource requests predictable.
- Mount a persistent cache (`GMLST_CACHE_DIR` or the default `~/.cache/gmlst`) so schemes download once per pipeline instance, not once per task.

## Environment variables in containers

| Variable | Typical container value |
| --- | --- |
| `GMLST_CACHE_DIR` | a mounted volume, e.g. `/data/.gmlst-cache` |
| `GMLST_TMPDIR` | scratch space on a mounted disk for large batches |
| `GMLST_PUBMLST_API_KEY` | secret injection for post-2024 PubMLST data |

See the [Configuration Reference](configuration.md) for the full variable list.
