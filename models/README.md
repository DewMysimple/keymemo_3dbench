# 模型工作台

`models/` 只保存模型基准及其源素材。每个模型遵循同一条关系：

```text
source/   原始模型、动画、贴图或导入辅助文件
    ↓
scenes/   基于 source 构建的 Blender 场景与可验证交付文件
```

模型之间互不嵌套，也不与 `scenes/GwayLoo/` 产生父子关系。共享的构建工具、
验证报告和运行资源分别位于仓库根目录的 `tools/`、`reports/` 和
`runtime/source_snapshot/`。

| 模型 | source | scenes | 备注 |
| --- | --- | --- | --- |
| Butterfly | `Butterfly/source/` | `Butterfly/scenes/` | `metadata/` 保存源清单，`archive/legacy/` 保留历史文件 |
| SpecimenFrame | 无外部源目录；场景本身为基准 | `SpecimenFrame/scenes/` | `Specimen_Frame_Transparent.blend` 单一正式版本 |
| 兰花 | `兰花/source/形态1/`、`兰花/source/形态2/` | `兰花/scenes/` | 保留原始 Alembic、FBX、OBJ、C4D、贴图 |
| 杜鹃花 | `杜鹃花/source/` | `杜鹃花/scenes/` | 含形态1与三角梅源素材 |
| 水 | `水/source/` | `水/scenes/` | 保留 Unreal `.uasset` 源文件 |

详细的文件关系和打开方式见各模型目录的 README。
