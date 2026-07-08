# gmlst 开发计划

基于 `gpt5.5-issus.md` 审核报告整理，共 5 个阶段、19 个任务项。

---

## 阶段一：紧急缺陷修复（预计 1 天）

当前存在可触发的运行时 bug 和发布流程缺陷，优先修复。

### 1.1 修复热图导出运行时 bug (I1)

**问题**：`filteredHeatmapLociView` 只返回 `{loci, cells}`，但 `exportHeatmapTsv()` / `exportHeatmapJson()` 读取 `view.labels`，导致 `undefined` 运行时错误。

**修改范围**：
- `gmlst/web/frontend/src/App.vue:275-280` — `filteredHeatmapLociView` computed
- `gmlst/web/frontend/src/App.vue:3188-3207` — `exportHeatmapTsv()` / `exportHeatmapJson()`

**修复方案**：
- 在 `filteredHeatmapLociView()` 中补充返回 `labels: this.filteredHeatmapView.labels`
- 或者让导出函数分别从两个 view 取数据

**验证**：
- 前端 build 通过
- 手动或自动化测试：热图页面点击 Export TSV / JSON 不报错，导出内容完整

**工作量**：S（单文件，~5 行改动）

---

### 1.2 修复 PyPI 发布流程缺少前端构建 (I2)

**问题**：`publish-pypi.yml` 直接执行 `python -m build`，未先构建前端。`test.yml` 的 `build` job 同样是新 checkout 未构建前端。`.gitignore` 的 `dist/` 规则会匹配 `gmlst/web/static/visual/dist/`，导致 CI fresh checkout 默认无前端产物。

**修改范围**：
- `.github/workflows/publish-pypi.yml` — 在 `python -m build` 前加 Node + npm build 步骤
- `.github/workflows/test.yml:65-86` — `build` job 在 `python -m build` 前加前端构建
- `.gitignore:34` — `dist/` 改为更精确的 `/dist/`（只忽略项目根目录 dist）

**修复方案**：
```yaml
# publish-pypi.yml 和 test.yml build job 中 python -m build 之前加入：
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
    cache-dependency-path: gmlst/web/frontend/package-lock.json
- run: npm ci
  working-directory: gmlst/web/frontend
- run: npm run build
  working-directory: gmlst/web/frontend
```
并在 build 后验证 wheel 中包含 `app.js` / `app.css`：
```yaml
- run: python -m build && python -c "
    import zipfile, glob
    whl = glob.glob('dist/*.whl')[0]
    with zipfile.ZipFile(whl) as z:
    names = z.namelist()
    assert any('app.js' in n for n in names), 'app.js missing from wheel'
    assert any('app.css' in n for n in names), 'app.css missing from wheel'
    "
```

**验证**：
- `python -m build` 后 wheel 包含前端静态资源
- `twine check dist/*` 通过

**工作量**：M（2 个 workflow 文件 + .gitignore）

---

### 1.3 修复前端 npm test 脚本 (I3)

**问题**：`package.json` 中 `"test": "vitest run"`，但 vitest 未在 devDependencies 中。实际测试文件用的是 Node 原生 test runner（`node:test`）。

**修改范围**：
- `gmlst/web/frontend/package.json:9` — test 脚本

**修复方案**：
将 `"test": "vitest run"` 改为 `"test": "node --test src/visualSelection.test.js"`

**验证**：
- `npm test` 在 `gmlst/web/frontend/` 下执行成功
- CI frontend job 加入 `npm test` 步骤
- `.github/workflows/test.yml` frontend job 末尾追加：
  ```yaml
  - name: Run frontend tests
    run: npm test
    working-directory: gmlst/web/frontend
  ```

**工作量**：S（2 个文件，各 1-2 行改动）

---

## 阶段二：安全加固（预计 1-2 天）

### 2.1 替换 pickle 缓存为安全格式 (I4)

**问题**：`core/exact_hash.py` 使用 `pickle.loads()` 反序列化缓存文件，且用 `suppress(Exception)` 静默吞掉错误。若缓存目录可被攻击者写入，可实现 RCE。

**修改范围**：
- `gmlst/core/exact_hash.py:37-66` — 缓存读写逻辑

