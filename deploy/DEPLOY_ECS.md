# Deploying Auteur on Alibaba Cloud ECS — copy-paste runbook

This produces the **real** deployment proof the hackathon requires (a short recording
of the backend running on Alibaba Cloud, separate from the demo video) — replacing the
old `alibaba_cloud_deployment_proof.txt`, which was captured in mock mode and proves
nothing. The whole thing is ~20 minutes plus a small ECS cost.

The trick that makes this proof *un-fakeable*: run **without** `AUTEUR_MOCK` and **with** a
real `DASHSCOPE_API_KEY`. Then `/healthz` performs a live Qwen smoke test and returns real
token counts — so the recording shows the backend actually calling Qwen Cloud **from the
Alibaba host**, next to the ECS console showing the instance ID. That is exactly what a
skeptical judge wants to see.

---

## 0. Prerequisites (5 min, one time)

- An Alibaba Cloud account with **Model Studio (DashScope)** enabled and an API key
  (`sk-...`). International console: https://dashscope.console.aliyun.com/
- Use the **Singapore** region — it matches the international DashScope endpoint
  (`dashscope-intl.aliyuncs.com`) and the default OSS endpoint (`oss-ap-southeast-1`).

## 1. Create the ECS instance (5 min)

- ECS → Create Instance. **Ubuntu 22.04**, `ecs.t6-c1m2.large` (2 vCPU / 4 GB) is plenty;
  pay-as-you-go so you can release it after judging.
- **Security Group inbound rules** — open these to `0.0.0.0/0` (demo only):
  - `22` (SSH), `8000` (API), `8080` (Studio)
- Note the **public IP** and the **instance ID** (`i-xxxxxxxxxxxxxxxxxxxx`) — the instance
  ID is the thing your recording must show.

## 2. Provision the host (5 min)

SSH in (`ssh root@<PUBLIC_IP>`), then:

```bash
# Docker (matches the verified docker-compose path)
curl -fsSL https://get.docker.com | sh

# Get the code
git clone https://github.com/bansalbhunesh/Qw.git && cd Qw

# Real key, NOT mock — this is what makes /healthz prove a live Qwen call
cat > .env <<'EOF'
DASHSCOPE_API_KEY=sk-REPLACE_WITH_YOUR_REAL_KEY
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
AUTEUR_MOCK=0
EOF
```

## 3. Launch (2 min)

```bash
docker compose up --build -d
docker compose ps         # both auteur (healthy) and viewer should be Up
```

The healthcheck fix (stdlib urllib, not curl) is already merged, so both containers come
up clean — verified locally. If you'd rather not use Docker:

```bash
apt-get update && apt-get install -y python3-pip ffmpeg
pip install -r requirements.txt
PORT=8000 python -m deploy.alibaba_cloud    # uvicorn on 0.0.0.0:8000
```

## 4. Prove it's live (2 min)

From the ECS box (and again from your laptop against the public IP):

```bash
curl http://localhost:8000/healthz
```

Expected — note the **`dashscope` block with a real token count**, which only appears with a
valid key and a real network call to Qwen Cloud:

```json
{"status":"ok","cloud":"alibaba",
 "dashscope":{"model":"qwen-flash","reply":"...","tokens":<non-zero>}}
```

Open the Studio in a browser: `http://<PUBLIC_IP>:8080/`

## 5. Record the proof (60–90s, one take)

Screen-record this sequence — keep it under 90 seconds, no cuts:

1. **ECS console** with the instance detail page visible — **instance ID and region on screen**.
2. SSH terminal: `hostname -I` (shows the private IP) then `docker compose ps` (both Up/healthy).
3. `curl http://localhost:8000/healthz` — pause on the JSON so the live `dashscope` tokens are readable.
4. From your **laptop**: `curl http://<PUBLIC_IP>:8000/healthz` — proves it's reachable on the public internet.
5. Browser on `http://<PUBLIC_IP>:8080/` — the Studio loading from the Alibaba host.

Upload as an **unlisted-but-public** YouTube video (separate from the demo video).

## 6. Commit the real proof, delete the fake one

Replace the mock log with a real proof doc (template below), then:

```bash
git rm deploy/alibaba_cloud_deployment_proof.txt
git add deploy/DEPLOYMENT_PROOF.md
git commit -m "docs: real Alibaba Cloud ECS deployment proof (instance id + recording)"
```

### `deploy/DEPLOYMENT_PROOF.md` template

```markdown
# Alibaba Cloud Deployment Proof

- **Recording:** https://youtu.be/XXXXXXXXXXX  (separate from the demo video)
- **Instance ID:** i-xxxxxxxxxxxxxxxxxxxx
- **Region:** ap-southeast-1 (Singapore)
- **Public IP:** xx.xx.xx.xx  (live during judging July 10–31; released after)
- **Date:** 2026-07-08
- **Services:** API :8000 (FastAPI + Qwen), Studio :8080
- **Live check:** `curl http://<ip>:8000/healthz` returns a real DashScope smoke test
  (`tokens` > 0), proving the backend calls Qwen Cloud from the Alibaba host.
- **Code using Alibaba services:** `deploy/alibaba_cloud.py` (DashScope/OSS/ECS),
  `auteur/agents/cinematographer.py` (OSS anchor-frame upload for Wan i2v).
```

## 7. Keep it warm for judging (optional but strong)

Leave the instance up July 10–31 in mock mode as a live judge sandbox:
`AUTEUR_MOCK=1 docker compose up -d`, and put `http://<PUBLIC_IP>:8080/` in the Devpost form.
Cost is a few dollars for the window and it neutralizes any "I couldn't run it" judge.

> Security note: `/produce` is unauthenticated. With a real key on a public IP, anyone who
> finds the URL can spend your DashScope quota. For the live sandbox use `AUTEUR_MOCK=1`
> (zero spend), and only run the un-mocked, real-key version during the short recording.
