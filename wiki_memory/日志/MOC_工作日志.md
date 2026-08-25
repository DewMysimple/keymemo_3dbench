---
type: moc
status: active
kind: process
importance: high
updated: 2026-08-25
topic: work-log-index
source_logs: []
supersedes: null
---

# 工作日志 MOC

> 单一工作日志索引，按更新时间倒序。任务类型通过 `kind` 元数据区分。

| 时间 | 类型 | 目标 | 状态 | 主题 | 日志 |
| --- | --- | --- | --- | --- | --- |
| 2026-08-25 | bug | - | archived | blender-asset-portability | [[日志/2026-08-25-Blender文件资源可移植性修复.md|Blender 文件资源可移植性修复]] |
| 2026-08-25 | maintenance | - | archived | blender-workbench-rename-memory-migration | [[日志/2026-08-25-Blender工作台重命名与记忆迁移.md|Blender 工作台重命名与记忆迁移]] |
| 2026-08-25 | maintenance | - | archived | blender-workbench-file-naming | [[日志/2026-08-25-Blender工作区文件命名统一.md|Blender 工作区文件命名统一]] |
| 2026-08-25 | maintenance | - | archived | blender-version-preparation | [[日志/2026-08-25-Blender多版本制作预留.md|Blender 多版本制作预留]] |
| 2026-08-25 | feature | - | archived | blender-no-animation-version | [[日志/2026-08-25-Blender去除非相机动画版本.md|Blender 去除非相机动画版本]] |
| 2026-08-23 | feature | - | archived | blender-chinese-workspaces | [[日志/2026-08-23-生成Blender项目中文工作区.md|2026-08-23｜生成 Blender 项目中文工作区]] |
| 2026-08-23 | bug | - | archived | blender-watercolor-alpha-depth-and-topology | [[日志/2026-08-23-Blender透明穿透与水彩卡拓扑整改.md|2026-08-23｜Blender 透明穿透与水彩卡拓扑整改]] |
| 2026-08-23 | bug | 撤回 Blender 中不符合源网站结构的竖直阴影卡片，恢复只包含源内容的可编辑场景。 | archived | blender-shadow-approximation-removal | [[日志/2026-08-23-Blender误加阴影近似撤回与源阴影边界确认.md|2026-08-23｜Blender 误加阴影近似撤回与源阴影边界确认]] |
| 2026-08-23 | bug | - | archived | blender-interface-language | [[日志/2026-08-23-Blender界面语言诊断.md|2026-08-23｜Blender 界面语言诊断]] |
| 2026-08-23 | bug | 修复 Blender 水彩材质黑屏、补齐网页程序化草，并明确禁止构建脚本修改 Blender 用户偏好。 | archived | blender-material-remap-procedural-grass-fix | [[日志/2026-08-23-Blender材质映射与程序化草修复.md|2026-08-23｜Blender 材质映射与程序化草修复]] |
| 2026-08-23 | bug | - | archived | blender-workspace-names | [[日志/2026-08-23-Blender工作区名称未翻译诊断.md|2026-08-23｜Blender 工作区名称未翻译诊断]] |
| 2026-08-23 | bug | - | archived | blender-scene-visual-restoration | [[日志/2026-08-23-Blender场景视觉恢复闭环.md|2026-08-23｜Blender 场景视觉恢复闭环]] |
| 2026-08-23 | bug | - | archived | blender-atlas-material-black-preview-diagnosis | [[日志/2026-08-23-Blender图集材质黑屏诊断.md|2026-08-23｜Blender 图集材质黑屏诊断]] |
| 2026-08-23 | bug | - | archived | blender-atlas-material-principled-fix | [[日志/2026-08-23-Blender图集材质节点整改.md|2026-08-23｜Blender 图集材质节点整改]] |
| 2026-08-23 | bug | - | archived | blender-launcher-vs-project-workspace | [[日志/2026-08-23-Blender启动器与项目工作区差异.md|2026-08-23｜Blender 启动器与项目工作区差异]] |
| 2026-08-23 | bug | - | archived | blender-watercolor-card-side-back-transparency | [[日志/2026-08-23-Blender主素材侧面背面透明排序整改.md|2026-08-23｜Blender 主素材侧面与背面透明排序整改]] |
| 2026-08-23 | bug | - | archived | blender-watercolor-card-view-angle-material-fix | [[日志/2026-08-23-Blender主素材2D图层视角材质稳定整改.md|2026-08-23｜Blender 主素材 2D 图层视角材质稳定整改]] |
| 2026-08-22 | feature | - | archived | scene-workbench-blender-mirror | [[日志/2026-08-22-三维场景工作区与Blender镜像.md|2026-08-22｜三维场景工作区与 Blender 镜像]] |
| 2026-08-22 | bug | 修复 Blender 主文件中摄像机/图层空间错位以及只有摄像机运动、图层动画缺失的问题。 | archived | blender-camera-layer-animation-fix | [[日志/2026-08-22-Blender摄像机与图层动画修复.md|2026-08-22｜Blender 摄像机与图层动画修复]] |
| 2026-08-22 | bug | 修复 Blender 主文件中可编辑对象被锁定、源镜像与动画层重叠以及材质预览透明空白的问题。 | archived | blender-editability-material-preview-fix | [[日志/2026-08-22-Blender可编辑性与材质预览修复.md|2026-08-22｜Blender 可编辑性与材质预览修复]] |

## 使用方式

- 由 `python 工具/memory_lint.py index` 生成或刷新。
- 查询时先阅读当前状态，再按关键词定位日志。
- 历史日志是审计记录，不应直接覆盖当前状态。

## 入口

- [[工程记忆README|工程 Agent 记忆系统]]
- [[README|项目 README]]
- [[AGENTS|记忆维护协议]]
- [[当前状态/项目概览|当前项目概览]]
- [[当前状态/系统架构|当前系统架构]]