**修复方案**：
- 将 `pickle.dumps/loads` 替换为 `json.dumps/loads` 或 `msgpack`（如 index 结构支持）
- 若 index 结构复杂（包含 set/dict 嵌套），优先 JSON + 自定义 encoder/decoder
- 移除 `suppress(Exception)`，改为显式捕获 `(OSError, json.JSONDecodeError, KeyError)` 并 `logger.warning` + 重建缓存
- 旧 pickle 缓存自动作废（fingerprint 机制已覆盖），无需迁移

**验证**：
- `pixi run pytest` 全部通过
- exact hash 缓存读写回归测试通过
- 新增测试：corrupt cache file → 重建而非崩溃

**工作量**：M（需要理解 index 数据结构，选择合适的序列化格式）

---

### 2.2 CLI 可视化路径添加规模限制 (I5)

**问题**：Web API 已有 `_validate_tsv_scale()` 限制样本/loci 数量，但 CLI 的 `visual mst`、`visual export` 等命令直接读取文件无限制。Edmonds O(n³) 和 GrapeTree O(n²·L) 算法在大输入下会导致长时间阻塞。

**修改范围**：
- `gmlst/visual/cli.py:402-416` — `cmd_visual_mst`
- `gmlst/visual/cli.py:855-889` — `cmd_visual_export`（及相关子命令）
- `gmlst/visual/app.py:85-96` — `_validate_tsv_scale()` 提取为公共函数

**修复方案**：
1. 将 `_validate_tsv_scale()` 从 `app.py` 提取到 `gmlst/visual/validation.py`（或直接在 `cli.py` 中 import）
2. CLI `visual mst/export` 在调用 `build_mst_from_tsv()` 之前调用 `validate_tsv_scale()`
3. 新增 `--force-large` flag，跳过规模限制但打印 warning
4. Edmonds/GrapeTree 对超大输入（>2000 样本）打印进度提示

**验证**：
- CLI 大输入（>5000 样本）触发拒绝或 warning
- `--force-large` 可绕过限制
- 现有测试不破坏
- 新增 CLI scale limit 测试

**工作量**：M（跨文件重构 + 新 flag + 测试）

---

## 阶段三：工程环境对齐（预计 1 天）

### 3.1 统一 Python 版本约束 (I6)

**问题**：`pixi.toml` 限制 `<3.13`，`pyproject.toml` 允许 `>=3.11`，CI 测试 3.13。

**修改范围**：
- `pixi.toml:22` — `python = ">=3.11,<3.13"`
- `pyproject.toml:34` — classifier `Programming Language :: Python :: 3.13`

**修复方案**：
二选一：
- **A**：若 3.13 已验证通过 → `pixi.toml` 改为 `python = ">=3.11,<3.14"`
- **B**：若 3.13 未验证 → 移除 `pyproject.toml` 中 3.13 classifier + CI matrix 中 3.13

建议方案 A（CI 已在测 3.13）。

**工作量**：XS（1 行改动）

---

### 3.2 CI 增加 pixi smoke job (I7)

**问题**：CI 只用 `pip install -e ".[dev]"`，不验证 pixi 环境。项目以 pixi 为主开发工具，环境 drift 不会被捕获。

**修改范围**：
- `.github/workflows/test.yml` — 新增 pixi job

**修复方案**：
```yaml
pixi:
  runs-on: ubuntu-latest
  steps:
  - uses: actions/checkout@v5
  - uses: prefix-dev/setup-pixi@v0.8
  - run: pixi install
  - run: pixi run check
  - run: pixi run test
```

**工作量**：S（新增 ~10 行 YAML）

---

### 3.3 删除冗余 MANIFEST.in (I10)

**问题**：项目使用 hatchling 构建，`pyproject.toml` 已配置 wheel/sdist include 规则。`MANIFEST.in` 对 hatchling 无效，且内容有重复条目（第 1-4 行与第 6-9 行完全重复）。

**修改范围**：
- 删除 `MANIFEST.in`

**验证**：
- `python -m build` 后 wheel 内容不变（hatchling 已在 pyproject.toml 中配置）

**工作量**：XS（删除文件）

---

### 3.4 修复 pixi run check 语义 (I11)

**问题**：`pixi run check` 实际执行 `ruff check --fix . && ruff format .`（会修改文件），但名称暗示 dry-run 检查。CI 使用的是不带 `--fix` 的版本。

**修改范围**：
- `pixi.toml:14` — `check` 任务
- `AGENTS.md` — Key Rules 第 1 条

**修复方案**：
```toml
check = "ruff check . && ruff format --check ."
fix = "ruff check --fix . && ruff format ."
```

