# Blender SceneBench 版本预留

当前工作台仍位于 `blender_scenebench/`，本目录只定义未来版本产物的管理方式，不代表已经创建了派生 `.blend` 文件。

## 版本边界

- `full` 是唯一完整基准版本：`blender/Verminoble_Scene_Mirror_5_0.blend`。
- 派生版本必须从 `full` 生成独立 `.blend`，不得使用 Blender 链接库共享可变数据。
- 派生版本使用 `versions/<version-id>/blender/`，并拥有自己的 `reports/` 和 `generated/` 输出目录。
- 版本制作工具不会修改来源文件；资源路径会按照目标 `.blend` 的新目录重新计算。
- 资源或结构验证失败时，版本不能标记为可用。

## 计划中的正式位置

未来如果正式迁移工作台，完整版本保持用户约定的入口：

```text
blender/_scenebench/blender/Verminoble_Scene_Mirror_5_0.blend
```

派生版本示例：

```text
blender/_scenebench/versions/no-animation/blender/Verminoble_Scene_Mirror_5_0_no_animation.blend
```

本次不创建 `blender/_scenebench/`，也不复制或修改当前完整文件。

## 预演与创建

安全预演不会写入文件：

```powershell
python blender_scenebench/tools/prepare_blend_version.py --version-id no-animation --dry-run
```

真正创建派生副本时必须显式使用 `--create`：

```powershell
python blender_scenebench/tools/prepare_blend_version.py `
  --version-id no-animation `
  --create `
  --blender 'F:\Blender\blender.exe'
```

创建后仍需对目标文件执行独立的 Blender 结构验证和渲染验证；“去除动画”本身不是版本准备工具的隐式操作。
