# Blender SceneBench Agent 入口

这是 `Verminoble` 主线中的 Blender 工作台，不是独立 Git 分支、仓库、子模块或 `module-replication/` 项目。网页和 Blender 继续在同一个 `main` 工程中同步开发。

开始 Blender 任务前：

1. 读取主线根目录 `AGENTS.md`，确认网页与工作台边界。
2. 读取本目录的 `wiki_memory/AGENTS.md`。
3. 按本地协议读取 `wiki_memory/当前状态/项目概览.md`、`系统架构.md`、`当前约束.md`、`当前待办.md`。
4. 按任务读取本地 active 决策、知识页和必要的最近日志。

## 任务路由

- Blender-only 任务的当前状态、决策、知识和工作日志写入本目录的 `wiki_memory/`。
- 网页-only 任务写入主线 `wiki_memory/`，不要把网页事实复制到这里。
- 混合任务分别写入两套记忆；只在主线记录网页侧边界，只在本地记录 Blender 侧实现细节。

## 工作台边界

- `blender/` 保存跟踪的 `.blend` 主文件；`source_snapshot/`、`generated/` 和自动备份按 `.gitignore` 保持本地忽略。
- `manifests/version_registry.json` 登记完整版本与派生版本；`versions/<version-id>/` 只在显式创建派生版本后出现。
- Blender 构建、验证、修复和渲染脚本都位于 `tools/`，报告位于 `reports/`。
- `.blend` 文件名、Blender 数据块、对象名、材质名和动画名属于稳定契约；变更前必须有明确任务授权。
- 主文件的外部资源应指向仓库跟踪的 `public/.../xp` 资源，或明确嵌入文件；不要恢复对被忽略快照的依赖。

## 版本制作边界

- `full` 是唯一完整基准文件；派生版本必须从它生成独立 `.blend`，不得使用 Blender 链接库共享可变数据。
- 使用 `python blender_scenebench/tools/prepare_blend_version.py --version-id <id> --dry-run` 预演；只有显式 `--create` 才能写入派生文件。
- 版本准备会重算目标文件的相对资源路径，并在资源或独立性检查失败时标记失败，不得标记为可用。
- “去除动画”等具体场景变更不属于版本复制动作，必须作为单独授权任务执行；完整版本不能被覆盖。

记忆体检和日志索引：

```text
python blender_scenebench/wiki_memory/工具/memory_lint.py check
python blender_scenebench/wiki_memory/工具/memory_lint.py index
```
