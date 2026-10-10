#!/bin/zsh
# 启动玄知见解运营服务（后台常驻，日志 logs/api.log，pid data/api.pid）
set -e
cd "$(dirname "$0")/.."
PID_FILE=data/api.pid
LOG_DIR=logs
[ -d "$LOG_DIR" ] || mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "服务已在运行（pid $(cat "$PID_FILE")）"
  exit 0
fi

if [ ! -x .venv/bin/uvicorn ]; then
  echo "未找到 .venv，先运行: make venv && make install"
  exit 1
fi

# 首次启动自动迁移
.venv/bin/alembic -c alembic.ini upgrade head

HOST="${API_HOST:-127.0.0.1}"
PORT="${API_PORT:-8700}"
# 用 detach.py 以新会话启动：父 shell / 会话结束后服务继续常驻
.venv/bin/python scripts/detach.py "$LOG_DIR/api.log" .venv/bin/uvicorn apps.api.main:app --host "$HOST" --port "$PORT" &
echo $! > "$PID_FILE"
sleep 2

if [ ! -f apps/web/dist/index.html ]; then
  echo "   提示: 前端管理台未构建，API 仍可用；构建: cd apps/web && npm install && npm run build"
fi

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "✅ 服务已启动: http://$HOST:$PORT  (pid $(cat "$PID_FILE"))"
  echo "   健康检查: curl http://$HOST:$PORT/health"
  echo "   停止:     ./scripts/stop.sh"
else
  echo "❌ 启动失败，查看日志: tail -30 $LOG_DIR/api.log"
  exit 1
fi
