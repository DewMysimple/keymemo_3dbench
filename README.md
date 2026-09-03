# keymemo_3dbench

独立的 Blender 5.0 模型与场景工作台。仓库根目录就是工作台根目录，源自
`Verminoble/blender_scenebench` 的提取历史；本仓库不依赖 Verminoble 的路径、
运行时或 Git 子模块。

## 目录

- `scenes/GwayLoo/`：GwayLoo 主场景、完整基准和派生版本。
- `models/`：按模型分区的源素材、模型场景、元数据和历史归档；每个模型目录
  的 `source/` 与 `scenes/` 一一对应。
- `runtime/source_snapshot/`：纳入仓库的运行资源快照，用于消除对 Verminoble
  `public/.../xp` 的依赖。
- `tools/`：资源准备、清单生成、Blender 构建、修复、验证和渲染脚本。
- `manifests/`：资源、场景、版本和本地大文件清单。
- `reports/`：构建、验证、渲染和迁移报告。
- `wiki_memory/`：本工程的当前状态、决策、知识和历史日志。

模型导航：`models/Butterfly/`、`models/SpecimenFrame/`、`models/兰花/`、
`models/杜鹃花/`、`models/水/`。每个模型的 README 说明 `source → scenes` 的
来源关系；Butterfly 另有 `metadata/` 和 `archive/legacy/`。

## 主文件与版本

`scenes/GwayLoo/full/GwayLoo_Scene_5_0.blend` 是 `full` 完整基准文件。
`scenes/GwayLoo/versions/no-animation/` 是保留相机动画、移除非相机动画的独立版本。
SpecimenFrame 同时保留双组件原始版本和合并为单物体的版本；两者均不含修改器，
其 HDRI 世界环境按文件内设置保存。

## 资源策略

主 `.blend` 的外部媒体统一指向仓库内的 `runtime/source_snapshot/assets/`；生成 Ground
图集和字体等必要的派生数据可以嵌入 `.blend`。`generated/`、渲染缓存和 Blender
自动备份不进入 Git。三个超过 GitHub 100 MB 限制的原始文件保留在本地，详见
`manifests/local_assets_manifest.json`，不会上传远程仓库。

## 常用命令

在仓库根目录执行：

```powershell
python tools/generate_manifests.py
python tools/migrate_workbench_layout.py
python wiki_memory/工具/memory_lint.py index
python wiki_memory/工具/memory_lint.py check
& 'F:\Blender\blender.exe' --background --factory-startup --python tools/build_blender_scene.py
& 'F:\Blender\blender.exe' --background --factory-startup scenes/GwayLoo/full/GwayLoo_Scene_5_0.blend --python tools/validate_blend.py
& 'F:\Blender\blender.exe' --background --factory-startup scenes/GwayLoo/full/GwayLoo_Scene_5_0.blend --python tools/render_validation.py
```

版本准备使用 `python tools/prepare_blend_version.py --version-id <id> --dry-run`；
确认后才使用 `--create`。修改材质或透明度前请先阅读
`reports/rendering-boundaries.md`。

目录迁移工具默认只做预演；只有明确传入 `--apply` 才移动文件。迁移会校验目标
冲突、本地大文件哈希，并使用 Blender 5.0 检查场景结构与资源路径。
