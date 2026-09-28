# Nexus on Cloudflare

Nexus now has a Cloudflare Python Worker entrypoint.

Cloudflare currently supports Python Workers through Pyodide. The Worker is the deployment/API layer; the existing Nexus brain remains in `src/brain/` and the local runtime remains available.

## Deploy

1. Install Node.js and uv.
2. From the repo root:
   `uv run pywrangler dev`
3. Set the model secret:
   `npx wrangler secret put OPENAI_API_KEY`
4. Set `NEXUS_MODEL` in `wrangler.toml` to the model you want to use.
5. Deploy:
   `uv run pywrangler deploy`

## API

POST `/` with:

{"message":"Hello Nexus"}

Health check:

GET `/health`

## Important

The current local tool runner uses filesystem and subprocess features that are not persistent/available in the same way inside Workers. Cloudflare's Python Worker filesystem is ephemeral, and threading/multiprocessing are unavailable. Durable Nexus memory/tasks should use Cloudflare KV, D1, Durable Objects, R2, or Queues as we migrate those subsystems.

This scaffold deliberately keeps the Cloudflare API safe instead of pretending every local tool works unchanged in Workers.
