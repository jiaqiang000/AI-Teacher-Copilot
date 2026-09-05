#!/usr/bin/env bash
# 智能作业批改系统(Teacher Copilot,V2)本地 production 一键部署(进程式,非 Docker)
#
# 用法(在 deer-flow/ 根目录执行):
#   ./scripts/deploy-local.sh              # 启动后端(uvicorn :8001)+ 前端(next start :3000)
#   ./scripts/deploy-local.sh --seed       # 初始化双角色账号（班级作业数据使用现有数据库）
#   ./scripts/deploy-local.sh --rebuild    # 强制重建前端生产包
#   ./scripts/deploy-local.sh --stop       # 停止前后端进程
#
# 端口可经环境变量覆盖:GATEWAY_PORT(默认 8001)/ FRONTEND_PORT(默认 3000)
# 前提:backend 完成 uv sync,frontend 完成 npm install。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
GATEWAY_PORT="${GATEWAY_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

SEED=0; REBUILD=0; STOP=0
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=1 ;;
    --rebuild) REBUILD=1 ;;
    --stop) STOP=1 ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

REQUIRED_ENV=("DEEPSEEK_API_KEY" "TC_LLM_API_KEY" "TC_OCR_API_KEY")

load_env() {
  if [ -f "$BACKEND/.env" ]; then
    set -a; # shellcheck disable=SC1091
    . "$BACKEND/.env"; set +a
  fi
}

check_env() {
  local missing=0
  for k in "${REQUIRED_ENV[@]}"; do
    if [ -z "${!k:-}" ]; then
      echo "[ERROR] 缺少环境变量 $k(参考 backend/.env.example,配置在 backend/.env)" >&2
      missing=1
    fi
  done
  if [ "$missing" -ne 0 ]; then
    echo "[ERROR] 环境变量校验失败,中止部署。" >&2; exit 1
  fi
  if [ -z "${TC_OSS_BUCKET:-}" ]; then
    echo "[WARN] 未配置 TC_OSS_*:图片上传/OCR 回填不可用(演示其余功能不受影响;"
    echo "      需要学生上传作答时,在 backend/.env 补充 TC_OSS_ACCESS_KEY_ID /"
    echo "      TC_OSS_ACCESS_KEY_SECRET / TC_OSS_BUCKET / TC_OSS_ENDPOINT)。"
  fi
}

stop_services() {
  pkill -f "uvicorn app.gateway.app:app" 2>/dev/null || true
  pkill -f "next start" 2>/dev/null || true
  pkill -f "next-server" 2>/dev/null || true
  echo "已停止后端与前端进程。"
}

start_backend() {
  echo "[1/4] 启动 Gateway 后端(127.0.0.1:$GATEWAY_PORT)..."
  cd "$BACKEND"
  nohup .venv/bin/python -m uvicorn app.gateway.app:app \
    --host 127.0.0.1 --port "$GATEWAY_PORT" \
    > "$LOG_DIR/gateway.log" 2>&1 &
  # 健康检查等待(首次启动会初始化 DB,最长 60s;未登录时 healthz 返回 401 属正常)
  for i in $(seq 1 30); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$GATEWAY_PORT/api/teacher-copilot/healthz" || echo 000)"
    if [ "$code" = "200" ] || [ "$code" = "401" ]; then
      sleep 1; echo "  后端就绪 ✔"; return 0
    fi
    sleep 2
  done
  echo "[ERROR] 后端 60 秒内未就绪,查看 logs/gateway.log" >&2; exit 1
}

run_seed() {
  echo "[2/4] 初始化双角色账号(幂等)..."
  cd "$BACKEND"
  .venv/bin/python -m app.teacher_copilot.db.seed.seed_accounts
  echo "  seed 完成 ✔"
}

start_frontend() {
  echo "[3/4] 启动前端(127.0.0.1:$FRONTEND_PORT)..."
  cd "$FRONTEND"
  if [ "$REBUILD" -eq 1 ] || [ ! -d .next ]; then
    echo "  构建前端生产包(next build,约 1-2 分钟)..."
    # 先清 .next:避免增量 manifest 残留导致原生路由 500(如 /workspace/chats)
    rm -rf .next
    npm run build > "$LOG_DIR/frontend-build.log" 2>&1 || {
      echo "[ERROR] 前端构建失败,查看 logs/frontend-build.log" >&2; exit 1; }
  fi
  nohup npm run start > "$LOG_DIR/frontend.log" 2>&1 &
  for i in $(seq 1 15); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$FRONTEND_PORT/login" || echo 000)"
    if [ "$code" = "200" ] || [ "$code" = "302" ] || [ "$code" = "307" ]; then
      echo "  前端就绪 ✔"; return 0
    fi
    sleep 2
  done
  echo "[ERROR] 前端未就绪,查看 logs/frontend.log" >&2; exit 1
}

verify() {
  echo "[4/4] 部署验证..."
  code_gw="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$GATEWAY_PORT/api/teacher-copilot/healthz")"
  code_fe="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$FRONTEND_PORT/login")"
  echo "  前端: http://127.0.0.1:$FRONTEND_PORT/login → $code_fe"
  echo "  后端: http://127.0.0.1:$GATEWAY_PORT/api/teacher-copilot/healthz → $code_gw"
  echo "  体验账号: teacher@demo.com / teacher123456(教师)  student@demo.com / student123456(学生)"
  echo "  日志目录: $LOG_DIR"
}

load_env
if [ "$STOP" -eq 1 ]; then stop_services; exit 0; fi
check_env
stop_services
start_backend
if [ "$SEED" -eq 1 ]; then run_seed; fi
start_frontend
verify
echo "部署完成 ✔ 浏览器打开 http://127.0.0.1:$FRONTEND_PORT"
