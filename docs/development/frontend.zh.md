# 前端

Flask 与 Vue 的分工、涉及的文件，以及修改可视化时需要运行的构建命令。

## Visual Web Frontend

可视化功能由 Flask 和 Vue 共同组成：

- 命令入口：`gmlst/visual/cli.py`
- Flask app：`gmlst/visual/app.py`（工厂 + 安全钩子）
- JSON API：`gmlst/visual/api_routes.py`（Blueprint），辅助函数在 `gmlst/visual/_api_helpers.py`
- MST 逻辑：`gmlst/visual/mst.py`
- 前端源码：`gmlst/web/frontend/`
- 构建产物：`gmlst/web/static/visual/dist/`

### 前端相关工作流

```bash
pixi run visual-ui-build
pixi run gmlst visual web --help
pixi run gmlst visual web --open-browser
```

如果你修改了前端，提交 PR 前请先重新构建静态资源。

## 本地开发循环

```bash
# 重新构建 Flask 提供的打包产物
pixi run visual-ui-build

# 启动 Flask 应用并打开浏览器
pixi run gmlst visual web --open-browser
```

需要热更新时可用 `npm --prefix gmlst/web/frontend run dev` 启动 Vite 开发服务器，
并在开发期间指向 Flask API。

## 需要保持的契约

- 前端不 import Python 代码，只消费 `/api/mst` 的 JSON
- MST 与距离逻辑留在 `gmlst/visual/mst.py`
- 新增载荷字段必须是增量式的，并写入 `docs/usage/visualization.md`

## 改动位置对照

| 改动 | 文件 |
| --- | --- |
| 节点颜色、标签、布局控件 | `gmlst/web/frontend/src/App.vue` |
| 全局样式 | `gmlst/web/frontend/src/style.css` |
| API 载荷或校验 | `gmlst/visual/api_routes.py` |
| 距离或 MST 算法 | `gmlst/visual/mst.py` |
| CLI 导出格式 | `gmlst/visual/_cli_export.py` |

未经批准不要新增 npm 依赖；保持 `App.vue` 的 `<style>` 为空，样式统一放在
`style.css`。
