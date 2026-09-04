---
type: log
status: archived
kind: feature
importance: high
updated: 2026-09-04
topic: mybutterfly-dynamic-wing-keyframes
source_logs:
  - "[[日志/2026-09-01-创建蝴蝶Blender完整文件|创建蝴蝶 Blender 完整文件]]"
supersedes: null
---

# 重制 MyButterfly 翅膀动态关键帧

## 目标

调整 `models/Butterfly/scenes/MyWork/MyButterfly_Master.blend` 中指定左右展示翼的
局部 Euler Z 轴动画，解决原动作幅度小、频率平均、逐帧线性插值导致运动感不足的问题。

## 结果

- 保持左右翼对象名、父级、网格、材质以及非 Z 轴动画不变。
- 原左右翼 Z 曲线分别为 85 和 91 个逐帧 `LINEAR` 关键帧，单侧总幅度约 `21.48°`。
- 新动作在 1–91 帧内使用 17 个 `BEZIER`、`AUTO_CLAMPED` 关键帧形成 8 次拍翅；
  各循环时长和极值均有变化，下压闭合更快、展开回程稍慢。
- 左翼范围改为 `21°～90°`，右翼按原 FBX 的 `2.19029°` 镜像校准偏差映射为
  `-92.19029°～-23.19029°`；第 1 帧与第 91 帧一致，可无缝循环。
- 展示翼分别绑定独立的 `MyButterfly_WingMotion_DYNAMIC_LEFT` 与
  `MyButterfly_WingMotion_DYNAMIC_RIGHT` Action；原 FBX Action 保留且未改写。

## 验证

- Blender 5.0 后台保存后重新打开成功。
- 专用验证器逐帧检查 1–91 帧，左右翼镜像偏差、循环接缝、关键帧数量、插值与手柄均通过。
- 新 Action 的所有非 Z FCurve 与各自源 Action 的 SHA-256 曲线签名一致。
- 第 1、6、15、31、37、48、54、91 帧完成 Eevee 预览；展开帧显示完整翼面，闭合峰值接近
  侧视薄翼，未发生超过目标角度的曲线过冲。
- 原文件备份保存在
  `generated/backups/MyButterfly_Master_before_dynamic_wings_20260904_2315.blend`；正式验证报告为
  `reports/mybutterfly-wing-animation-validation.json`。

## 工具

- `tools/adjust_mybutterfly_wing_animation.py`
- `tools/validate_mybutterfly_wing_animation.py`
- `tools/inspect_mybutterfly_wing_animation.py`
- `tools/render_mybutterfly_wing_preview.py`
