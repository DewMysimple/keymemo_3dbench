---
type: decision
status: active
kind: architecture
importance: high
updated: 2026-09-02
topic: standalone-blender-workbench
source_logs:
  - "[[日志/2026-09-02-Blender工作台独立迁移至keymemo_3dbench|Blender 工作台独立迁移至 keymemo_3dbench]]"
supersedes: "[[决策/ADR-001-工作台与网页记忆路由|ADR-001 工作台与网页记忆路由]]"
---

# ADR-003 keymemo_3dbench 独立仓库与资源边界

## 决策

将 Blender 工作台从 Verminoble 提取为独立的 `keymemo_3dbench` 仓库，仓库根目录
直接承载 `blender/`、`blender_modelbench/`、`tools/`、`reports/`、`manifests/`、
`versions/` 和 `wiki_memory/`。原 `Verminoble/blender_scenebench` 保留为本地备份，
不建立子模块、软链接或运行时引用。

`source_snapshot/` 纳入仓库并作为主 `.blend` 的可复现资源根；生成缓存不纳入 Git。
三个超过 GitHub 100 MB 限制的原始文件只保留在本机，并由本地清单核验。提取历史
中的同名大 Blob 已从新仓库历史清除，不使用 Git LFS。

## 结果

脚本从新仓库根目录运行，`.blend` 的外部资源不再解析到 Verminoble。Git 远程为
`https://github.com/DewMysimple/keymemo_3dbench.git`，默认分支为 `main`。
