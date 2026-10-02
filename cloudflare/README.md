# Nexus Cloudflare Worker

The Worker currently provides a small, stateless chat API. It is a deployment scaffold and does not yet route through the full local `NexusBrain`, its tools, or its memory/task systems.

## Configure

1. Install Node.js and `uv`.
2. From the repository root, set a random API token with at least 32 characters:
   `npx wrangler secret put NEXUS_API_TOKEN`
3. Set `OPENAI_API_KEY` as a Worker secret:
   `npx wrangler secret put OPENAI_API_KEY`
4. Set `NEXUS_MODEL` in `wrangler.jsonc`.
5. If a browser client will call the Worker, set `NEXUS_ALLOWED_ORIGINS` to a comma-separated list of exact origins, such as `https://app.example.com`. Leave it empty when there is no browser client. Origins with paths, wildcards, or credentials are rejected.

The `NEXUS_API_TOKEN` secret is required for every POST request. The Worker fails closed if the secret is missing or shorter than 32 characters. Send it in the `Authorization: Bearer <token>` header. Do not put it in browser source code; a browser app needs a trusted backend that can keep secrets private.

## Run and deploy

From the repository root:

```bash
uv run pywrangler dev
uv run pywrangler deploy
```

## API

Authenticated POST `/`:

```http
Authorization: Bearer <NEXUS_API_TOKEN>
Content-Type: application/json
```

```json
{"message":"Hello Nexus"}
```

GET `/health` is public and reports service health. The Worker does not persist messages or conversation state.

## Runtime boundary

The local tool runner uses filesystem and subprocess features that are not available in the same way inside Workers. Worker filesystems are ephemeral, and threading/multiprocessing are unavailable. Durable Nexus memory/tasks need Cloudflare KV, D1, Durable Objects, R2, or Queues as those subsystems are migrated.
