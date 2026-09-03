# 兰花模型

源素材按形态分区保存于 `source/形态1/` 和 `source/形态2/`；构建后的 Blender
场景统一位于 `scenes/`。`.blend` 文件仍保留原文件名和 Blender 内部数据。

- `source/形态1/`：Alembic、C4D、FBX、OBJ 及对应贴图。
- `source/形态2/`：Magnolia2 的 MAX、C4D、FBX、OBJ、MTL 及贴图。
- `scenes/兰花_形态1.blend`、`scenes/兰花_形态2.blend`：对应形态的场景交付。

构建脚本：`../../tools/build_orchid_scenes.py`。
