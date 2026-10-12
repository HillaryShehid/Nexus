# Connect NexusCore to OmniRoute

Nexus already uses the OpenAI-compatible OmniRoute gateway through `src/model.py`.
This guide verifies the real connection instead of assuming the configuration works.

## 1. Start OmniRoute

Start the OmniRoute service on the machine/network where Nexus can reach it, then
connect and enable the provider accounts/models you want OmniRoute to route to.
The exact dashboard and provider setup depends on your OmniRoute installation.

## 2. Configure Nexus

Copy `.env.example` to `.env` in the repository root, then set the values for
your OmniRoute instance:

```dotenv
NEXUS_MODEL_MODE=free
NEXUS_PROVIDER_ORDER=omniroute
NEXUS_OMNIROUTE_MODEL=auto
OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
OMNIROUTE_API_KEY=sk_omniroute
```

Use the actual API key expected by your OmniRoute instance. The values above are
local-development defaults/placeholders, not proof that a service is running.
Keep `.env` private and never commit real keys to GitHub.

If you use a different host or port, replace the base URL. Keep the OpenAI-compatible
API prefix (usually `/v1`) if your OmniRoute installation uses it.

**Important for hosted Nexus:** `127.0.0.1` means the same machine/container as the
Nexus backend, not your laptop. If Nexus is deployed to a cloud host, give it an
OmniRoute endpoint reachable from that backend, or run the gateway alongside the
backend. Do not expose an unauthenticated gateway to the public internet.

## 3. Install dependencies and run the connection check

From the repository root, with Python 3.11 or newer:

```bash
python -m pip install -e .
python scripts/check_omniroute.py
```

The script makes one small real chat request using `NEXUS_OMNIROUTE_MODEL` (default
`auto`). A `PASS` confirms the endpoint answered that request. A `FAIL` means the
connection or selected route still needs attention; check that the service is running,
the URL/key are correct, and at least one route is enabled.

## 4. Run Nexus

```bash
python run.py
```

Send a simple message. If the connection check passes but Nexus itself errors, inspect
the terminal output and `nexus_system.log`; the gateway check isolates connectivity
from the rest of Nexus's reasoning/tool pipeline.

## Current boundary

This connects and verifies the **Python NexusCore process** to OmniRoute. It does not
by itself create a public hosted chat API, website login, database-backed multi-user
memory, or secure remote access. Those are separate deployment tasks.
