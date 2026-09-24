# 流水线集成

gmlst 提供容器镜像与开箱即用的工作流示例（Nextflow、Snakemake 或纯 Docker），无需本地 conda 环境即可接入大规模监测流水线。

## Docker

镜像（Docker Hub 上的 `indexofire/gmlst`）内置 gmlst 与全部四个比对后端（BLAST+、minimap2、MUMmer4、KMA），以及 KMC 与 samtools：

```bash
# 拉取发布镜像
docker pull indexofire/gmlst:latest

# 分型单样本（挂载工作目录；scheme 缓存位于 /home/mambauser/.cache/gmlst）
docker run --rm -v "$PWD:/data" indexofire/gmlst:latest \
    typing mlst -s saureus_1 /data/sample.fna -o /data/result.tsv

# 批量：16 并行样本 + 持久化 scheme 缓存
docker run --rm -v "$PWD:/data" -v "$PWD/.gmlst-cache:/home/mambauser/.cache/gmlst" \
    indexofire/gmlst:latest \
    typing mlst -s saureus_1 -t 1 --max-workers 16 /data/assemblies/*.fna -o /data/batch.tsv
```

每个发布版本均有对应标签（`indexofire/gmlst:0.3.3`、`0.3` 等）。镜像构建内置冒烟测试（`gmlst --version`、`blastn`、`minimap2`、`kma`）——见 `.github/workflows/docker.yml`。

从本地源码构建：

```bash
docker build -t gmlst:local .
# 或固定精确 PyPI 版本：
docker build --build-arg GMLST_VERSION=0.3.3 -t gmlst:0.3.3 .
```

## Nextflow

见 [`examples/pipelines/gmlst_mlst.nf`](../../examples/pipelines/gmlst_mlst.nf)：

```bash
nextflow run gmlst_mlst.nf \
    --samples "assemblies/*.fna" \
    --scheme saureus_1 \
    -profile docker \
    -resume
```

该 process 输出每样本的 TSV + JSON 及用于溯源的 `versions.yml`。附加 CLI 参数通过 `--args "--minscore 50"` 传入。云端执行器上让 Nextflow 按样本扇出；每个任务内 gmlst 保持单样本运行（无需 `--max-workers`）。

## Snakemake

见 [`examples/pipelines/Snakefile`](../../examples/pipelines/Snakefile)：

```bash
snakemake -j 16 --use-singularity --config scheme=saureus_1 sample_dir=data/assemblies
```

## 并行策略建议

- 单机批量运行以 `--max-workers N` 为主要加速手段（实测数据见 README）。
- 工作流引擎中优先做任务级扇出（每任务一个样本）——每个任务内 gmlst 单样本、默认线程，资源申请可预测。
- 挂载持久缓存（`GMLST_CACHE_DIR` 或默认 `~/.cache/gmlst`），使 scheme 只在每个流水线实例中下载一次，而非每个任务一次。

## 容器中的环境变量

| 变量 | 容器中的典型取值 |
| --- | --- |
| `GMLST_CACHE_DIR` | 挂载卷，如 `/data/.gmlst-cache` |
| `GMLST_TMPDIR` | 挂载磁盘上的暂存空间（大批量场景） |
| `GMLST_PUBMLST_API_KEY` | 密钥注入，用于 2024 之后的 PubMLST 数据 |

完整变量列表见[配置参考](configuration.md)。
