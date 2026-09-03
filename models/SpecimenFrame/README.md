# Transparent Pale Lavender Specimen Frame

这是一个独立的 Blender 标本方框模型，交付文件位于：

`scenes/Specimen_Frame_Transparent.blend`

模型由两个可独立编辑的实体组成；当前版本不保留任何修改器，也没有应用或保留 Bevel：

- `SPECIMEN_OUTER_FRAME`：带开口和真实厚度的方形环体，使用半透明白色材质 `MAT_OuterFrame_TranslucentWhite`。
- `SPECIMEN_INNER_PANEL`：嵌入外框开口的独立有厚度方板，使用透明浅紫色材质 `MAT_InnerPanel_TransparentLavender`。

文件中没有 Bevel、`Subdivision Surface` 或其他修改器，保留的是 `c5a6b12` 的基础方形网格。当前姿态已立在 Y-Z 平面，厚度沿 X，且立起旋转已应用到网格，两个对象的 Rotation 数值为 0；紫色主体已设为外框的子物体，会跟随外框变换。外框底面中心原点位于世界原点，整体模型向世界 Z 正方向延伸；紫色主体原点位于自身几何中心。旧的 Area 灯光组件已移除，World 使用打包进文件的 Blender Studio HDRI 作为环境光。打开文件后，在 `布局` 或 `着色` 工作区使用 `渲染` 查看 HDRI 环境光、透明和高光效果；底色背景仍为透明，中心紫色已调浅。

尺寸（Blender 单位）：整体 9.1、开口 7.1、外框深度 0.42、中心板深度 0.28。

构建脚本：`../../tools/build_specimen_frame_scene.py`

验证报告：`../../reports/specimen-frame-validation.json`

## 合并物体版本

另有一个基于上述文件生成的合并版本：`scenes/Specimen_Frame_Transparent_Merged.blend`。
该版本将外框与紫色主体合并为单个 `SPECIMEN_FRAME_MERGED` 物体，同时保留两个材质槽；合并物体的物体原点位于合并后整体几何中心。模型实际位置、HDRI、相机、透明背景和无修改器状态保持不变。

合并版本构建脚本：`../../tools/build_specimen_frame_merged_scene.py`

合并版本验证报告：`../../reports/specimen-frame-merged-validation.json`

## 默认材质文件名下的紫晶内芯版本

`scenes/Specimen_Frame_Transparent_Default_Material.blend` 按用户确认覆盖为
Eevee 展示用紫晶内芯版本；文件名保留，但已不再是白色默认材质。

- 单对象 `SPECIMEN_OUTER_FRAME`，原点位于 `(0,0,4.55)`；外形 `0.42 × 9.1 × 9.1`。
- 材质槽1 `MAT_OuterFrame_TranslucentWhite` 覆盖外框12面，槽2
  `MAT_InnerPanel_TransparentLavender` 覆盖完整内芯6面。
- 内芯 `0.42 × 7.1 × 7.1`，正反面齐平；接触面只保留一层，侧面可以透过白框看见紫色。
- 16顶点/32边/18面，其中8条三面交汇边是有意保留的内部界面；本版本不作为打印或布尔实体。
- 使用直接 Principled、DITHERED、Alpha 与清漆高光，Transmission 为0；不是多层物理折射方案。
- 保留相机、透明背景、UVMap 和打包 Studio HDRI；渲染采样512，视口采样64。

从仓库根目录运行构建入口（旧 `no_material` 命令也转发到同一流程）：

```powershell
# 生成候选文件、备份和15张验证图；不覆盖正式文件。
& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/build_specimen_frame_default_material.py
# 检查候选目录中的图片后，用上一步输出的目录发布。
& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/build_specimen_frame_default_material.py -- --create --candidate generated/SpecimenFrame/crystal_core/<run-directory>
```

报告：`../../reports/specimen-frame-default-material-validation.json`；其中 `original_backup`
记录首次覆盖前的白色默认材质文件备份。构建实现位于 `../../tools/build_specimen_frame_crystal_core.py`，
只读回归测试位于 `../../tools/test_specimen_frame_crystal_core.py`。
