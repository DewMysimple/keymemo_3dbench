# Transparent Specimen Frame

SpecimenFrame 只保留一个正式的 Blender 展示文件：

`scenes/Specimen_Frame_Transparent.blend`

这是 Eevee 优先的透明外框与紫晶内芯单对象模型：

- 对象名为 `SPECIMEN_OUTER_FRAME`，没有独立内板对象。
- 整体尺寸为 `0.42 × 9.1 × 9.1`，内芯区域为 `0.42 × 7.1 × 7.1`。
- 正反面位于 `X=-0.21` 与 `X=+0.21`，内芯与外框无缝对齐。
- 材质槽1 `MAT_OuterFrame_TranslucentWhite` 覆盖外框12面。
- 材质槽2 `MAT_InnerPanel_TransparentLavender` 覆盖完整紫晶内芯6面，侧面可见紫色内芯。
- 网格为16顶点、32边、18面；8条三面交汇边是有意保留的内部材质界面，适合渲染展示，不作为打印或布尔实体。
- 使用直接 Principled、`DITHERED`、Alpha 与清漆高光；Transmission 为0，不依赖多层物理折射。
- 保留相机、透明背景、UVMap 和打包 Studio HDRI；渲染采样512，视口采样64。

## 构建与验证

从仓库根目录运行：

```powershell
# 生成候选文件、最近一次验证图和安全副本；不覆盖正式文件。
& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/build_specimen_frame_transparent.py

# 只发布已经验证且未被修改的候选目录。
& 'F:\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python tools/build_specimen_frame_transparent.py -- --create --candidate generated/SpecimenFrame/transparent/<run-directory>
```

发布流程成功后只保留最近一次 `generated/SpecimenFrame/transparent/` 验证结果，旧候选和诊断缓存会清理。

正式验证报告：`../../reports/specimen-frame-validation.json`

只读回归测试：`../../tools/test_specimen_frame_transparent.py`

Blender 用户偏好中的 `Save Versions` 已设置为 `0`，因此不会自动生成 `.blend1/.blend2`。
构建流程仍会在验证期间保留一个受控安全副本；该副本位于 `generated/`，不属于正式模型资产。
