# Installation

This guide covers the supported ways to install `gmlst` and verify that the CLI and backend tools are ready to use.

`gmlst` is a Python 3.12 command line tool for MLST, cgMLST, and wgMLST style bacterial genome typing. The recommended setup uses [Pixi](https://pixi.sh/), because Pixi installs both the Python package and the external bioinformatics tools needed by the alignment backends.

## System Requirements

| Requirement | Minimum | Recommended | Notes |
|---|---:|---:|---|
| Operating system | Linux, macOS | Linux, macOS | Supported Pixi platforms are `linux-64`, `osx-arm64`, and `osx-64` |
| Python | 3.12 | 3.12 | Required for pip or source installs |
| Memory | 2 GB RAM | 8 GB RAM or more | Larger cgMLST schemes benefit from more memory |
| Disk space | 1 GB free | 5 GB or more | Includes package, indexes, cached schemes, and temporary files |

## Installation Methods

### Method 1: Install with Pixi (recommended)

Use this method if you want the smoothest setup. Pixi manages:

- Python
- Python dependencies
- external tools such as `blastn`, `kma`, `minimap2`, `nucmer`, `samtools`, and `kmc`
- project tasks such as `pixi run start`, `pixi run test`, and `pixi run check`

### Step 1: Install Pixi

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

After installation, restart your shell if `pixi` is not immediately available.

### Step 2: Clone the repository

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
```

### Step 3: Install the project environment

```bash
pixi install
```

This reads `pixi.toml`, creates the environment, and installs both Python and external dependencies.

### Step 4: Enter the Pixi shell

```bash
pixi shell
```

Inside the shell, `gmlst` and all required tools should be on `PATH`.

### Step 5: Verify the CLI

```bash
gmlst --version
gmlst --help
gmlst utils check -b blastn
```

You can also run commands without entering a shell:

```bash
pixi run gmlst --help
pixi run gmlst utils check -b blastn
```

### Method 2: Install with pip

Use this method if you want a plain Python virtual environment and you are comfortable installing the backend tools yourself.

### Step 1: Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Step 2: Install `gmlst`

```bash
pip install gmlst
```

### Step 3: Install external bioinformatics tools separately

If you use pip, you must install the external backend tools yourself. Conda and Homebrew are the most practical choices.

See [External Dependencies](#external-dependencies) below for the full tool matrix and install commands.

### Step 4: Verify the install

```bash
gmlst --version
gmlst --help
gmlst utils check -b blastn
```

### Method 3: Install from source

Use this method if you want an editable checkout for local development or documentation work.

### Step 1: Clone the repository

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
```

### Step 2: Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Step 3: Install the package in editable mode

```bash
pip install -e .
```

This uses the project build configuration in `pyproject.toml` and installs the `gmlst` CLI entry point locally.

### Step 4: Install backend tools

Editable install only covers the Python package. You still need to install tools such as `blastn`, `kma`, `minimap2`, and `nucmer` separately unless you use Pixi.

### Step 5: Verify the install

```bash
gmlst --version
gmlst --help
gmlst utils check -b blastn
```

## Verify Installation

Use the checks below after any installation method.

### Check the version

```bash
gmlst --version
```

Example output:

```text
gmlst, version 0.1.0
```

### Check top level help

```bash
gmlst --help
```

You should see the main command groups:

```text
Commands:
  typing
  scheme
  utils
  visual
```

### Check backend availability

```bash
gmlst utils check -b blastn
gmlst utils check -b minimap2
gmlst utils check -b kma
gmlst utils check -b nucmer
```

Example output:

```text
[OK] backend=blastn is available
```

### Run a simple scheme query

```bash
gmlst scheme list -p pubmlst -t mlst
```

If your network access is working, you can also download a scheme and inspect it:

```bash
gmlst scheme download -s saureus_1
gmlst scheme show -s saureus_1
```

## Platform-Specific Notes

### Linux

- Linux is the simplest target for both Pixi and manual backend installation.
- `linux-64` is an official Pixi platform for this project.
- If you use clusters or shared servers, prefer Pixi or Conda to avoid tool version drift.

### macOS

### Apple Silicon (ARM64)

- `osx-arm64` is supported by the Pixi configuration.
- Pixi is the easiest choice on Apple Silicon because it resolves compatible binaries automatically.
- If you install tools manually with Homebrew, make sure your shell is using the ARM64 Homebrew prefix.

### Intel macOS

- `osx-64` is also supported by Pixi.
- Homebrew and Conda both work for manual installs.

### Rosetta 2

- Some third party bioinformatics tools may behave differently across ARM64 and x86_64 builds.
- If a tool is only available or more stable under x86_64, you may need to start a Rosetta shell and use an x86_64 toolchain.
- Try native ARM64 first. Only use Rosetta if a specific tool fails.

### Windows

- Native Windows is not the main target for this repository.
- The practical setup is **WSL2** with Ubuntu or another Linux distribution.
- Install Pixi, Python, and backend tools inside WSL2, not in PowerShell.

Example WSL2 workflow:

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

## External Dependencies

If you install with Pixi, these tools are handled for you. If you install with pip or from source, install the ones required by the backends you plan to use.

| Tool | Used for | Needed by backend or feature | Conda install | Homebrew install |
|---|---|---|---|---|
| `blastn`, `makeblastdb` | nucleotide alignment and index building | `blastn` backend | `conda install -c bioconda blast` | `brew install blast` |
| `minimap2` | assembly and read alignment | `minimap2` backend | `conda install -c bioconda minimap2` | `brew install minimap2` |
| `nucmer`, `show-coords` | whole genome alignment | `nucmer` backend via MUMmer4 | `conda install -c bioconda mummer4` | `brew install mummer` |
| `kma` | k-mer based mapping and typing | `kma` backend | `conda install -c bioconda kma` | not commonly packaged, use Conda |
| `kmc` | optional k-mer counting acceleration | `minimap2` k-mer engine when configured | `conda install -c bioconda kmc` | not commonly packaged, use Conda |
| `samtools` | BAM handling for targeted validation | `minimap2` targeted validation path | `conda install -c bioconda samtools` | `brew install samtools` |
| `mmseqs` | project dependency managed by Pixi | internal workflows and future extensions | `conda install -c bioconda mmseqs2` | `brew install mmseqs2` |
| `prodigal` | gene prediction support | scheme-free and CDS-related workflows | `conda install -c bioconda prodigal` | `brew install prodigal` |

### Manual install example with Conda

```bash
conda install -c conda-forge -c bioconda \
  blast minimap2 mummer4 kma kmc samtools mmseqs2 prodigal
```

### Manual install example with Homebrew

```bash
brew install blast minimap2 mummer samtools mmseqs2 prodigal
```

For `kma` and `kmc`, Conda is usually the simpler option.

## Python Dependencies

The project depends on these Python packages:

- `click`
- `flask`
- `requests`
- `rich`
- `xxhash`
- `pyyaml`
- `pyrodigal`

These are installed automatically by Pixi, `pip install gmlst`, or `pip install -e .`.

## Troubleshooting

### `pixi: command not found`

Cause:

- Pixi is not installed, or
- its install directory is not on `PATH`

Fix:

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

Then restart your shell and confirm:

```bash
pixi --version
```

If needed, add Pixi's bin directory to your shell profile.

### `blastn: command not found`

Cause:

- BLAST+ is not installed, or
- you are outside the Pixi environment, or
- your manual install is not on `PATH`

Fix:

```bash
gmlst utils check -b blastn
which blastn
```

If you installed with Pixi, enter the environment:

```bash
pixi shell
```

If you installed manually, install BLAST+ with Conda or Homebrew:

```bash
conda install -c bioconda blast
```

### Permission errors during install

Common cases:

- system Python blocks package writes
- global `pip install` needs elevated permissions
- shared filesystem has restricted cache directories

Fix:

- prefer a virtual environment
- avoid `sudo pip install`
- if needed, set a writable cache directory

Example:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install gmlst
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### Unsupported Python version

`gmlst` requires Python 3.12.

Check your interpreter:

```bash
python --version
```

If you do not see Python 3.12, install Python 3.12 or use Pixi, which manages the interpreter for you.

### Network or proxy issues when downloading schemes

Symptoms:

- `gmlst scheme download` fails
- provider catalogs do not refresh
- HTTPS requests time out behind a proxy

Things to try:

```bash
gmlst scheme update
gmlst scheme download -s saureus_1 --download-tool curl
gmlst scheme download -s saureus_1 --download-tool requests
```

If you are behind a corporate proxy, export standard proxy variables before running the command:

```bash
export HTTPS_PROXY=http://proxy.example.org:8080
export HTTP_PROXY=http://proxy.example.org:8080
```

If a provider requires authentication for a specific dataset, use the documented `--token` option where appropriate.

## Next Steps

- Follow the [Quick Start](quickstart.md) guide to run your first MLST call
- Browse the full [Command Reference](commands.md)
- See the repository overview in [../README.md](../README.md)
