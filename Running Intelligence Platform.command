#!/bin/zsh
set -e

cd "$(dirname "$0")"

PYTHON_CMD="python3"
APP_PYTHON="$PYTHON_CMD"
DASHBOARD_PORT="8766"

stop_server_on_port() {
  local port="$1"
  local label="$2"
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -z "$pids" ]; then
    return 0
  fi

  echo "偵測到 $label http://127.0.0.1:$port 已經在執行，正在關閉舊伺服器..."
  for pid in ${(f)pids}; do
    kill "$pid" 2>/dev/null || true
  done

  for _ in {1..30}; do
    if ! lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "$label 舊伺服器已關閉。"
      return 0
    fi
    sleep 0.2
  done

  echo "無法自動關閉 $label。請先關掉舊視窗，或在終端機執行："
  echo "lsof -nP -iTCP:$port -sTCP:LISTEN"
  exit 1
}

if [ -x ".venv/bin/python" ]; then
  APP_PYTHON=".venv/bin/python"
elif [ -d ".venv/lib/python3.14/site-packages" ]; then
  export PYTHONPATH=".venv/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
else
  "$PYTHON_CMD" -m venv .venv
  APP_PYTHON=".venv/bin/python"
fi

if ! "$APP_PYTHON" - <<'PY' >/dev/null 2>&1
import garmin_fit_sdk
import openpyxl
import garminconnect
PY
then
  "$PYTHON_CMD" -m venv --clear .venv
  APP_PYTHON=".venv/bin/python"
  "$APP_PYTHON" -m pip install -r requirements.txt
fi

stop_server_on_port "$DASHBOARD_PORT" "Running Intelligence Platform"

echo "啟動 Running Intelligence Platform..."
echo "首頁會先打開平台；需要轉檔時，再從首頁進入 RAC。"
echo ""
echo "平台網址：http://127.0.0.1:$DASHBOARD_PORT/"
echo "按 Ctrl+C 或直接關閉視窗即可停止。"
echo ""

exec "$APP_PYTHON" analysis_platform/dashboard_app.py analysis_platform/running_analytics.sqlite --port "$DASHBOARD_PORT"
