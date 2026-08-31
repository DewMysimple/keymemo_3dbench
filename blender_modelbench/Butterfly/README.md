# Butterfly Blender 文件集

输出目录：`blender_scenebench/blender_modelbench/Butterfly`

此目录现在按每个源 FBX 输出独立 Blender 文件；每个独立文件的 ARTIST_EDIT 只显示一个对应模型，动画可直接播放。

## 文件

- `blender/Butterfly_Master.blend`：全素材总文件，包含 10 个源 FBX 的 SOURCE_REFERENCE 数据，默认展示 Butterfly_Idle_1。
- `blender/idle/Butterfly_Idle_1.blend`：animations/idle/Butterfly_Idle_1.fbx；源对象 4 个，Action 2 个。
- `blender/idle/Butterfly_Idle_2.blend`：animations/idle/Butterfly_Idle_2.fbx；源对象 4 个，Action 2 个。
- `blender/idle/Butterfly_Idle_3.blend`：animations/idle/Butterfly_Idle_3.fbx；源对象 4 个，Action 2 个。
- `blender/idle/Butterfly_Idle_4.blend`：animations/idle/Butterfly_Idle_4.fbx；源对象 4 个，Action 2 个。
- `blender/idle/Butterfly_Idle_5.blend`：animations/idle/Butterfly_Idle_5.fbx；源对象 4 个，Action 2 个。
- `blender/idle/Butterfly_Idle_6.blend`：animations/idle/Butterfly_Idle_6.fbx；源对象 4 个，Action 2 个。
- `blender/idle/Butterfly_Idle_7.blend`：animations/idle/Butterfly_Idle_7.fbx；源对象 4 个，Action 2 个。
- `blender/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend`：animations/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.fbx；源对象 6 个，Action 3 个。
- `blender/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend`：animations/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.fbx；源对象 6 个，Action 3 个。
- `blender/slow_flap/BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.blend`：animations/slow_flap/BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.fbx；源对象 4 个，Action 2 个。

## 打开方式

- 默认场景 `ARTIST_EDIT`：单个已居中的展示模型，展示副本保持左右翅膀的原始父子关系和动作。
- 场景 `SOURCE_REFERENCE`：对应文件的原始 FBX 导入对象；用于核对源数据，不会与其它动画叠加。
- `source/`：18 个源文件的唯一原样来源；4 张图像已同时打包进每个 `.blend`。
- `manifests/source-files.json`：记录每个源文件的大小与 SHA-256。
- C4D 不能被 Blender 5 原生解析；C4D 原始字节保存在 `蝴蝶_C4D原始二进制_Base64` 文本块，并有 SHA-256 记录。

## 翅膀修正说明

上一版的问题是把所有 FBX 同时放进一个源场景，并把展示变换叠加到层级中的多个对象上。新版每个文件只显示一个 FBX，展示缩放只施加于单一展示根节点；源对象和 Action 不改名、不合并、不删除。

构建报告：`blender_scenebench/reports/butterfly-variants-build.json`
预览图：`blender_scenebench/generated/Butterfly_preview.png`
