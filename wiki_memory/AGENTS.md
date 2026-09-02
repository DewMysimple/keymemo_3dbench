# Blender 工程记忆维护协议

本目录是 `keymemo_3dbench` 独立 Blender 工作台的任务记忆，使用统一的 Markdown Schema，只记录 Blender 范围的事实。本仓库与 Verminoble 网页工程分离，不建立运行时依赖。

## 读取顺序

1. 读取本文件。
2. 读取 `当前状态/项目概览.md`、`当前状态/系统架构.md`、`当前状态/当前约束.md`、`当前状态/当前待办.md`。
3. 读取相关 active 决策。
4. 读取相关知识页。
5. 只有需要追溯时才读取最近 1–3 篇日志或更早历史。

## 写入范围

- Blender 场景、材质、对象、动画、资源路径、构建、验证、渲染和创作过程写入本目录。
- Verminoble 网页实现和网页资源事实不属于本仓库；需要对照时只引用公开的历史背景。
- 不把本仓库的 Blender 细节复制回其他工程的运行时记忆。
- `日志/` 是不可改写的追加式历史；需要修正时新增日志，不改历史正文。
- 长期页面使用 YAML frontmatter；`日志/MOC_工作日志.md` 是本地日志唯一索引。

## 检查

```text
python wiki_memory/工具/memory_lint.py check
python wiki_memory/工具/memory_lint.py index
```

记忆路径使用 `/`，不写机器特定的绝对路径。源代码、`.blend` 和报告仍是事实来源，记忆只保存结论、关系和相对路径。
