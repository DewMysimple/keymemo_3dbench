---
type: log
status: archived
kind: bug
importance: high
updated: 2026-09-04
topic: mybutterfly-follow-path-z-only-wing-fix
source_logs:
  - "[[日志/2026-09-04-为MyButterfly生成两份FollowPath翅膀关键帧版本|为 MyButterfly 生成两份 Follow Path 翅膀关键帧版本]]"
supersedes: "[[日志/2026-09-04-为MyButterfly生成两份FollowPath翅膀关键帧版本|为 MyButterfly 生成两份 Follow Path 翅膀关键帧版本]]"
---

# 修正 MyButterfly 只复制翅膀 Z 曲线

## 问题

初版 `MyButterfly_Master_FollowPath1_WingKeys.blend` 与
`MyButterfly_Master_FollowPath2_WingKeys.blend` 错误复制了来源翅膀 Action 的全部 9 条
FCurve，而不是只复制局部 Euler Z。虽然每条曲线都按第 1 帧进行了数值平移，但 Follow Path
来源翼与 Master 翼位于不同父级空间，来源 `location` 曲线在 Master 层级重放后仍会造成翅膀错位。

## 修复

- 两个输出均从 Master 原左右翼 Action 创建独立副本。
- 只将来源 `rotation_euler[2]` 的 91 个关键帧、手柄、插值与缓动复制到新 Action，并以
  Master 第 1 帧局部 Z 旋转为基线。
- `location XYZ`、`rotation_euler X/Y`、`scale XYZ` 共 8 条非 Z FCurve 全部保持 Master 原值。
- 不绑定 Follow Path 路径控制器，不复制来源位置、缩放或路径转向。
- Master 原版与两份 Follow Path 来源文件保持原 SHA-256，不被覆盖。

## 验证

- 两个修正版由 Blender 5.0 保存后重新打开并通过专用验证。
- 左翼 8 条 Master 非 Z 曲线共 680 个关键帧点、右翼共 728 个关键帧点，逐点与 Master 相同。
- 两翼 Z 曲线各 91 个关键帧点，来源相对值、手柄时间、插值和缓动保持一致。
- 第 1、10、20、30、45、60、75、91 帧重新渲染，翅根保持连接且没有来源位置曲线造成的漂移。
- 修正后 SHA-256：版本 1 为
  `3d949a91163d5236a4a4e7b86b2c4d95b7a162b8d7e5238accffb966a8dba1ba`，版本 2 为
  `e36f538a3bf2970c871cc441bd1db4119938e8a8b19e4160fe3c89406e8a1954`。
