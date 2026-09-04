---
type: log
status: archived
kind: bug
importance: high
updated: 2026-09-04
topic: butterfly-follow-path-motion-path-cache-removal
source_logs:
  - "[[日志/2026-09-04-生成FollowPath去灯光去路径旋转关键帧版本|生成 Follow Path 去灯光去路径旋转关键帧版本]]"
supersedes: "[[日志/2026-09-04-生成FollowPath去灯光去路径旋转关键帧版本|生成 Follow Path 去灯光去路径旋转关键帧版本]]"
---

# 清除 Follow Path Motion Path 缓存

## 问题

用户截图中的橙色曲线和帧号不是几何路径，而是 Blender 对路径控制空物体保存的
Motion Path 可视化缓存。即使已经清除路径 Action，缓存仍会在视图中显示。

## 修复

- 在两个 `NO_LIGHT_NO_PATH_ROTATION_ONLY` 派生文件中，按 `ARTIST_EDIT` 和
  `SOURCE_REFERENCE` 两个 View Layer 清除全部 Motion Path 缓存。
- 继续保持：4 个灯光对象已删除；非翅膀对象无 Action；两翼只保留
  `rotation_euler` 旋转 FCurve。
- 原始两个 Follow Path 文件不覆盖。

## 验证

- Blender 5 重新打开两个输出，Motion Path 对象数均为 0。
- 两个输出无 LIGHT 对象、无 Follow Path 约束、无非旋转关键帧；左右翼各保留 3 条
  `rotation_euler` 曲线，每条 91 个关键帧，且与对应源文件逐点一致。
- 输出 SHA-256：版本 1 为
  `129083fa9b7bfc95257ea6e22b3056ced1a8047bbd707edbc15e3226bc2f96ab`，版本 2 为
  `80a7340282ff6680de1b0aaa248d29abf13dd5d1cf4504d2b1e19432443090d2`。
