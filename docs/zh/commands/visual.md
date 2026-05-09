[← 命令参考](../../commands.md)

# gmlst visual

用于启动本地 Web 可视化界面，查看基于 profile 距离构建的 MST。

## web

启动本地 Flask + Vue 可视化应用，用于上传 profile、构建 MST 并交互式查看结果。

### 用法
```bash
gmlst visual web [OPTIONS]
```

### 选项

| 选项 | 说明 | 默认值 |
| --- | --- | --- |
| `--host TEXT` | 指定监听地址。 | `127.0.0.1` |
| `--port INTEGER` | 指定监听端口。 | `8787` |
| `--open-browser` | 启动后自动打开浏览器。 | 关闭 |

### 示例
```bash
gmlst visual web --open-browser
gmlst visual web --host 0.0.0.0 --port 8787
```

### 注意事项
- 后端使用 Flask 路由提供本地 API，前端使用 Vue 3 + Vite 构建并作为静态资源提供服务。
- Web UI 可以接收 `gmlst` 生成的 TSV，也可以接收 GrapeTree 风格的 profile 表，要求第一列为 `#Strain`。
- 应用会基于每个位点的 allele 差异构建 MST。
- 界面支持 `tree` 和 `radial` 两种布局。
- 支持按元数据列给节点着色。
- 支持在界面中导出 SVG。
