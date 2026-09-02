---
type: log
status: archived
kind: maintenance
importance: high
updated: 2026-09-02
topic: standalone-blender-workbench-migration
source_logs:
  - "[[日志/2026-08-25-Blender工作台重命名与记忆迁移|Blender 工作台重命名与记忆迁移]]"
---

# Blender 工作台独立迁移至 keymemo_3dbench

## 请求

将 `Verminoble/blender_scenebench` 抽出为独立工程
`C:/Users/Administrator/Desktop/keymemo_3dbench`，保留原目录作为本地备份，
迁移相关工程记忆，并使用远程仓库管理新工程。

## 实施

- 使用 `git subtree split --prefix=blender_scenebench` 提取工作台相关历史，并将
  提取树展开到新仓库根目录。
- 纳入 `source_snapshot/` 和主文件 `blender/GwayLoo_Scene_5_0.blend`；不迁移
  `generated/` 缓存内容、自动备份和临时转换产物。
- 将主 `.blend` 及派生版本的外部资源规范为仓库内 `source_snapshot/assets/`
  相对路径。
- 将三项超过 GitHub 100 MB 限制的原始文件保留在本地，写入
  `manifests/local_assets_manifest.json` 并加入 `.gitignore`；从新仓库历史中
  清除对应 Blob。
- 更新根目录说明、构建脚本、版本清单和当前工程记忆；历史日志正文保持历史
  语义，不回写为当前路径。

## 验证

迁移后检查源仓库工作区和关键资产哈希不变，目标仓库脚本路径不再依赖旧工作台
前缀，记忆索引和体检通过，并在推送前检查 Git 历史中不存在超过 100 MB 的对象。
