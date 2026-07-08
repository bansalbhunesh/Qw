# Alibaba Cloud Deployment Proof

Per the hackathon rules, the required proof of Alibaba Cloud usage is **a link to a code
file in the repository that demonstrates use of Alibaba Cloud services and APIs**. Auteur
satisfies this directly — the backend is built on Alibaba Cloud services and there is a
live, metered run proving real calls.

## Alibaba Cloud services used (code-file proof)

| Alibaba Cloud service | Where it's used | What it does |
|---|---|---|
| **Model Studio / DashScope** (`dashscope-intl.aliyuncs.com`) | [`auteur/config.py`](../auteur/config.py) (base URLs), [`auteur/transport.py`](../auteur/transport.py), [`deploy/alibaba_cloud.py`](./alibaba_cloud.py) | All Qwen LLM/VL and Wan video calls — the entire generative pipeline runs on Qwen models on Qwen Cloud |
| **OSS** (Object Storage Service) | [`auteur/agents/cinematographer.py`](../auteur/agents/cinematographer.py) (`_upload_image`) | Uploads anchor/reference frames so Wan i2v/r2v can condition on them |
| **ECS service entrypoint** | [`deploy/alibaba_cloud.py`](./alibaba_cloud.py) | FastAPI app packaged to run the backend on Alibaba Cloud ECS (see `deploy/DEPLOY_ECS.md`) |

## Live evidence (real calls, not mock)

`out_live/ledger.json` records a real production run against Alibaba Cloud with per-call
metering. Models actually invoked:

- `qwen-max`, `qwen-flash` (Qwen LLM tiers, via DashScope)
- `qwen-vl-max` (Qwen-VL critic, via DashScope)
- `wan2.2-t2v-plus` (Wan video generation, via DashScope)

Result: a 7.3/10-scored short drama, 13,043 tokens, ~$0.60 estimated — every row auditable.

## Optional: backend hosted on Alibaba Cloud compute (recording)

If a live-hosting recording is also submitted, use `deploy/ecs_setup.sh` (one-shot deploy)
and record per `deploy/DEPLOY_ECS.md`. Fill in after recording:

- **Recording:** https://youtu.be/__________ · **Instance ID:** i-__________ · **Region:** ap-southeast-1 · **Date:** 2026-07-____

> **Note (India / free-tier).** Alibaba Cloud's *free trial* is not currently offered for
> India-based individual accounts, which blocks the free ECS instance. The account itself and
> Model Studio/DashScope + OSS usage are fully functional (see the live ledger). Compute
> hosting can still be done pay-as-you-go or via Function Compute if required — but the
> code-file proof above is the form the rules explicitly ask for. See
> `deploy/ORGANIZER_QUESTION.md` for the clarification requested from the organizers.
