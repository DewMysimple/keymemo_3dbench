---
type: log
status: archived
kind: feature
importance: high
updated: 2026-09-04
topic: mybutterfly-follow-path-wing-key-variants
source_logs:
  - "[[日志/2026-09-02-用Master替换蝴蝶扇翅动画|用 Master 替换蝴蝶扇翅动画]]"
  - "[[日志/2026-09-04-重制MyButterfly翅膀动态关键帧|重制 MyButterfly 翅膀动态关键帧]]"
supersedes: null
---

# 为 MyButterfly 生成两份 Follow Path 翅膀关键帧版本

## 目标

以 `models/Butterfly/scenes/MyWork/MyButterfly_Master.blend` 为不变原版，分别使用两份
Follow Path Blender 文件的左右翼 Action 替换 `ARTIST_EDIT` 展示翼关键帧，生成两个独立版本。

## 结果

- `models/Butterfly/scenes/MyWork/MyButterfly_Master_FollowPath1_WingKeys.blend`
  使用 `BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend` 的左右翼 Action。
- `models/Butterfly/scenes/MyWork/MyButterfly_Master_FollowPath2_WingKeys.blend`
  使用 `BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend` 的左右翼 Action。
- 两个输出均以 Master 第 1 帧局部位置、旋转和缩放作为新 Action 基线，完整保留来源 Action 的
  相对关键帧变化、帧号、手柄时间、插值和缓动；未绑定 Follow Path 路径控制器，因此没有带入
  沿路径位移或路径转向。
- Master 的身体、非翅膀展示对象、父子关系、材质、场景和 `SOURCE_REFERENCE` 保持不变。
- 原版 SHA-256 保持
  `71bf897e4ceb545c301cfb5b436f6b158eb63ce1889af5bbad4a6647c696a90a`；两份 Follow Path
  来源文件的 SHA-256 也与构建前一致。

## 来源动作差异

两份 Follow Path 文件的路径运动不同，但它们左右翼的 9 条 FCurve 关键帧数据彼此相同；因此
两个新版本的翅膀视觉动作一致。仍分别生成两份文件，并使用独立 Action 名称与来源元数据，确保
版本来源可追溯。

## 验证

- 两个输出均由 Blender 5.0 保存后重新打开。
- 每只翼验证 9 条 FCurve、819 个关键帧点；所有来源关键帧相对变化、手柄时间和插值信息一致。
- 第 1、10、20、30、45、60、75、91 帧完成 Eevee 预览复核。
- 构建报告：`reports/mybutterfly-follow-path-wing-variants.json`。
- 验证报告：`reports/mybutterfly-follow-path-wing-validation.json`。

## 工具

- `tools/build_mybutterfly_follow_path_wing_variants.py`
- `tools/validate_mybutterfly_follow_path_wing_variants.py`
