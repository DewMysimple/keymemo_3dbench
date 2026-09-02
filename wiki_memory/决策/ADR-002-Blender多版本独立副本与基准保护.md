---
type: decision
status: active
kind: architecture
importance: high
updated: 2026-09-02
topic: blender-version-isolation
source_logs:
  - "[[日志/2026-08-25-Blender多版本制作预留|Blender 多版本制作预留]]"
  - "[[日志/2026-08-25-Blender去除非相机动画版本|Blender 去除非相机动画版本]]"
supersedes: null
---

# ADR-002 Blender 多版本独立副本与基准保护

`full` 是唯一完整 Blender 基准文件：`blender/GwayLoo_Scene_5_0.blend`。
`no-animation` 等版本使用 `versions/<version-id>/` 的独立 `.blend`，不得使用
Blender 链接库共享可变数据，也不得覆盖 `full`。

版本准备工具默认只预演；只有显式 `--create` 才生成目标文件。生成时按目标
`.blend` 位置重算 `source_snapshot/` 的相对资源路径，并在资源或独立性检查失败
时保持失败状态。
