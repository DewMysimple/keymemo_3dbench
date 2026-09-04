---
type: log
status: archived
kind: feature
importance: high
updated: 2026-09-04
topic: no-animation-self-contained-assets
source_logs:
  - "[[日志/2026-08-25-Blender去除非相机动画版本|Blender 去除非相机动画版本]]"
  - "[[日志/2026-09-03-Blender工作台目录结构统一迁移|Blender 工作台目录结构统一迁移]]"
supersedes: null
---

# no-animation 版本资源内嵌化

## 目标

将 `scenes/GwayLoo/versions/no-animation/GwayLoo_Scene_5_0_no_animation.blend`
制作成不依赖外部资产的派生文件。按用户要求，不保留被引用的 MP4 视频文件和外部字体，
并将其余资产全部打包进 `.blend`。

## 修改

- 新增 `tools/make_blend_self_contained.py`，统一盘点图片、Movie Clip、声音、字体、
  Volume、Cache File 和 Blender Library，并在仍有外部依赖时失败。
- 从目标文件移除 24 个 `MOVIE` 图像数据块；保留 12 个景观场景、对象和材质入口，
  但它们不再引用 MP4。共享的 `runtime/source_snapshot/assets/videos/` 未删除。
- 将 6 个标题文本的 Canela 字体槽替换为 Blender 内置字体，随后移除 Canela 字体数据块。
- 将余下 8 张静态图像全部打包进文件；更新版本注册表、版本元数据和验证报告。
- 记录用户新的长期 Git 交付要求：每次修改完成后创建 commit 并推送远程。

## 验证

- `tools/make_blend_self_contained.py`：通过；移除 24 个视频数据块和 1 个外部字体，
  打包资源 8 个，外部资源 0，Blender Library 0。
- `tools/validate_blend.py -- --version-id no-animation`：通过；非相机对象和形态键动作均为
  0，相机控制与 12 个景观场景入口保留，外部图片/视频 0，外部字体 0。
- `tools/render_validation.py`：成功生成 30 张回归图。
- `full` 基准 SHA-256 保持
  `03344698C5427F397255E46B5AB7B67EDDA38FDE312E475F8D2B32993E61482E`；目标文件
  SHA-256 更新为
  `29579509CCB1E13797DDE21961D9D90D26313A59749709DEE33D2ABF0FDA7572`。

## 结果

`no-animation` 现在采用 `self-contained-no-video-no-external-font` 资产策略；主场景可在没有
运行快照资源的情况下打开和渲染。视频景观入口保留为空材质结构，不再提供视频画面。