**验证**：
- `pixi run check` 不修改文件，仅报告问题
- `pixi run fix` 执行自动修复

**工作量**：XS（2 个文件，各 1-2 行）

---

## 阶段四：质量门禁增强（预计 2-3 天）

### 4.1 引入类型检查报告 (I8)

**问题**：Pyright 报告 133 个 source 诊断 + 24 个 test 诊断，但未纳入任何质量门禁。核心路径（pipeline、aligner、typing_runner）存在类型不一致。

**修改范围**：
- `pixi.toml` — 新增 `typecheck` 任务
- `gmlst/core/types.py:26-31` — `TypingContext` 类型标注
- 各处类型标注修复（分批进行）

**修复方案**：
1. **第一步**：新增非阻塞 typecheck 任务
   ```toml
   typecheck = "pyright gmlst/ test/ || true"
   ```
2. **第二步**：修复 `TypingContext` 类型 — 给 `core/scheme/aligner/cache` 定义 Protocol 或具体类型
3. **第三步**：逐步修复最关键的类型错误（pipeline、ranking、typing_runner）
4. **第四步**：达到 0 errors 后改为阻塞门禁

**工作量**：L（分多轮，核心类型修复可能涉及多文件）

---

### 4.2 修复假测试和 pytest warnings (I9)

**问题**：`test_gmlst_comprehensive.py` 中函数返回 `list[TestResult]` 而非 assert，触发 `PytestReturnNotNoneWarning`。`TestResult` 类名触发 `PytestCollectionWarning`。

**修改范围**：
- `test/test_gmlst_comprehensive.py` — 全文件 420 行

**修复方案**：
二选一：
- **A**：将 `test_*` 函数改为真实 assert（推荐，保留测试价值）
- **B**：重命名为 `diagnostic_*.py` 或移到 `scripts/`，排除出 pytest 收集

建议方案 A — 将 `run_command()` + `TestResult` 模式改为标准 assert：
```python
def test_basic_commands():
    success, stdout, stderr = run_command("gmlst --help")
    assert success, f"Help failed: {stderr}"
    assert "gmlst" in stdout
```

**验证**：
- `pixi run pytest` 0 warnings
- 所有测试仍然通过

**工作量**：M（420 行重构，但模式统一）

---

### 4.3 新增关键回归测试

基于审核发现的安全和质量缺口，补充以下测试：

| 测试 | 覆盖问题 | 优先级 |
|---|---|---|
| Pickle 缓存 tamper/corrupt 回归 | I4 验证 | 高 |
| CLI 大输入 scale-limit 拒绝 | I5 验证 | 高 |
| 热图 TSV/JSON 导出 roundtrip | I1 验证 | 高 |
| 热图导出 labels 存在性 | I1 回归 | 高 |
| `pixi run check` 不修改文件 | I11 验证 | 中 |
| `npm test` 可执行 | I3 验证 | 中 |

**工作量**：M（~6 个新测试用例）

---

## 阶段五：前端优化与代码清理（预计 1-2 天）

### 5.1 前端快捷键和可访问性改进 (I12)

**问题**：
1. 全局快捷键拦截 Ctrl/Cmd+F/S/E，未判断焦点是否在 `input/textarea` 中
2. 矩阵 cell 和热图 row header 无键盘等价操作
3. Node hover 每次 mousemove 都更新，大图下可能造成 jank

**修改范围**：
- `gmlst/web/frontend/src/App.vue:432-457` — 快捷键 handler
- `gmlst/web/frontend/src/App.vue:894-918` — hover handler

**修复方案**：
1. 快捷键 handler 开头加入：
   ```js
   const tag = document.activeElement?.tagName;
   if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
       || document.activeElement?.isContentEditable) return;
   ```
2. tooltip/table sync 仅在 `hoveredNodeId` 变化时执行（加 throttle 或 prev id 判断）

**工作量**：S（~10 行改动）

---

### 5.2 热图列方向限制 (I13)

**问题**：R2 修复只限制了行数（200 行），但保留所有 loci 列。cgMLST/wgMLST 可能有数千 loci，200×3000 的 DOM 仍有性能问题。

**修改范围**：
- `gmlst/web/frontend/src/App.vue:239-249` — `filteredHeatmapLociView`
- `gmlst/web/frontend/src/App.vue:4051-4086` — 热图渲染

