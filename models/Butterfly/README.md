# Butterfly Blender 文件集

目录关系：`source/` 是 18 个源文件的唯一原样来源，`scenes/` 保存基于这些源文件
生成的 Blender 场景，`metadata/` 保存源清单，`archive/legacy/` 保留历史文件。

此目录现在按每个源 FBX 输出独立 Blender 文件；每个独立文件的 ARTIST_EDIT 只显示一个对应模型，动画可直接播放。

## 文件

- `scenes/master/Butterfly_Master.blend`：全素材总文件，包含 10 个源 FBX 的 SOURCE_REFERENCE 数据，默认展示 Butterfly_Idle_1。
- `scenes/idle/Butterfly_Idle_1.blend` 至 `Butterfly_Idle_7.blend`：对应 `source/animations/idle/` 的独立场景。
- `scenes/follow_path/`：对应 `source/animations/follow_path/` 的 Follow Path 场景。
- `scenes/slow_flap/BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.blend`：对应慢速扇翅源 FBX。

## 头部跟随摄像机版本

以下两个文件是 Follow Path 原文件的独立副本；原始两个 Follow Path 文件保持不变：

- `scenes/follow_path/head_camera/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_HEAD_CAMERA.blend`
- `scenes/follow_path/head_camera/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_HEAD_CAMERA.blend`

这两个副本的 `ARTIST_EDIT` 默认摄像机为 `CAMERA_HEAD_FOLLOW`，绑定关系为：

`CAMERA_HEAD_FOLLOW → CAMERA_HEAD_ANCHOR → 展示身体网格 → 原始 FBX 父级动画链`

镜头是参考图所示的自上而下正面展开第三人称视角。`CAMERA_HEAD_FOLLOW` 的位置通过头部父级链跟随蝴蝶，`CAMERA_HEAD_TRACK_TO` 使用 `DAMPED_TRACK` 持续旋转对准 `CAMERA_HEAD_LOOK_TARGET`，因此蝴蝶飞行、转向时摄像机也会不断更新朝向并保持正面构图；原来的 `蝴蝶_英雄相机` 仍保留。当前 FBX 没有独立的头部对象，因此 `CAMERA_HEAD_ANCHOR` 使用展示身体网格的头部端几何位置作为绑定点，`CAMERA_HEAD_LOOK_TARGET` 作为整体蝴蝶展开区域的瞄准参考点。

手动调整摄像机：

1. 在 `ARTIST_EDIT` 中选中 `CAMERA_HEAD_ANCHOR`，移动它可以调整头部绑定位置。
2. 选中 `CAMERA_HEAD_FOLLOW`，移动或旋转它可以调整第三人称镜头的距离、高度和视角。
3. 保留 `CAMERA_HEAD_FOLLOW` 的父级 `CAMERA_HEAD_ANCHOR` 和 `CAMERA_HEAD_TRACK_TO` 约束，这样摄像机才会跟随并持续对准蝴蝶。
4. 播放第 1 帧到最后一帧检查正面构图；运动路径仍可在原有 Follow Path 动画空物体上编辑。

## Master 扇翅替换版本

以下两个文件均以 `Butterfly_Master.blend` 为基准，分别使用对应 Follow Path 文件中的左右翅膀扇动变化：

- `scenes/wing_flap_only/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_WING_FLAP_ONLY.blend`
- `scenes/wing_flap_only/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_WING_FLAP_ONLY.blend`

这两个版本的场景、展示根、身体、材质、相机、灯光和整体布局都来自 Master。`ARTIST_EDIT` 只替换左右翅膀的扇动变化：翅膀第 1 帧的位置/旋转保持 Master 原值，Follow Path 的路径位移和路径转向不会应用到 Master。`SOURCE_REFERENCE` 保留 Master 原有的全部源对象和 Action，方便核对源数据；Master 原文件与两个 Follow Path 原文件均不覆盖。

专用构建脚本：`tools/build_butterfly_master_wing_flap_variants.py`
专用验证脚本：`tools/validate_butterfly_master_wing_flap_variants.py`
专用构建报告：`reports/butterfly-master-wing-flap-variants.json`
专用验证报告：`reports/butterfly-master-wing-flap-validation.json`

## 打开方式

- 默认场景 `ARTIST_EDIT`：单个已居中的展示模型，展示副本保持左右翅膀的原始父子关系和动作；编辑两个 `follow_path` 文件时切换到中文 `动画` 工作区即可。
- 场景 `SOURCE_REFERENCE`：对应文件的原始 FBX 导入对象；用于核对源数据，不会与其它动画叠加。
- 两个 `follow_path` 文件已保存 Blender Motion Path：打开 `ARTIST_EDIT` 后选中名称以 `展示_` 开头的动画空物体，即可看到轨迹；通过该对象的 Action 关键帧可以手动调整运动。`SOURCE_REFERENCE` 同时保留原始 FBX 空物体的轨迹显示。
- 顶部工作区已固定为中文：`布局`、`建模`、`动画`、`合成` 等；如果手动切换语言或加载旧文件，运行 `tools/fix_butterfly_chinese_workspaces.py` 可重新固定。
- `source/`：18 个源文件的唯一原样来源；4 张图像已同时打包进每个 `.blend`。
- `scenes/follow_path/head_camera/`：两个不覆盖原文件的头部跟随摄像机副本。
- `metadata/source-files.json`：记录每个源文件的大小与 SHA-256。
- C4D 不能被 Blender 5 原生解析；C4D 原始字节保存在 `蝴蝶_C4D原始二进制_Base64` 文本块，并有 SHA-256 记录。

## 翅膀修正说明

上一版的问题是把所有 FBX 同时放进一个源场景，并把展示变换叠加到层级中的多个对象上。新版每个文件只显示一个 FBX，展示缩放只施加于单一展示根节点；源对象和 Action 不改名、不合并、不删除。

## 手动编辑 Follow Path

FBX 里的路径是动画关键帧，不是可直接拖拽的曲线。操作步骤：

1. 打开 `scenes/follow_path/` 下的文件，保持场景为 `ARTIST_EDIT`。
2. 在视图中选中已自动选中的 `展示_..._03_...` 动画空物体；按小键盘 `.`（View Selected）可将它和轨迹居中。
3. 切换顶部 `动画` 工作区，在 Dope Sheet 或 Graph Editor 中编辑这个对象的 Location/Rotation 关键帧。
4. 修改后执行 `物体（Object）→ 运动路径（Motion Paths）→ 更新路径（Update Paths）`。

这会调整展示动画的运动轨迹；`SOURCE_REFERENCE` 仍保留原始 FBX 关键帧，作为对照。

构建报告：`reports/butterfly-variants-build.json`
头部摄像机验证结果：`reports/butterfly-validation.json`
预览图：`generated/Butterfly_preview.png`
