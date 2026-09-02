# keymemo_3dbench

独立的 Blender 5.0 模型与场景工作台。仓库根目录就是工作台根目录，源自
`Verminoble/blender_scenebench` 的提取历史；原 `Verminoble` 目录保留为本地
备份，本仓库不依赖它的路径、运行时或 Git 子模块。

## 目录

- `blender/`：主场景和稳定交付入口。
- `blender_modelbench/`：Butterfly、SpecimenFrame、兰花、杜鹃花和水等模型
  基准资产、源素材与交付文件。
- `source_snapshot/`：纳入仓库的运行资源快照，用于消除对 Verminoble
  `public/.../xp` 的依赖。
- `tools/`：资源准备、清单生成、Blender 构建、修复、验证和渲染脚本。
- `manifests/`：资源、场景、版本和本地大文件清单。
- `versions/`：独立派生 Blender 版本及其报告。
- `reports/`：构建、验证、渲染和迁移报告。
- `wiki_memory/`：本工程的当前状态、决策、知识和历史日志。

## 主文件与版本

`blender/GwayLoo_Scene_5_0.blend` 是 `full` 完整基准文件。
`versions/no-animation/` 是保留相机动画、移除非相机动画的独立版本。
SpecimenFrame 同时保留双组件原始版本和合并为单物体的版本；两者均不含修改器，
其 HDRI 世界环境按文件内设置保存。

## 资源策略

主 `.blend` 的外部媒体统一指向仓库内的 `source_snapshot/assets/`；生成 Ground
图集和字体等必要的派生数据可以嵌入 `.blend`。`generated/`、渲染缓存和 Blender
自动备份不进入 Git。三个超过 GitHub 100 MB 限制的原始文件保留在本地，详见
`manifests/local_assets_manifest.json`，不会上传远程仓库。

## 常用命令

在仓库根目录执行：

```powershell
python tools/generate_manifests.py
python wiki_memory/工具/memory_lint.py index
python wiki_memory/工具/memory_lint.py check
& 'F:\Blender\blender.exe' --background --factory-startup --python tools/build_blender_scene.py
& 'F:\Blender\blender.exe' --background --factory-startup blender/GwayLoo_Scene_5_0.blend --python tools/validate_blend.py
& 'F:\Blender\blender.exe' --background --factory-startup blender/GwayLoo_Scene_5_0.blend --python tools/render_validation.py
```

版本准备使用 `python tools/prepare_blend_version.py --version-id <id> --dry-run`；
确认后才使用 `--create`。修改材质或透明度前请先阅读
`reports/rendering-boundaries.md`。
