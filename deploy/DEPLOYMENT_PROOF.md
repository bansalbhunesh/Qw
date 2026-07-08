# Alibaba Cloud Deployment Proof

> Fill in the blanks after recording. This replaces the old mock-mode text log
> (which proved nothing). See `deploy/DEPLOY_ECS.md` for the full runbook and
> `deploy/ecs_setup.sh` for the one-shot deploy.

- **Recording (separate from the demo video):** https://youtu.be/__________
- **Instance ID:** i-__________________
- **Region:** ap-southeast-1 (Singapore)
- **Public IP:** ______._____._____.____  _(live during judging July 10–31; released after)_
- **Date recorded:** 2026-07-____

## What the recording shows

1. Alibaba Cloud ECS console — instance ID and region on screen.
2. `docker compose ps` (or the running `deploy.alibaba_cloud` process) on the host.
3. `curl http://localhost:8000/healthz` returning a real DashScope smoke test with a
   **non-zero token count** — proof the backend calls Qwen Cloud *from the Alibaba host*.
4. `curl http://<public-ip>:8000/healthz` from a separate machine — reachable publicly.
5. A browser on `http://<public-ip>:8080/` (if the full Studio is deployed).

## Code that uses Alibaba Cloud services

- `deploy/alibaba_cloud.py` — DashScope (Qwen/Qwen-VL/Wan) + OSS + the ECS service entrypoint.
- `auteur/agents/cinematographer.py` — OSS anchor/reference upload for Wan i2v/r2v conditioning.
- `auteur/transport.py` — DashScope OpenAI-compatible transport with retry/backoff.
