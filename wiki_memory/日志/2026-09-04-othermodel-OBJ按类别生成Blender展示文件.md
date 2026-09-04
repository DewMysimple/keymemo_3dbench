---
type: log
status: archived
kind: feature
importance: high
updated: 2026-09-04
topic: othermodel-obj-category-showcases
source_logs:
  - "[[当前状态/系统架构|当前系统架构]]"
  - "[[知识/模块/工作台结构|工作台结构]]"
supersedes: null
---

# othermodel OBJ 按类别生成 Blender 展示文件

## 目标

将 `models/othermodel/source/` 下的 OBJ 模型按类别整理为 Blender 文件，每类一个文件，
并按源文件名排序展示。

## 修改

- 新增 `tools/build_othermodel_obj_collections.py`，导入 OBJ 几何，按语义类别分组并生成
  展示环境、标签、摄影机、灯光和展示地面。
- 新增 `tools/validate_othermodel_obj_collections.py`，重新打开每个输出文件，检查源文件
  顺序、模型根数量、网格数量、标签数量、摄影机和外部资源。
- 61 个 OBJ 分成 7 类：Envelope 39、Bookmark 10、Card 6、CardHolder 3、BubbleMailer 1、
  FoodPackaging 1、PaperBackdrop 1；输出位于 `models/othermodel/scenes/`。
- `models/othermodel/README.md` 记录类别清单和材质边界；源 OBJ 缺少 MTL，因此未臆造
  外部贴图，导入使用默认材质。

## 验证

- Blender 5.0 构建报告：`models/othermodel/reports/build.json`，61/61 OBJ 导入成功，
  7/7 类别通过，全部输出文件无外部资源或 Blender Library。
- 重新打开验证：`models/othermodel/reports/validation.json` 通过；7 个文件的模型根和
  标签数量分别为 39/39、10/10、6/6、3/3、1/1、1/1、1/1，源顺序与自然排序一致。
- 生成 7 张类别预览到 `generated/othermodel/`，Envelope 与 Bookmark 预览复核标题、
  首尾模型均未裁切。

## 结果

用户可直接打开 `models/othermodel/scenes/<Category>.blend` 查看对应类别的全部 OBJ 模型；
源 OBJ、MTL 和 JPG 文件不作为输出文件的运行时依赖。
