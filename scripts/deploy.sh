#!/bin/bash
set -e

# 部署脚本：在服务器上执行，拉取最新镜像并重启服务
# 用法：cd /path/to/project && bash scripts/deploy.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "[Deploy] Pulling latest images..."
docker compose pull api web

echo "[Deploy] Restarting services..."
docker compose up -d

echo "[Deploy] Pruning old images..."
docker image prune -af --filter "until=168h" > /dev/null 2>&1 || true

echo "[Deploy] Done."
docker compose ps
