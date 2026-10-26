# cgMLST/wgMLST 与 MST Web 审查报告

- 日期：2026-10-27
- 范围：`gmlst/core`、`gmlst/calling`、`gmlst/visual`、`gmlst/web/frontend`
- 基线：gmlst 0.6.0，1080 backend tests / 77 frontend tests
- 方法：100 轮审查 probe（属性测试、边界用例、静态数据流检查、前后端契约检查、性能复杂度审查）；最后连续 3 轮无新增问题后停止。

## 结论

共确认 **16 个问题**：**8 个已按 TDD 修复**，**8 个保留为后续改进/风险**。

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

## 保留问题（按优先级）

### P1/P2

1. **MST 算法复杂度与输入上限不匹配**
   - `_MAX_SAMPLE_COUNT = 5000`，但 Edmonds 路径是 O(n³) 根枚举，grapetree_v2 需要 O(n²) 距离矩阵与 O(n²) `DirectedEdge` 查找表。
   - 5000×10 的输入能通过 `validate_tsv_scale`，但可能耗尽内存/CPU。
   - 建议：按 method 设置 n 上限；大样本只允许经典 Kruskal/Prim；或在 API 层拒绝不可执行组合。

2. **cgMLST chew 分类每个样本重复加载 allele 数据**
   - `classify_chew_style_calls` 每样本重新读取 locus length、allele hashes、allele sequences。
   - wgMLST 数千 loci 时这是明显 I/O/解析放大。
   - 建议：在 `TypingContext`/scheme cache 上缓存 allele metadata，按数据库版本失效。

3. **自动列识别对非数字 allele ID 不安全**
   - `_detect_non_allele_columns` 主要按“全数字/逗号数字”判断 allele-like；自定义 scheme 使用 `abc_1` 等 ID 时，locus 列可能被误判为 metadata。
   - 建议：显式 `--metadata-columns` / schema hint，保留启发式为 fallback。

4. **sample 列回退规则可能把 locus 当样本**
   - `_sample_key_for` 在缺少 FILE/sample_id 时取第一列；对非 gmlst 格式的 profile TSV 可能把 locus 当 sample。
   - 建议：要求显式 sample 列或校验重复样本 ID。

### P2/P3

5. **MST matrix API 仍计算完整 n×n**
   - frontend 仅渲染 200 行，但 backend 先生成完整矩阵/JSON；大样本 JSON 和内存成本高。
   - 建议：API 增加 limit/cluster filter 下的 lazy matrix，或提前拒绝超限。

6. **Web API 没有服务端 payload 大小限制**
   - 客户端 64 MiB 限制可绕过；直接 POST 超大 TSV 仍会进入解析/MST。
   - 建议：Flask `MAX_CONTENT_LENGTH` 与 API scale check 双保险。

7. **chew 边界规则测试覆盖不足**
   - 仅有 plus-strand PLOT3 用例；缺 `PLOT5`、minus strand、`LOTSC`、`ASM`、`ALM`、`NIPHEM`。
   - 建议：按 chewBBACA 语义补齐表驱动测试，再谈算法改动。

8. **MST 统计阈值硬编码**
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
```

修复后：

```text
backend:  1080 passed
frontend: 77 passed (all test files)
vite build: success
lint / pyright: success
```
