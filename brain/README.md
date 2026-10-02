# Nexus Brain on Cloudflare

This directory deploys the **canonical personal Nexus Python brain** as a Cloudflare Container.

## Architecture

```
Nexus Pages site
      |
      | /api/chat + Bearer token
      v
Cloudflare Worker
      |
      v
NexusBrainContainer (Python)
      |
      v
src/core.py -> NexusBrain -> tools/memory/model
```

The existing `web_server.py` remains the API server used inside the container. The container listens on `0.0.0.0:8080` in Cloudflare and still listens on `127.0.0.1:8787` for normal local development when no environment variables are set.

## Cloudflare deployment

Cloudflare Containers are a **Workers Paid** feature. The current setup uses one container instance for the personal Nexus brain. Cloudflare can build the Dockerfile through Workers Builds when this directory is used as the Worker root.

In Cloudflare Workers & Pages, create a **Worker** connected to this repository and set:

- Root directory: `brain`
- Production branch: `main`
- Deploy command: `npx wrangler deploy`

Set these Worker secrets:

- `OPENAI_API_KEY` — your model-provider API key.
- `NEXUS_MODEL` — the model name Nexus should use.
- `NEXUS_API_TOKEN` — a long random token shared with the Pages Function.

Do **not** commit those values to GitHub.

The Worker URL becomes the Pages project's `NEXUS_API_URL`, for example:

```
NEXUS_API_URL=https://nexus-personal-brain.<your-workers-subdomain>.workers.dev
```

The Pages project should use the same `NEXUS_API_TOKEN` value.

## Important

The brain uses local files for some current memory/task functionality. Container disk is ephemeral, so durable persistence should be moved to Cloudflare Durable Object SQLite, D1, R2, or another durable store before treating this as a permanent production memory backend.

The container is intentionally personal-only. No business/CRM/sales functionality is added here.
