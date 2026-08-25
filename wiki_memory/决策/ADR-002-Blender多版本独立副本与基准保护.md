---
type: decision
status: active
kind: architecture
importance: high
updated: 2026-08-25
topic: blender-version-isolation
source_logs:
  - "[[日志/2026-08-25-Blender多版本制作预留|Blender 多版本制作预留]]"
  - "[[日志/2026-08-25-Blender去除非相机动画版本|Blender 去除非相机动画版本]]"
supersedes: null
---

# ADR-002 Blender 多版本独立副本与基准保护

## 决策

full 是当前唯一完整 Blender 基准文件。no-animation 等版本使用 versions/<version-id>/ 独立目录和独立 .blend，不得通过 Blender 链接库共享可变数据，也不得直接修改或覆盖 full。当前 no-animation 已在第 3586 帧固化所有非相机对象和形态键，并保留相机动画。

版本准备工具默认只预演，只有显式 --create 才生成目标文件。生成时从来源文件重新保存，并以目标文件位置计算外部资源相对路径；资源或独立性检查失败时版本保持不可用状态。

当前工作台仍位于 blender_scenebench/。blender/_scenebench/ 只是未来正式迁移时的目标结构，本次不创建。

## 结果

版本清单、来源关系、变更集合和验证状态集中登记在 manifests/version_registry.json；版本制作细节和历史日志继续写入本地 Blender wiki_memory/。
