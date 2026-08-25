# Blender SceneBench 版本管理

当前工作台仍位于 `blender_scenebench/`。本目录集中保存已经创建或未来创建的派生版本；工具、版本清单和 Blender 工程记忆仍在工作台根目录共用。

## 版本边界

- `full` 是唯一完整基准版本：`blender/GwayLoo_Scene_5_0.blend`。
- 派生版本必须从 `full` 生成独立 `.blend`，不得使用 Blender 链接库共享可变数据。
- 派生版本使用 `versions/<version-id>/blender/`，并拥有自己的 `reports/` 和 `generated/` 输出目录。
- 版本制作工具不会修改来源文件；资源路径会按照目标 `.blend` 的新目录重新计算。
- 资源或结构验证失败时，版本不能标记为可用。
- `no-animation` 在第 3586 帧固化全部非相机对象和形态键，删除水彩图层与草地动画，只保留相机动画。

## 计划中的正式位置

未来如果正式迁移工作台，完整版本保持用户约定的入口：

```text
blender/_scenebench/blender/GwayLoo_Scene_5_0.blend
```

派生版本示例：

```text
blender/_scenebench/versions/no-animation/blender/GwayLoo_Scene_5_0_no_animation.blend
```

当前仍不创建 `blender/_scenebench/`；完整文件保持在当前工作台，派生文件位于集中版本目录。

## 当前版本

已创建并验证：

```text
versions/no-animation/blender/GwayLoo_Scene_5_0_no_animation.blend
```

该版本来自 `full`，默认显示第 3586 帧的立起终态；相机仍可按 0–3586 帧播放。

## 预演与创建

安全预演不会写入文件：

```powershell
python blender_scenebench/tools/prepare_blend_version.py --version-id no-animation --dry-run
```

真正创建派生版本时必须显式使用 `--create`：

```powershell
python blender_scenebench/tools/prepare_blend_version.py `
  --version-id no-animation `
  --create `
  --blender 'F:\Blender\blender.exe'
```

创建后仍需对目标文件执行独立的 Blender 结构验证和渲染验证。当前 `no-animation` 的变体动作由注册表的 `remove-all-non-camera-animation` 明确指定，不会作用于 `full`。

验证当前版本：

```powershell
& 'F:\Blender\blender.exe' --background --factory-startup `
  blender_scenebench/versions/no-animation/blender/GwayLoo_Scene_5_0_no_animation.blend `
  --python blender_scenebench/tools/validate_blend.py -- `
  --version-id no-animation `
  --report blender_scenebench/versions/no-animation/reports/blender-validation.json
```
