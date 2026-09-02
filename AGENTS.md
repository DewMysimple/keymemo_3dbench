# keymemo_3dbench Agent 入口

这是独立的 Blender 工作台仓库 `keymemo_3dbench`，由 `Verminoble` 的
`blender_scenebench` 历史提取而来。它不属于 Verminoble 的网页运行时，不是
子模块、软链接或 `module-replication/` 项目；维护时不得建立对 Verminoble
目录的运行时依赖。

开始任务前：

1. 读取本文件。
2. 读取 `wiki_memory/AGENTS.md`。
3. 按本地协议读取 `wiki_memory/当前状态/项目概览.md`、`系统架构.md`、
   `当前约束.md`、`当前待办.md`。
4. 按任务读取 active 决策、知识页和必要的最近日志。

## 工作台边界

- 仓库根目录就是工作台根目录；脚本从根目录运行，不使用
  `Verminoble` 或 `blender_scenebench` 前缀。
- `blender/` 保存主 `.blend`；`blender_modelbench/` 保存模型基准与源素材；
  `source_snapshot/` 是可复现的运行资源快照。
- `generated/`、渲染输出和 `.blend1/.blend2` 自动备份保持本地忽略。
- 三个超过 GitHub 100 MB 限制的原始文件只保留在本机，路径、大小和 SHA-256
  记录在 `manifests/local_assets_manifest.json`，不得加入 Git。
- 主 `.blend` 和派生 `.blend` 的外部资源必须使用仓库内
  `source_snapshot/` 的相对路径，或明确嵌入文件。
- `.blend` 文件名、Blender 数据块、对象、材质、动画、父子关系和模型资产
  路径属于稳定契约；未获明确授权不得重命名或简化。

## 记忆与验证

- Blender 场景、资源、构建、验证和创作事实写入本仓库的 `wiki_memory/`。
- 运行 `python wiki_memory/工具/memory_lint.py index` 更新日志 MOC，运行
  `python wiki_memory/工具/memory_lint.py check` 体检记忆。
- 构建、修复和验证脚本位于 `tools/`，报告位于 `reports/`；从仓库根目录
  使用它们。
- 版本准备默认只预演；只有显式 `--create` 才生成派生文件，且不得覆盖
  `full` 主文件。

## Git

- 默认使用 `main`，每个完成的任务先创建本地 commit。
- 本仓库远程为
  `https://github.com/DewMysimple/keymemo_3dbench.git`；只有用户明确要求
  时才推送。
