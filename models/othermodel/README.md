# othermodel OBJ 类别展示

`source/` 中的 61 个 OBJ 已按文件名语义分为 7 类；每类生成一个独立 Blender 文件，
文件位于 `scenes/`：

| 类别 | 数量 | Blender 文件 |
| --- | ---: | --- |
| Envelope | 39 | `scenes/Envelope.blend` |
| Bookmark | 10 | `scenes/Bookmark.blend` |
| Card | 6 | `scenes/Card.blend` |
| CardHolder | 3 | `scenes/CardHolder.blend` |
| BubbleMailer | 1 | `scenes/BubbleMailer.blend` |
| FoodPackaging | 1 | `scenes/FoodPackaging.blend` |
| PaperBackdrop | 1 | `scenes/PaperBackdrop.blend` |

每个文件都包含该类别的全部 OBJ 几何、按源文件名自然排序的展示网格、模型编号标签、
摄影机、灯光和展示地面；OBJ 导入后几何数据写入 `.blend`，打开文件不依赖源 OBJ。
`reports/build.json` 保存每类的完整源文件顺序，`reports/validation.json` 保存重新打开
后的结构与资源检查结果。

源 OBJ 声明了 `mtllib`，但当前 `source/` 未提供对应的 MTL 文件，因此导入时使用 Blender
默认材质；本次没有根据旁边的 JPG 预览图臆造材质贴图。
