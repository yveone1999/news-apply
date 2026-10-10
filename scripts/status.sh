#!/bin/zsh
# 查看服务状态
cd "$(dirname "$0")/.."
PORT="${API_PORT:-8700}"
if [ -f data/api.pid ] && kill -0 "$(cat data/api.pid)" 2>/dev/null; then
  echo "进程: 运行中 (pid $(cat data/api.pid))"
else
  echo "进程: 未运行"
fi
RESP=$(curl -s -m 3 http://127.0.0.1:$PORT/health 2>/dev/null) && echo "健康: $RESP" || echo "健康: 不可达"
