---
type: log
status: archived
kind: feature
importance: high
updated: 2026-09-04
topic: butterfly-follow-path-rotation-only-no-light-no-path
source_logs:
  - "[[日志/2026-09-04-重定向MyButterfly翅膀Z曲线避免交叉|重定向 MyButterfly 翅膀 Z 曲线避免交叉]]"
---

# 生成 Follow Path 去灯光、去路径、仅旋转关键帧版本

## 目标与输出

以两份 Follow Path 源文件为只读输入，新增独立派生文件：

- `models/Butterfly/scenes/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_NO_LIGHT_NO_PATH_ROTATION_ONLY.blend`
- `models/Butterfly/scenes/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_NO_LIGHT_NO_PATH_ROTATION_ONLY.blend`

原始 `BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend` 与 `_2.blend` 未覆盖。

## 处理规则

- 删除 4 个灯光对象及其无引用灯光数据。
- 清除路径控制层级空物体的 Action；同时清除所有非翅膀对象的动画，避免路径位移或转向残留。
- 两翼 Action 仅保留 `rotation_euler` 旋转 FCurve，删除 Location、Scale 等非旋转关键帧。
- 翅膀旋转关键帧的帧号、数值、贝塞尔手柄、插值和缓动逐点保持来源值。
- 清除无对象引用的路径 Action 数据块，避免文件内部残留其他动画关键帧。

## 验证

- Blender 5 重新打开两个输出文件并通过 `tools/validate_butterfly_follow_path_rotation_only.py`。
- 两个输出均无 LIGHT 对象、无 Follow Path 约束、无非翅膀对象 Action。
- 两个输出的全部 Action 仅含旋转 FCurve；每个左右翼 Action 保留 3 条 `rotation_euler` 曲线、每条 91 个关键帧。
- 左右翼旋转关键帧与对应源文件逐点一致；第 1、46、91 帧抽样确认 Z 旋转仍在变化。
- 输入源 SHA-256 保持：版本 1 为
  `3a17b9ac29d09acf147b3ee3b7a9fd9282c94c59db75286da53b7b7a611f9876`，版本 2 为
  `01c87a17b7311d12778f7625dd13c5f1166530234e702c4d7c74bdf2149853e7`。
- 输出 SHA-256：版本 1 为
  `58bd5101d6d8e7553a8d81748a9ed0660370017001f126ee5fb717ba0728914d`，版本 2 为
  `e2ccc6c6a5bd0ecf44ce45d2ce6fb203def3077debbe5ecc8cf1024e0959ec5f`。
