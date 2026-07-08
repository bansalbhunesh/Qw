#!/usr/bin/env bash
#
# One-shot Auteur deploy for an Alibaba Cloud ECS instance (Ubuntu 22.04).
# Produces the *real* deployment proof: an un-mocked backend making a live Qwen
# call from the Alibaba host, so /healthz returns a real DashScope token count.
#
# Usage (on the ECS box, as root):
#   export DASHSCOPE_API_KEY=sk-your-real-key
#   curl -fsSL https://raw.githubusercontent.com/bansalbhunesh/Qw/main/deploy/ecs_setup.sh | bash
#
# ...or clone first and run:  DASHSCOPE_API_KEY=sk-... bash deploy/ecs_setup.sh
#
# Uses the lightweight API-only path (python -m deploy.alibaba_cloud), which fits the
# free-tier 2-core/2GB instance. For the full Studio too, use `docker compose up` instead
# (needs ~4GB). This script never enables mock mode — the whole point is a live call.
set -euo pipefail

KEY="${DASHSCOPE_API_KEY:-${1:-}}"
if [ -z "$KEY" ]; then
  echo "ERROR: set DASHSCOPE_API_KEY (export it, or pass as first arg)." >&2
  echo "  export DASHSCOPE_API_KEY=sk-...   then re-run" >&2
  exit 1
fi

REPO_URL="https://github.com/bansalbhunesh/Qw.git"
APP_DIR="${APP_DIR:-/opt/auteur}"
PORT="${PORT:-8000}"

echo "==> Installing system deps (python, pip, ffmpeg, git)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends python3-pip python3-venv ffmpeg git curl

echo "==> Fetching Auteur into $APP_DIR…"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> Python deps…"
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r requirements.txt

echo "==> Writing .env (real key, NOT mock)…"
cat > .env <<EOF
DASHSCOPE_API_KEY=$KEY
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
AUTEUR_MOCK=0
EOF

echo "==> Launching the API on 0.0.0.0:$PORT…"
pkill -f "deploy.alibaba_cloud" 2>/dev/null || true
set -a; . ./.env; set +a
nohup python3 -m deploy.alibaba_cloud > "$APP_DIR/auteur.log" 2>&1 &
APP_PID=$!
echo "    started PID $APP_PID (logs: $APP_DIR/auteur.log)"

echo "==> Waiting for health…"
for i in $(seq 1 30); do
  if curl -fsS "http://localhost:$PORT/healthz" >/dev/null 2>&1; then break; fi
  sleep 2
done

echo ""
echo "================ LIVE PROOF (screen-record this) ================"
echo "\$ curl http://localhost:$PORT/healthz"
curl -s "http://localhost:$PORT/healthz" | python3 -m json.tool || curl -s "http://localhost:$PORT/healthz"
echo ""
echo "================================================================"
echo "The 'dashscope' block above with a non-zero token count proves this"
echo "host really called Qwen Cloud. Now record: the ECS console (instance"
echo "id + region), this terminal, and a browser hitting the public IP:$PORT."
PUB=$(curl -s https://api.ipify.org 2>/dev/null || echo "<your-public-ip>")
echo "  Public health URL:  http://$PUB:$PORT/healthz"
