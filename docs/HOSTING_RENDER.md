# Deploy the first Nexus API (Render free tier)

This creates a **single-owner API smoke-test deployment**, not the complete NexusCore web app. Partner accounts, durable hosted database storage, private per-user memory, and a browser UI are not implemented by this deployment step.

## 1. Before deploying

1. Push/merge the API changes to the repository's `main` branch.
2. Make sure OmniRoute has at least one provider connected and can answer requests.
3. The OmniRoute endpoint must be reachable from the internet-facing Render service over HTTPS or a private network. A laptop-only URL such as `http://127.0.0.1:20128/v1` will **not** work from Render. Do not expose an unauthenticated OmniRoute gateway publicly.

## 2. Create the Render service

1. Sign in to Render and choose **New → Blueprint**.
2. Connect `HillaryShehid/Nexus` and select the branch containing this file.
3. Review the service named `nexus-api` and deploy the blueprint.
4. When prompted for secret values, set:
   - `NEXUS_API_TOKEN`: a random secret at least 32 characters long. Generate one with a password manager; keep it private.
   - `OMNIROUTE_BASE_URL`: the reachable OmniRoute OpenAI-compatible base URL ending in `/v1`.
   - `OMNIROUTE_API_KEY`: the OmniRoute gateway key, not an upstream provider's secret.
5. Wait for the deploy to finish and open the Render service URL. `/health` should return `{"status":"ok","service":"nexus-api"}`.

## 3. Send a test chat

Use a local terminal, replacing the URL and token with your own values:

```bash
curl -X POST "https://YOUR-RENDER-SERVICE.onrender.com/v1/chat" \
  -H "Authorization: Bearer YOUR_NEXUS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Reply with: Nexus is connected."}'
```

A successful response contains a JSON `response` field. A first request may take a while because free Render services can spin down while idle.

## Important limits

- The API requires a bearer token; keep it out of frontend JavaScript and never commit it to GitHub.
- This is one owner token and one owner identity (`hilal`) only. Do not share it with partners.
- Free service local disk is ephemeral and the service may sleep. Do not rely on its local SQLite/JSON files for durable memory or business data.
- This API is not yet the full NexusCore website. The frontend, real user login, role permissions, per-person private memory, durable database, and secure provider network path remain future steps.
- The API health check confirms the process is alive; it does not prove OmniRoute can reach a model. The authenticated chat test is the end-to-end check.
