#!/bin/bash
set -e

# ETL 定时运行脚本
# 建议配合 crontab 使用，例如每天凌晨 02:00 执行：
# 0 2 * * * cd /path/to/project && bash scripts/run-etl.sh >> logs/etl-cron.log 2>&1

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs

LOG_FILE="logs/etl-cron-$(date +%Y%m%d-%H%M%S).log"

echo "[ETL] Starting at $(date)" | tee -a "$LOG_FILE"
docker compose --profile etl run --rm etl >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "[ETL] Finished at $(date) with exit code $EXIT_CODE" | tee -a "$LOG_FILE"

# 可选：保留最近 30 天的日志
find logs -name 'etl-cron-*.log' -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
