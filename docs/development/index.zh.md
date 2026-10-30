# 开发

搭建工具链、遵循开发流程，并在不破坏现有架构的前提下扩展 gmlst。

<div class="grid cards" markdown>

-   **开发环境**

    ---

    Pixi 环境、验证命令与项目地图。

    [开发环境](setup.zh.md)

-   **开发工作流**

    ---

    分支、编辑循环、lint、测试与提交约定。

    [工作流](workflow.zh.md)

-   **代码风格**

    ---

    格式、import、命名、类型标注、错误处理与 Click 模式。

    [代码风格](code-style.zh.md)

-   **扩展 gmlst**

    ---

    新增比对后端、数据提供方或 CLI 命令。

    [扩展](extending.zh.md)

-   **测试**

    ---

    运行测试套件、编写聚焦测试与回归测试。

    [测试](testing.zh.md)

-   **文档**

    ---

    文档位置、双语约定与索引规则。

    [文档](docs.zh.md)

-   **前端**

    ---

    Flask/Vue 分工与可视化构建命令。

    [前端](frontend.zh.md)

-   **Pull Request**

    ---

    评审关注点与提交前检查。

    [Pull Request](pull-requests.zh.md)

-   **发布流程**

    ---

    版本号位置、打标签与发布。

    [发布](release.zh.md)

</div>

## 获取帮助

如果不确定改动应该放在哪里，先查看最近的同类模块并沿用其模式。对于面向用户的行为，请在同一個 PR 中同时更新文档与测试，保持仓库一致。

常用入口：

| 问题 | 从这里开始 |
| --- | --- |
| 代码应该放在哪里？ | [开发环境](setup.zh.md)、[代码风格](code-style.zh.md) |
| 如何新增后端/provider/命令？ | [扩展](extending.zh.md) |
| 应该测试什么？ | [测试](testing.zh.md) |
| 文档怎么写？ | [文档](docs.zh.md) |
| 评审期待什么？ | [Pull Request](pull-requests.zh.md) |
