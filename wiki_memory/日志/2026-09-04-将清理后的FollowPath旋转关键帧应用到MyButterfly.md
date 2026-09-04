---
type: log
status: archived
kind: feature
importance: high
updated: 2026-09-04
topic: mybutterfly-follow-path-rotation-only-applied
source_logs:
  - "[[日志/2026-09-04-清除FollowPathMotionPath缓存|清除 Follow Path Motion Path 缓存]]"
  - "[[日志/2026-09-04-重定向MyButterfly翅膀Z曲线避免交叉|重定向 MyButterfly 翅膀 Z 曲线避免交叉]]"
---

# 将清理后的 Follow Path 旋转关键帧应用到 MyButterfly

## 输出

以 `models/Butterfly/scenes/MyWork/MyButterfly_Master.blend` 为基准，分别读取清理后的
Follow Path 版本左右翼旋转关键帧，生成：

- `models/Butterfly/scenes/MyWork/MyButterfly_Master_FollowPath1_RotationOnlyApplied.blend`
- `models/Butterfly/scenes/MyWork/MyButterfly_Master_FollowPath2_RotationOnlyApplied.blend`

原版 Master 未覆盖；Master 原有灯光、场景和非目标对象保持不变。

## 处理规则

- 目标为 `展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_` 和
  `展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_`。
- 应用来源左右翼的 `rotation_euler[0..2]` 三条曲线，各 91 个关键帧。
- 曲线帧位、插值、缓动和手柄时间/形状保留；X/Y 以 Master 第 1 帧姿态重基线。
- Z 以 Master 第 1 帧姿态重基线，并缩放到正负 `32°` 安全幅度，避免左右翼跨越身体中线。
- 目标展示翼的 Location、Scale 等非旋转 FCurve 删除；第 1 帧位置、父级和整体姿态保持。
- Master 的 `SOURCE_REFERENCE` 和其他显示对象不重新绑定来源路径动画。

## 验证

- Blender 5 重新打开两份输出，两个版本均通过专用验证器。
- 两翼各有 3 条 `rotation_euler` 曲线、每条 91 个关键帧，且与来源旋转曲线逐点映射一致。
- 91 帧全帧几何检查通过：左翼 Z 为 `16.00°～80.00°`，右翼为
  `-88.19°～-24.19°`；解剖侧投影最小比例分别为 `0.8414` 和 `0.8389`。
- 多视角渲染检查了第 1、2、17、32、45、55、75、91 帧，未见换边或交叉。
- Master SHA-256 保持
  `71bf897e4ceb545c301cfb5b436f6b158eb63ce1889af5bbad4a6647c696a90a`。
- 输出 SHA-256：版本 1 为
  `a0ba8a5cb8681931961a0237ed2ec9d0c0218238d82366d8357c7df9f2c28429`，版本 2 为
  `5c3de9ecb01af5397b8e1d2ae74020b4f485439dd0cf94bedc4271d6b5218096`。
