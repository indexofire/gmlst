# cgMLST/wgMLST 与 MST Web 审查报告

- 日期：2026-10-27
- 范围：`gmlst/core`、`gmlst/calling`、`gmlst/visual`、`gmlst/web/frontend`
- 基线：gmlst 0.6.0，1080 backend tests / 77 frontend tests
- 方法：100 轮审查 probe（属性测试、边界用例、静态数据流检查、前后端契约检查、性能复杂度审查）；最后连续 3 轮无新增问题后停止。

## 结论

共确认 **16 个问题**：**13 个已按 TDD 修复**，**3 个保留为后续改进/风险**。

没有发现需要立即推翻 cgMLST calling 算法的错误；高风险主要集中在 **MST Web 导出/状态持久化** 和 **大样本 MST 性能上限**。

## 已修复（TDD）

| ID | 严重度 | 模块 | 问题 | 修复 |
| --- | --- | --- | --- | --- |
| F01 | P1 | Web file input | 代码限制 32 MiB，但注释/测试/文档承诺 64 MiB；大文件被静默拒绝 | `MAX_FILE_SIZE` 恢复 64 MiB；启用已有测试 |
| F02 | P1 | Web test infra | `npm test` 只跑 `visualSelection.test.js`，其余 4 个测试文件（含已失败的 fileInput）从未执行 | 改为 `node --test src/*.test.js`；77 tests 全跑 |
| F03 | P1 | Newick export | 多根森林只在整个输出末尾加一个 `;`，生成非法 Newick | 每个 root 单独终止；新增 forest 测试 |
| F04 | P1 | Newick export | 过滤/聚类后的 rendered graph 仍导出 parentMap 中的隐藏节点 | 只遍历 rendered nodes/edges；新增 hidden-node 测试 |
| F05 | P2 | MST frontend | 单节点 MST 没有边，Stats/Summary 直接返回 null，页面空白 | 抽出 `buildGraphStats`；空图返回 null，单节点返回 0 权重统计 |
| F06 | P2 | MST frontend | Stats/Summary 读取 `lastData`，不随当前过滤/edge threshold 更新 | Stats 改用 `currentRenderedGraph` |
| F07 | P2 | Session | 导出/恢复丢失 color scheme、theme、表格查询/排序、timeline 状态 | 增加 options 字段并 round-trip 测试 |
| F08 | P3 | Session/App | App 复制了一份 session payload 构建逻辑，helper 未使用，已开始漂移 | App 改用 `buildSessionJsonPayload`；同时复用 graph export helper |
| F09 | P1 | Web upload | 客户端允许 64 MiB，但 Flask 默认上限仍是 32 MiB，客户端放行后服务端 413 | 服务端默认上限统一为 64 MiB；新增契约测试 |
| F10 | P2 | cgMLST chew | 每个样本重复读取 allele length/hash/sequence，wgMLST 下 I/O 放大 | 单次加载 + content-stat cache；新增缓存复用/失效测试 |
| F11 | P2 | cgMLST chew tests | 边界规则仅覆盖 plus-strand PLOT3，缺 PLOT5/minus/LOTSC/ASM/ALM | 增加表驱动测试，10 个 chew tests 全通过 |
| F12 | P1 | MST backend | `_MAX_SAMPLE_COUNT=5000` 未区分方法，Edmonds/grapetree_v2 可能 OOM/超时 | 方法级上限：edmonds 1000、grapetree_v2 2000、classic 5000；新增超限测试 |
| F13 | P1 | Matrix/Heatmap API | 后端仍生成完整 n×n 矩阵，大样本 JSON/内存风险 | 1000 节点上限，超限返回 400；新增 matrix/heatmap 测试 |

## 保留问题（按优先级）

### P1/P2

1. **自动列识别对非数字 allele ID 不安全**
   - `_detect_non_allele_columns` 主要按“全数字/逗号数字”判断 allele-like；自定义 scheme 使用 `abc_1` 等 ID 时，locus 列可能被误判为 metadata。
   - 建议：显式 `--metadata-columns` / schema hint，保留启发式为 fallback。

2. **sample 列回退规则可能把 locus 当样本**
   - `_sample_key_for` 在缺少 FILE/sample_id 时取第一列；对非 gmlst 格式的 profile TSV 可能把 locus 当 sample。
   - 建议：要求显式 sample 列或校验重复样本 ID。

### P2/P3

3. **MST 统计阈值硬编码**
   - outlier 阈值固定 `weight > 50`；不同 scheme/loci 规模下不合适。
   - 建议：阈值可配置或按分位数显示。

## 性能改进建议

### cgMLST/wgMLST

- 将 allele length/hash/sequence 预加载到 scheme cache，按 sample 复用。
- 对 `ultrafast`/`fast` 的二次确认预算建立基准，避免大 scheme 上的无界重对齐。
- 对 KMA FASTQ / minimap2 的候选生成阶段记录 candidate count，防止 prefilter 退化为全量比对时无提示。

### MST

- Edmonds/grapetree_v2 加硬性 n 上限；大样本推荐 classic Kruskal/Prim。
- `grapetree_v2` 避免构造完整 `edge_lookup`；按需从矩阵生成边。
- 距离矩阵 API 支持 `limit` 或 cluster-scoped matrix。
- 前端已限制 200 行/300 loci；后端应使用相同上限，避免“前端截断但后端已耗尽内存”。

## TDD 验证

修复前新增/启用失败测试：

```text
src/fileInput.test.js            MAX_FILE_SIZE 64 MiB
src/tableExport.test.js          forest semicolons / hidden nodes
src/mstStats.test.js             empty + single-node + two-node stats
src/sessionPersistence.test.js   color/theme/table/timeline round-trip
test/test_chew_policy.py         metadata cache reuse + invalidation
test/test_visual_command.py      default upload cap matches client
```

修复后：

```text
backend:  1090 passed
frontend: 77 passed (all test files)
vite build: success
lint / pyright: success
```
