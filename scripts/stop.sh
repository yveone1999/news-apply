#!/bin/zsh
# 停止玄知见解运营服务
cd "$(dirname "$0")/.."
PID_FILE=data/api.pid
if [ ! -f "$PID_FILE" ]; then
  echo "未找到 pid 文件（服务可能未运行）"
  exit 0
fi
PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null
  echo "✅ 服务已停止 (pid $PID)"
else
  echo "进程 $PID 不存在，清理 pid 文件"
fi
rm -f "$PID_FILE"
