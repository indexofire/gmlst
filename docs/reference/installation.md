# Installation Troubleshooting

Fixes for missing Pixi, Python version errors, failing `pip install`, missing `blastn`, and permission problems.

## Installation Issues

### `pixi: command not found`

Pixi is not installed, or your shell has not picked up the new PATH yet.

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

Then open a new terminal and verify:

```bash
pixi --version
```

### `Python 3.12 is required`

Your Python is too old for the package.

Check:

```bash
python --version
python3 --version
```

If you want the easiest path, use pixi instead of a system Python install:

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi run gmlst --version
```

### `pip install gmlst` fails

Common reasons:

- Python is not 3.12
- build tools or environment are inconsistent
- external tools are missing and later commands fail

Try a clean virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install gmlst
```

If you still hit environment problems, use pixi.

### `blastn` not found

`blastn` is part of BLAST+. If you installed with pixi, run inside the pixi environment. If you used pip, install BLAST+ separately.

Check:

```bash
gmlst utils check -b blastn
```

Or:

```bash
pixi run gmlst utils check -b blastn
```

### I get permission errors during install

Do not use `sudo pip` or `sudo pixi` for normal local installs. Use a user-local environment.

Good options:

- pixi environment
- Python virtual environment
- conda or mamba environment

## One-shot install with the bundled environment file

If you have a checkout, `environment.yml` installs Python and every backend:

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
conda env create -f environment.yml
conda activate gmlst
gmlst utils check -b blastn
```

## Verify every backend

```bash
for b in blastn minimap2 nucmer kma; do
  gmlst utils check -b "$b" || echo "missing: $b"
done
```

`kma` is the only backend that accepts FASTQ; `blastn` and `nucmer` reject read
input by design.

## `pip install gmlst` succeeds but commands fail

The Python package installs fine without external tools; only typing needs
them. This is the most common "broken install" report:

```bash
gmlst --version          # works
gmlst typing mlst -s saureus_1 sample.fna
# error: blastn not found
```

Install the backend you intend to use (`conda install -c bioconda blast`) or
switch to `-b minimap2` / `-b kma` if those are already present.
