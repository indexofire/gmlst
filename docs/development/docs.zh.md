# 文档

各类文档应该放在哪里、双语文件约定，以及如何保持索引准确。

## 文档规则

不同类型的文档应该放在不同位置：

- 用户和开发者文档：`docs/`
- 内部活跃文档：`docs/internal/stable/`
- 内部归档文档：`docs/internal/archive/`
- 命令行为权威说明：`docs/usage/cli/index.md`

文档按主题组织，与 `gside` 的布局保持一致：

```text
docs/
  index.md              文档首页
  installation/         安装指南、快速开始、配置、流水线
  usage/                CLI 参考、后端、数据源与各类指南
  architecture/         系统设计
  reference/            FAQ
  development/          贡献指南
```

每个页面都有同名的中文版本，使用 `.zh.md` 后缀（`quick-start.md` →
`quick-start.zh.md`），i18n 插件据此构建 `/zh/`。章节入口页为 `index.md`，
使用 Material 的 grid cards 链接子页面。

如果你改了命令行为，就更新 `docs/usage/cli/index.md`。如果你新增或重组文档，也记得检查 `docs/index.md`，确保索引页仍然准确。

常用交叉引用文档：

- `docs/installation/guide.zh.md`
- `docs/installation/quick-start.zh.md`
- `docs/usage/cli/index.zh.md`
- `docs/architecture/index.zh.md`

## 新增页面

1. 创建 `docs/<section>/<page>.md` 与 `docs/<section>/<page>.zh.md`。
2. 在 `mkdocs.yml` 的 `nav` 中加入两页并设置标签。
3. 如果是新标签，在 `zh` 的 `nav_translations` 中补充翻译。
4. 从所在章节的 `index.md` / `index.zh.md` 卡片中链接到新页面。
5. 运行 `pixi run mkdocs build --strict` 与 `pixi run check`。

## 双语文件示例

```text
docs/usage/backends.md
docs/usage/backends.zh.md
```

中文页面链接到 `.zh.md` 兄弟文件；构建时 i18n 插件会自动处理语言切换。

## 章节划分

| 章节 | 内容 |
| --- | --- |
| `installation/` | 安装、快速开始、配置、流水线 |
| `usage/` | CLI 参考与任务指南 |
| `architecture/` | 内部设计 |
| `reference/` | 故障排查与错误参考 |
| `development/` | 贡献者工作流 |

## 文档 PR 检查清单

```text
[ ] 中英文页面都已更新
[ ] nav 与 nav_translations 已补充
[ ] 章节首页卡片链接到新页面
[ ] mkdocs build --strict 通过
[ ] 示例中的命令确实可运行
```
