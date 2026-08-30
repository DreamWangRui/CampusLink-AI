#!/bin/bash
# ============================================================
# CampusLink AI 数据卷备份脚本（Linux / macOS / Git Bash）
# 备份 chroma_db（知识库）与 uploads（源文件）两个数据卷
# hf_cache（Embedding 模型缓存）体积大且可重新下载，默认不备份
# ============================================================
set -e

# Git Bash 下禁用 MSYS 路径转换（防止 /backup 被改写为 Windows 路径）
export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/../backups"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "==== CampusLink AI 数据卷备份 ===="

for VOLUME in campuslink_chroma_data campuslink_upload_data; do
    docker run --rm -v "$VOLUME":/data:ro -v "$BACKUP_DIR":/backup alpine \
        sh -c "tar czf /backup/${VOLUME}_${STAMP}.tar.gz -C /data ."
    echo "✓ $VOLUME -> backups/${VOLUME}_${STAMP}.tar.gz"
done

echo "==== 备份完成 ===="
echo "恢复单个卷："
echo "  docker run --rm -v <卷名>:/data -v $BACKUP_DIR:/backup alpine sh -c 'rm -rf /data/* && tar xzf /backup/<备份文件名>.tar.gz -C /data'"
