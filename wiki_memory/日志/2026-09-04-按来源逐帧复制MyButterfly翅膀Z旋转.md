---
type: log
status: archived
kind: bug
importance: high
updated: 2026-09-04
topic: mybutterfly-follow-path-exact-source-z-values
source_logs:
  - "[[日志/2026-09-04-将清理后的FollowPath旋转关键帧应用到MyButterfly|将清理后的 Follow Path 旋转关键帧应用到 MyButterfly]]"
supersedes: "[[日志/2026-09-04-将清理后的FollowPath旋转关键帧应用到MyButterfly|将清理后的 Follow Path 旋转关键帧应用到 MyButterfly]]"
---

# 按来源逐帧复制 MyButterfly 翅膀 Z 旋转

## 用户修正

用户明确要求目标展示左右翼的 Z 旋转关键帧逐帧完全等于来源文件，不再使用先前为避免交叉而设置的 Z 安全幅度缩放。因此撤销 Z 仿射缩放：来源每个 Z 曲线关键点的帧位、数值、左右手柄时间和值均原样写入目标 Action。

## 输出

仍以 `models/Butterfly/scenes/MyWork/MyButterfly_Master.blend` 为基准，原版不覆盖，生成两份独立文件：

- `models/Butterfly/scenes/MyWork/MyButterfly_Master_FollowPath1_RotationOnlyApplied.blend`
- `models/Butterfly/scenes/MyWork/MyButterfly_Master_FollowPath2_RotationOnlyApplied.blend`

两份输出均只替换指定展示左右翼的 `rotation_euler[0..2]` 曲线；每轴 91 个关键帧，目标翼 Location、Scale 等非旋转曲线删除。X/Y 仍以 Master 第 1 帧为基线重定向，Z 不重定向、不缩放，逐帧使用来源值。

## 验证与取舍

- Blender 5 专用验证器通过两个版本：左右翼各 3 条旋转曲线、每条 91 个关键帧，Z 的 `value_scales` 均为 `1.0`，并通过来源/目标曲线逐点（含手柄）比较。
- 来源 Z 范围为左翼约 `-48.77°～90.47°`、右翼约 `-90.44°～48.79°`；这是来源的原始完整幅度。
- 由于用户要求保留上述原始 Z 数值，部分帧会出现跨身体中线或左右解剖侧的现象；验证报告将其记录为 `anatomical_side_crossing_observed`，不再以安全侧约束拒绝输出。这是“数值完全相等”和“绝不交叉”之间的明确取舍。
- Master SHA-256 保持 `71bf897e4ceb545c301cfb5b436f6b158eb63ce1889af5bbad4a6647c696a90a`。
- 输出 SHA-256：版本 1 为 `8226b24655bcd64af2de6b7fac70d50393a2a634ffa5af01d732a9f1b7c40fad`；版本 2 为 `1767810a105b6e546aea624d44ed782bf884605227c9dea64cffe3d028ac82a1`。
