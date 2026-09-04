---
type: log
status: archived
kind: bug
importance: high
updated: 2026-09-04
topic: mybutterfly-follow-path-z-retarget-no-crossing
source_logs:
  - "[[日志/2026-09-04-修正MyButterfly只复制翅膀Z曲线|修正 MyButterfly 只复制翅膀 Z 曲线]]"
supersedes: "[[日志/2026-09-04-修正MyButterfly只复制翅膀Z曲线|修正 MyButterfly 只复制翅膀 Z 曲线]]"
---

# 重定向 MyButterfly 翅膀 Z 曲线避免交叉

## 问题

上一版已经只复制 `rotation_euler[2]`，但仍直接保留来源 Z 曲线的完整相对幅度。来源左翼
Z 范围约为 `-21.62°～117.62°`，右翼约为 `-125.81°～13.42°`；在 MyButterfly Master
的局部坐标中，这些数值跨过身体中线，使左右翼进入错误的解剖侧并在极值帧交叉。

## 修复

- 两个输出继续只替换展示层左右翼的 `rotation_euler[2]`，不复制其他变换通道。
- 保留来源曲线的 91 个帧位、贝塞尔手柄时间、插值和缓动形状。
- 以 Master 第 1 帧 Z 为基线，将来源相对值和手柄值统一仿射缩放到正负 `32°` 的安全幅度。
- 修正后左翼 Z 范围为 `16.00°～80.00°`，右翼为 `-88.19°～-24.19°`，两翼始终保留在各自解剖侧。
- `location XYZ`、`rotation_euler X/Y`、`scale XYZ` 共 8 条非 Z 曲线继续逐点保持 Master 原值。
- Master 原版和两份 Follow Path 来源文件未覆盖、未改写。

## 验证

- Blender 5 重新打开两份输出，逐帧检查第 1～91 帧。
- 91 帧中左翼 Z 始终在 `0°～90°`，右翼始终在 `-90°～0°`。
- 翼面质心相对身体的最小解剖侧投影比例：左翼 `0.8414`、右翼 `0.8389`，均高于 `0.7` 安全阈值。
- 从 X、Y、Z 三个轴向渲染第 1、2、17、32、45、55、75、91 帧并人工复核；张开、闭合和过渡姿态未再出现换边或交叉。
- Master SHA-256 保持
  `71bf897e4ceb545c301cfb5b436f6b158eb63ce1889af5bbad4a6647c696a90a`。
- 修正后 SHA-256：版本 1 为
  `7444e7a1eced439e10b6313d2b49638436fb9ec97f2ca152d4ac754c37f6b0fd`，版本 2 为
  `b404873f57578fe1e0db6a2e986bac85a0b2ca2d308e93e415e8bb53fbbeff8e`。