**修复方案**：
- 增加 loci 方向 render limit（如 300 列）
- 超出时显示 truncation warning + 建议 filter
- 或者对超宽热图切换为 Canvas 渲染（长期方案）

**工作量**：S-M（取决于方案复杂度）

---

### 5.3 删除 Newick 导出空 if block (L1)

**问题**：`App.vue:3072-3077` 有一个空的 `if (parentId === targetId) {}` 块，是 R3 重构残留。

**修改范围**：
- `gmlst/web/frontend/src/App.vue:3074-3075`

**修复方案**：删除空 block。

**工作量**：XS（删除 2 行）

---

### 5.4 .gitignore 规则修正 (L4)

**问题**：
- `tests/` 与实际测试目录 `test/` 不一致
- `*.sh` 过宽，会阻止提交有用的 shell 脚本

**修改范围**：
- `.gitignore:30,45-46`

**修复方案**：
- 删除 `tests/`（或改为 `# tests/ — legacy, now test/`）
- 将 `*.sh` 改为更具体的路径（如 `tmp/*.sh`）或删除

**工作量**：XS

---

### 5.5 自定义 scheme ID 并发竞态 (L2)

**问题**：`_get_next_custom_id()` 读取 catalog 后返回 `max_id + 1`，无文件锁，两个进程可能拿到同一 ID。

**修改范围**：
- `gmlst/commands/scheme.py:835-858`

**修复方案**：
- 使用 `filelock` 或 `fcntl.flock()` 在 catalog 更新期间加锁
- 或使用 atomic write（write to tmp + rename）

**工作量**：S

---

### 5.6 异常静默吞掉改为日志记录 (L3)

**问题**：多处 `with suppress(Exception)` 或 bare `except: pass`，用户无法定位缓存损坏、权限错误等问题。

**修改范围**：
- `gmlst/database/providers/bigsdb.py:169-176`
- `gmlst/database/cache.py:228-231`
- `gmlst/commands/scheme.py:856-877`
- `gmlst/metadata_io.py:11-13`

**修复方案**：
- 将 `suppress(Exception)` 改为显式捕获预期异常 + `logger.warning()`
- 保留容错语义（不抛出），但提供可追溯性

**工作量**：S（4 处，每处 ~3 行改动）

---

## 总结：优先级与工作量矩阵

| 阶段 | 任务 | 编号 | 优先级 | 工作量 | 前置依赖 |
|---|---|---|---|---|---|
| 一 | 热图导出 bug | I1 | 🔴 紧急 | S | 无 |
| 一 | PyPI 发布流程 | I2 | 🔴 紧急 | M | 无 |
| 一 | npm test 修复 | I3 | 🔴 紧急 | S | 无 |
| 二 | Pickle 缓存安全 | I4 | 🟠 高 | M | 无 |
| 二 | CLI 规模限制 | I5 | 🟠 高 | M | 无 |
| 三 | Python 版本对齐 | I6 | 🟡 中 | XS | 确认 3.13 兼容性 |
| 三 | pixi CI job | I7 | 🟡 中 | S | 无 |
| 三 | 删除 MANIFEST.in | I10 | 🟡 中 | XS | 无 |
| 三 | check 语义修复 | I11 | 🟡 中 | XS | 无 |
| 四 | 类型检查门禁 | I8 | 🟡 中 | L | 无（可分批） |
| 四 | 假测试修复 | I9 | 🟡 中 | M | 无 |
| 四 | 回归测试补充 | — | 🟡 中 | M | I1, I4, I5 完成后 |
| 五 | 快捷键/可访问性 | I12 | 🟢 低 | S | 无 |
| 五 | 热图列限制 | I13 | 🟢 低 | S-M | 无 |
| 五 | Newick 空块清理 | L1 | 🟢 低 | XS | 无 |
| 五 | .gitignore 修正 | L4 | 🟢 低 | XS | 无 |
| 五 | scheme ID 竞态 | L2 | 🟢 低 | S | 无 |
| 五 | 异常日志记录 | L3 | 🟢 低 | S | 无 |

**预计总工作量**：6-8 个工作日

**推荐执行顺序**：阶段一 → 阶段二 → 阶段三 → 阶段四 → 阶段五

**并行机会**：
- 阶段一的 I1/I2/I3 可并行
- 阶段三的 I6/I7/I10/I11 可并行
- 阶段五的所有任务可并行
- 回归测试（4.3）可在 I1/I4/I5 完成后立即开始
