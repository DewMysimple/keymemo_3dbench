---
type: log
status: archived
kind: maintenance
importance: medium
updated: 2026-09-04
topic: remove-butterfly-wing-flap-only-variants
source_logs:
  - "[[日志/2026-09-04-重建竖框蝴蝶轴向与干净层级|重建竖框蝴蝶轴向与干净层级]]"
supersedes: null
---

# 删除蝴蝶 wing_flap_only 派生目录

## 原因

用户确认不再保留 `models/Butterfly/scenes/wing_flap_only/` 这一派生版本分类，后续不继续维护该目录下的框面附着扇翅文件。

## 处理

- 删除该目录及其中两个 `BUTTERFLY_FLAP_FAST_FOLLOW_PATH_*_WING_FLAP_ONLY.blend` 文件。
- 删除只用于生成或验证该派生分类的构建脚本、验证脚本与当前报告。
- 保留 `scenes/master/`、`scenes/follow_path/`、`scenes/idle/`、`scenes/slow_flap/`、源 FBX、OBJ、贴图和历史归档。
- 刷新全仓 `.blend` 资源报告；删除后共扫描 21 个 Blender 文件，资源检查通过。
- 历史日志和迁移历史报告保留为不可改写记录，不作为当前可用入口。

