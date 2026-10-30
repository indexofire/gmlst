# 安装问题

Pixi 缺失、Python 版本不符、`pip install` 失败、找不到 `blastn` 以及权限问题的处理办法。

## 安装问题

### `pixi: command not found`

说明 Pixi 还没安装，或者当前 shell 还没有加载新的 PATH。

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

然后重新打开终端，再检查：

```bash
pixi --version
```

### `Python 3.12 is required`

说明当前 Python 版本太低。

先检查版本：

```bash
python --version
python3 --version
```

如果想少踩环境坑，建议直接改用 pixi：

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi run gmlst --version
```

### `pip install gmlst` 失败

常见原因包括：

- Python 版本不是 3.12
- 构建环境不一致
- 外部工具没有安装，后续命令因此失败

可以先试一个干净虚拟环境：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install gmlst
```

如果还是环境问题较多，建议直接用 pixi。

### `blastn` not found

`blastn` 属于 BLAST+。如果你用的是 pixi，请确保命令运行在 pixi 环境里。如果你用的是 pip，需要单独安装 BLAST+。

检查命令：

```bash
gmlst utils check -b blastn
```

或者：

```bash
pixi run gmlst utils check -b blastn
```

### 安装时遇到权限错误

本地开发环境下，不建议使用 `sudo pip` 或 `sudo pixi`。请改用用户自己的环境。

更合适的方式：

- pixi 环境
- Python 虚拟环境
- conda 或 mamba 环境

## 用自带 environment.yml 一次装齐

如果已经克隆仓库，`environment.yml` 会装好 Python 与全部后端：

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
conda env create -f environment.yml
conda activate gmlst
gmlst utils check -b blastn
```

## 逐个验证后端

```bash
for b in blastn minimap2 nucmer kma; do
  gmlst utils check -b "$b" || echo "missing: $b"
done
```

只有 `kma` 支持 FASTQ；`blastn` 与 `nucmer` 按设计会拒绝 reads 输入。

## `pip install gmlst` 成功但命令失败

Python 包本身不依赖外部工具，只有分型阶段需要。这是最常见的“安装损坏”报告：

```bash
gmlst --version          # 正常
gmlst typing mlst -s saureus_1 sample.fna
# 报错：blastn not found
```

安装你要用的后端（`conda install -c bioconda blast`），或改用已经安装的
`-b minimap2` / `-b kma`。
