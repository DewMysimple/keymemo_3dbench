# Transparent Pale Lavender Specimen Frame

这是一个独立的 Blender 标本方框模型，交付文件位于：

`blender/Specimen_Frame_Transparent.blend`

模型由两个可独立编辑的实体组成：

- `SPECIMEN_OUTER_FRAME`：带开口、带真实厚度和圆角的方形环体，使用半透明白色材质 `MAT_OuterFrame_TranslucentWhite`。
- `SPECIMEN_INNER_PANEL`：嵌入外框开口的独立有厚度方板，使用透明浅紫色材质 `MAT_InnerPanel_TransparentLavender`。

打开文件后，在 `布局` 或 `着色` 工作区切换到 `材质预览`，可以看到透明和玻璃高光效果。默认相机和中性冷灰背景只用于快速预览，不影响两个主体模型的独立编辑；冷灰背景用于避免背景色把浅紫内板污染成粉色。

尺寸（Blender 单位）：整体 9.1、开口 7.1、外框深度 0.42、中心板深度 0.28。

构建脚本：`../../tools/build_specimen_frame_scene.py`

验证报告：`../../reports/specimen-frame-validation.json`
