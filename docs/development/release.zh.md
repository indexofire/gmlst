# 发布流程

版本号位置、发布清单、打标签与发布。

如果你在准备发布版本，需要保证版本号和发布说明同步。

### 版本相关位置

- `pixi.toml`，workspace 版本
- `pyproject.toml`，Python 包版本
- `gmlst/__init__.py`，运行时版本号，前提是当前发布流程使用这里
- `CHANGELOG.md`，发布说明

### 常见发布清单

1. 更新版本号
2. 更新 `CHANGELOG.md`
3. 运行检查和测试
4. 创建 release commit
5. 打 Git tag，例如 `v0.1.0`
6. 在 GitHub 上发布 release

示例命令：

```bash
pixi run check
pixi run test
git add pyproject.toml pixi.toml CHANGELOG.md gmlst/__init__.py
git commit -m "chore: prepare release v0.1.0"
git tag v0.1.0
```

如果当前发布流程并不需要修改其中某个文件，不要为了凑清单而强行改动。以仓库的真实状态为准。

## 发布命令序列

```bash
# 1. 在各处同步版本号
grep -n "version" pyproject.toml pixi.toml gmlst/__init__.py

# 2. 更新 CHANGELOG.md（[Unreleased] -> [x.y.z]）

# 3. 验证
pixi run check
pixi run test
pixi run mkdocs build --strict

# 4. 提交并打标签
git add pyproject.toml pixi.toml gmlst/__init__.py CHANGELOG.md pixi.lock
git commit -m "release: gmlst x.y.z"
git tag vx.y.z
git push origin main --tags
```

创建 GitHub Release 会触发 PyPI 与 Docker 工作流。如果标签只是 Zenodo 快照，
PyPI 仍停留在上一版本：对外宣布前先用 `pip index versions gmlst` 确认。

## 版本一致性检查

```bash
python - <<'PY'
import tomllib
from gmlst import __version__

py = tomllib.load(open("pyproject.toml", "rb"))["project"]["version"]
pixi = tomllib.load(open("pixi.toml", "rb"))["workspace"]["version"]
assert py == pixi == __version__, (py, pixi, __version__)
print("versions agree:", py)
PY
```
