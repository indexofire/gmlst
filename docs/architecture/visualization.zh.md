# 可视化

Flask 后端、MST 计算与 Vue 前端，以及让可视化与分型流水线保持解耦的契约。

## 可视化架构

可视化栈主要分成两层。

### 后端层

- `gmlst/visual/cli.py` 暴露导出和服务命令
- `gmlst/visual/app.py` 创建 Flask 应用并校验 JSON payload
- `gmlst/visual/mst.py` 从 typing 输出表中计算 distance、mismatch loci、聚合节点和 MST edge

### 前端层

- `gmlst/web/frontend/` 存放 Vue 3 + Vite 前端源码
- `gmlst/web/templates/` 存放 Flask 使用的 HTML 模板
- `gmlst/web/static/` 存放构建后的静态资源

可视化模块与 typing pipeline 是解耦的。它消费导出的 TSV 或 JSON 风格 payload，而不是直接调用比对流程。

## 请求流程

```text
浏览器
  -> Vue 应用（dist 静态资源）
  -> POST /api/mst  {profiles, options}
  -> visual/app.py 校验载荷并应用安全钩子
  -> visual/mst.py 计算距离与图结构
  -> JSON 响应 {nodes, edges, meta}
  -> D3 渲染树形或放射状布局
```

## 不开浏览器时的批量用法

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --format tsv *.fna > profiles.tsv
gmlst visual mst --input profiles.tsv --format summary
gmlst visual matrix --input profiles.tsv --format tsv -o distances.tsv
gmlst visual locus-diff --input profiles.tsv
```

可视化层只消费 profile 表，从不导入分型流水线。新增命令时应保持这一边界。
