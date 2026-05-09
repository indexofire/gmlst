# 安装指南

本指南介绍 `gmlst` 的安装方式，以及如何确认 CLI 和后端工具已经可以正常使用。

`gmlst` 是一个基于 Python 3.12 的命令行工具，用于细菌基因组的 MLST、cgMLST 和 wgMLST 分型。最推荐的安装方式是使用 [Pixi](https://pixi.sh/)，因为它不仅管理 Python 依赖，也会一起安装各个比对后端所需的外部生物信息学工具。

## 系统要求

| 项目 | 最低要求 | 推荐配置 | 说明 |
|---|---:|---:|---|
| 操作系统 | Linux、macOS | Linux、macOS | 当前 Pixi 支持的平台为 `linux-64`、`osx-arm64`、`osx-64` |
| Python | 3.12 | 3.12 | 使用 pip 或源码安装时需要 |
| 内存 | 2 GB RAM | 8 GB RAM 以上 | 较大的 cgMLST 方案会更吃内存 |
| 磁盘空间 | 1 GB 可用空间 | 5 GB 以上 | 包含程序、本地索引、缓存方案和临时文件 |

## 安装方式

### 方式 1：使用 Pixi 安装（推荐）

如果你希望安装过程最省心，建议直接使用 Pixi。Pixi 会统一管理：

- Python 解释器
- Python 依赖包
- 外部工具，例如 `blastn`、`kma`、`minimap2`、`nucmer`、`samtools`、`kmc`
- 项目任务，例如 `pixi run start`、`pixi run test`、`pixi run check`

### 第 1 步：安装 Pixi

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

安装完成后，如果终端里暂时找不到 `pixi`，请重新打开一个 shell。

### 第 2 步：克隆仓库

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
```

### 第 3 步：安装项目环境

```bash
pixi install
```

这一步会读取 `pixi.toml`，创建环境，并安装 Python 依赖和外部工具。

### 第 4 步：进入 Pixi shell

```bash
pixi shell
```

进入后，`gmlst` 以及相关后端工具都会自动出现在 `PATH` 中。

### 第 5 步：验证 CLI

```bash
gmlst --version
gmlst --help
gmlst utils check -b blastn
```

如果你不想进入交互式 shell，也可以直接这样运行：

```bash
pixi run gmlst --help
pixi run gmlst utils check -b blastn
```

### 方式 2：使用 pip 安装

如果你更习惯标准 Python 虚拟环境，也可以使用 pip 安装。不过这种方式需要你自己额外安装后端依赖工具。

### 第 1 步：创建并激活虚拟环境

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 第 2 步：安装 `gmlst`

```bash
pip install gmlst
```

### 第 3 步：单独安装外部生物信息学工具

如果使用 pip，`gmlst` 的 Python 包会安装好，但 `blastn`、`kma`、`minimap2`、`nucmer` 等后端工具需要你自己安装。

完整工具列表和安装命令见下方的 [外部依赖](#外部依赖)。

### 第 4 步：验证安装

```bash
gmlst --version
gmlst --help
gmlst utils check -b blastn
```

### 方式 3：从源码安装

如果你要进行本地开发、调试，或者修改文档，源码安装最合适。

### 第 1 步：克隆仓库

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
```

### 第 2 步：创建并激活虚拟环境

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 第 3 步：以 editable 模式安装

```bash
pip install -e .
```

这一步会根据 `pyproject.toml` 安装项目，并在本地生成 `gmlst` 命令入口。

### 第 4 步：安装后端工具

源码安装只会安装 Python 包，不会自动安装 `blastn`、`kma`、`minimap2`、`nucmer` 等外部工具。除非你改用 Pixi，否则仍然需要手动安装这些后端依赖。

### 第 5 步：验证安装

```bash
gmlst --version
gmlst --help
gmlst utils check -b blastn
```

## 验证安装

无论你使用哪种安装方式，都建议做下面几步检查。

### 检查版本

```bash
gmlst --version
```

示例输出：

```text
gmlst, version 0.1.0
```

### 检查帮助信息

```bash
gmlst --help
```

你应该能看到这些主命令组：

```text
Commands:
  typing
  scheme
  utils
  visual
```

### 检查后端工具是否可用

```bash
gmlst utils check -b blastn
gmlst utils check -b minimap2
gmlst utils check -b kma
gmlst utils check -b nucmer
```

示例输出：

```text
[OK] backend=blastn is available
```

### 运行一个简单的方案查询

```bash
gmlst scheme list -p pubmlst -t mlst
```

如果网络正常，也可以继续下载一个方案再查看：

```bash
gmlst scheme download -s saureus_1
gmlst scheme show -s saureus_1
```

## 平台说明

### Linux

- Linux 是最直接、最稳定的安装平台。
- `linux-64` 是项目当前支持的 Pixi 平台。
- 在服务器或集群环境中，推荐使用 Pixi 或 Conda，避免工具版本不一致。

### macOS

### Apple Silicon（ARM64）

- `osx-arm64` 已在 Pixi 配置中支持。
- 对于 Apple Silicon，Pixi 往往是最简单的方式，因为它会自动解析兼容的二进制包。
- 如果你使用 Homebrew 手动安装，请确认当前 shell 使用的是 ARM64 对应的 Homebrew 前缀。

### Intel macOS

- `osx-64` 同样受支持。
- 使用 Pixi、Homebrew 或 Conda 都可以。

### Rosetta 2

- 某些第三方生物信息学工具在 ARM64 和 x86_64 下的表现可能不同。
- 如果某个工具只有 x86_64 版本更稳定，可能需要在 Rosetta shell 中运行对应环境。
- 建议先优先尝试原生 ARM64，只有在特定工具失败时再考虑 Rosetta。

### Windows

- 当前仓库的主要目标平台不是原生 Windows。
- 实际使用时，推荐通过 **WSL2** 安装 Ubuntu 或其他 Linux 发行版。
- 请在 WSL2 里安装 Pixi、Python 和后端工具，不要混用 PowerShell 里的环境。

WSL2 示例流程：

```bash
sudo apt update
sudo apt install -y curl git
curl -fsSL https://pixi.sh/install.sh | bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi shell
gmlst --version
```

## 外部依赖

如果你使用 Pixi，这些工具会自动安装。如果你使用 pip 或源码安装，则需要根据自己打算使用的后端手动安装对应工具。

| 工具 | 作用 | 对应后端或功能 | Conda 安装命令 | Homebrew 安装命令 |
|---|---|---|---|---|
| `blastn`, `makeblastdb` | 核酸比对和索引构建 | `blastn` 后端 | `conda install -c bioconda blast` | `brew install blast` |
| `minimap2` | 组装序列和测序 reads 比对 | `minimap2` 后端 | `conda install -c bioconda minimap2` | `brew install minimap2` |
| `nucmer`, `show-coords` | 全基因组比对 | 通过 MUMmer4 提供 `nucmer` 后端 | `conda install -c bioconda mummer4` | `brew install mummer` |
| `kma` | 基于 k-mer 的分型和比对 | `kma` 后端 | `conda install -c bioconda kma` | 一般建议用 Conda |
| `kmc` | 可选的 k-mer 计数加速 | 配置 `minimap2` k-mer 引擎时可用 | `conda install -c bioconda kmc` | 一般建议用 Conda |
| `samtools` | BAM 文件处理 | `minimap2` 定向验证流程 | `conda install -c bioconda samtools` | `brew install samtools` |
| `mmseqs` | Pixi 管理的项目依赖 | 内部流程和后续扩展 | `conda install -c bioconda mmseqs2` | `brew install mmseqs2` |
| `prodigal` | 基因预测 | 无方案分型和 CDS 相关流程 | `conda install -c bioconda prodigal` | `brew install prodigal` |

### 使用 Conda 一次性安装示例

```bash
conda install -c conda-forge -c bioconda \
  blast minimap2 mummer4 kma kmc samtools mmseqs2 prodigal
```

### 使用 Homebrew 安装示例

```bash
brew install blast minimap2 mummer samtools mmseqs2 prodigal
```

其中 `kma` 和 `kmc` 通常用 Conda 更方便。

## Python 依赖

项目使用的主要 Python 依赖包括：

- `click`
- `flask`
- `requests`
- `rich`
- `xxhash`
- `pyyaml`
- `pyrodigal`

这些依赖会由 Pixi、`pip install gmlst` 或 `pip install -e .` 自动安装。

## 常见问题排查

### `pixi: command not found`

可能原因：

- Pixi 还没有安装
- Pixi 安装目录没有加入 `PATH`

解决方法：

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

然后重新打开 shell，再确认：

```bash
pixi --version
```

如果仍然找不到，请把 Pixi 的 bin 目录加入 shell 配置文件。

### `blastn: command not found`

可能原因：

- BLAST+ 没有安装
- 你当前不在 Pixi 环境中
- 手动安装后的工具目录没有加入 `PATH`

排查方式：

```bash
gmlst utils check -b blastn
which blastn
```

如果你是用 Pixi 安装的，请先进入环境：

```bash
pixi shell
```

如果是手动安装，请使用 Conda 或 Homebrew 安装 BLAST+：

```bash
conda install -c bioconda blast
```

### 安装时出现权限错误

常见场景包括：

- 系统 Python 不允许写入包目录
- 全局执行 `pip install` 需要管理员权限
- 共享文件系统对缓存目录有限制

建议做法：

- 优先使用虚拟环境
- 不要使用 `sudo pip install`
- 如有需要，显式指定可写的缓存目录

示例：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install gmlst
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### Python 版本不符合要求

`gmlst` 需要 Python 3.12。

检查当前解释器版本：

```bash
python --version
```

如果输出不是 Python 3.12，请升级到 Python 3.12，或者直接使用 Pixi，让它自动管理解释器。

### 下载方案时遇到网络或代理问题

常见表现：

- `gmlst scheme download` 失败
- provider catalog 刷新失败
- 在代理网络下 HTTPS 请求超时

可以尝试：

```bash
gmlst scheme update
gmlst scheme download -s saureus_1 --download-tool curl
gmlst scheme download -s saureus_1 --download-tool requests
```

如果你处于公司或机构代理环境，可以先导出标准代理变量：

```bash
export HTTPS_PROXY=http://proxy.example.org:8080
export HTTP_PROXY=http://proxy.example.org:8080
```

如果某些数据源需要认证，可以根据命令帮助使用 `--token` 参数。

## 下一步

- 阅读[快速开始](quickstart.md)，完成第一次 MLST 分型
- 查看完整的[命令参考](../commands.md)
- 了解项目概览，请见 [../../README.md](../../README.md)
