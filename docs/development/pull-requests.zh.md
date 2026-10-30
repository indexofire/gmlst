# Pull Request

一份合格 PR 描述应包含什么、评审关注点，以及提交前要运行的检查。

## Pull Request 流程

分支准备好后，就可以在 GitHub 上发起 Pull Request。PR 描述最好完整到让 reviewer 不需要额外猜背景。

### PR 描述建议包含的内容

- 问题是什么
- 你的处理方式是什么
- 你跑了哪些验证命令
- CLI 输出、provider 行为、backend 选择是否有变化
- 如果改了 visual web UI，再附截图

### 评审通常会关注什么

- 是否符合现有架构，尤其是 protocol 和 registry 一致性
- CLI 行为和帮助文本是否稳定
- 改动是否有测试覆盖
- 用户可见变化是否补了文档
- 命令层和领域逻辑之间是否保持合理边界

### 提交 PR 前建议运行

```bash
pixi run check
pixi run test
pixi run internal-docs-check
```

如果 PR 涉及 `gmlst/web/frontend/`，还应运行：

```bash
pixi run visual-ui-build
```

## PR 描述模板

```markdown
## 问题
cgMLST FASTQ 使用 `-b minimap2` 时会静默使用仅支持 FASTA 的索引。

## 改动
在 `commands/typing.py` 中强制 KMA 优先策略，并在后端被改写时给出警告。

## 验证
- `pixi run test`
- `gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 reads_R{1,2}.fq.gz`

## 行为变化
TSV/JSON 输出不变；stderr 现在会提示后端切换。
```

保持 diff 聚焦：一个问题、一种方案，测试与文档放在同一个 PR。

## 常见评审意见

| 意见 | 含义 |
| --- | --- |
| “这段应该放在 `core/`” | 属于领域逻辑，而非 CLI 逻辑 |
| “复用现有协议” | 不要新增一次性的后端/provider 路径 |
| “补一个回归测试” | 测试应在修复前失败、修复后通过 |
| “中文页面也要更新” | 双语文档是硬性要求 |
