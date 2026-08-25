# Blender 工程记忆

Blender 工作台的工程记忆位于本目录，与网页主线 `wiki_memory/` 分开维护任务范围，但代码和资产仍属于同一个 `main` 工程。

## 目录

- `当前状态/`：工作台当前事实
- `决策/`：Blender 工作台决策
- `知识/`：场景结构、资源和验证流程
- `日志/`：Blender 历史日志与唯一 MOC
- `工具/memory_lint.py`：体检和日志索引工具

## 命令

```text
python 工具/memory_lint.py check
python 工具/memory_lint.py index
```

入口规则见 [`AGENTS.md`](./AGENTS.md)。
