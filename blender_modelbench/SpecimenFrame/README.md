# Transparent Pale Lavender Specimen Frame

这是一个独立的 Blender 标本方框模型，交付文件位于：

`blender/Specimen_Frame_Transparent.blend`

模型由两个可独立编辑的实体组成；当前版本不保留任何修改器，也没有应用或保留 Bevel：

- `SPECIMEN_OUTER_FRAME`：带开口和真实厚度的方形环体，使用半透明白色材质 `MAT_OuterFrame_TranslucentWhite`。
- `SPECIMEN_INNER_PANEL`：嵌入外框开口的独立有厚度方板，使用透明浅紫色材质 `MAT_InnerPanel_TransparentLavender`。

文件中没有 Bevel、`Subdivision Surface` 或其他修改器，保留的是 `c5a6b12` 的基础方形网格。当前姿态已立在 Y-Z 平面，厚度沿 X，且立起旋转已应用到网格，两个对象的 Rotation 数值为 0；紫色主体已设为外框的子物体，会跟随外框变换。外框底面中心原点位于世界原点，整体模型向世界 Z 正方向延伸；紫色主体原点位于自身几何中心。旧的 Area 灯光组件已移除，World 使用打包进文件的 Blender Studio HDRI 作为环境光。打开文件后，在 `布局` 或 `着色` 工作区使用 `渲染` 查看 HDRI 环境光、透明和高光效果；底色背景仍为透明，中心紫色已调浅。

尺寸（Blender 单位）：整体 9.1、开口 7.1、外框深度 0.42、中心板深度 0.28。

构建脚本：`../../tools/build_specimen_frame_scene.py`

验证报告：`../../reports/specimen-frame-validation.json`

## 合并物体版本

另有一个基于上述文件生成的合并版本：`blender/Specimen_Frame_Transparent_Merged.blend`。
该版本将外框与紫色主体合并为单个 `SPECIMEN_FRAME_MERGED` 物体，同时保留两个材质槽；合并物体的物体原点位于合并后整体几何中心。模型实际位置、HDRI、相机、透明背景和无修改器状态保持不变。

合并版本构建脚本：`../../tools/build_specimen_frame_merged_scene.py`

合并版本验证报告：`../../reports/specimen-frame-merged-validation.json`

## 默认材质版本

另有一个几何优先版本：`blender/Specimen_Frame_Transparent_Default_Material.blend`。
该版本保留两个模型对象、父子层级、相机、透明背景和世界空间中的实际几何位置；
`SPECIMEN_OUTER_FRAME` 的物体原点位于其几何中心。两个模型对象使用 Blender 默认的
`Material` 材质，不含透明节点、Transmission 或自定义透明参数；World 和图像数据均已移除，
源文件不受影响。

默认材质版本构建脚本：`../../tools/build_specimen_frame_default_material.py`

默认材质版本验证报告：`../../reports/specimen-frame-default-material-validation.json`
