# NexusCore Cloud Deployment Roadmap

Status: planning document only. This does not deploy services or change the `main` branch.

## Goal

Make NexusCore accessible from phone, laptop, and teammates' devices while the owner's PC is completely off. Keep one Nexus intelligence/core with role-specific capabilities, shared business knowledge where authorized, and private per-person conversations and memories.

## What the repository currently tells us

- `run.py` launches a terminal input loop; it is not a browser application or web API.
- `src/core.py` wires together the brain, tools, permissions, events, tasks, and autonomy engine.
- `src/model.py` calls OmniRoute through an OpenAI-compatible endpoint.
- `.env.example` currently points OmniRoute at `http://127.0.0.1:20128/v1`. That address only works when OmniRoute is running on the same machine/network namespace as the backend. A cloud deployment needs a reachable, private, authenticated endpoint.
- `src/storage.py` defines storage interfaces and explicitly leaves durable cloud implementations to be added.
- `src/access.py` currently has an owner-centric authorization setup. It is not yet a complete five-person account and isolation system.
- `src/voice_livekit.py` has local-service defaults for some speech components; cloud voice needs deliberate provider configuration and secure secret handling.

## Deployment design

```text
Phone / laptop / teammate browser
              |
        HTTPS web app
              |
    Authenticated Python API
       |       |        |
  NexusCore  Cloud DB  Job worker / scheduler
       |
 Private OmniRoute endpoint
       |
 Remote model providers
```

The browser must never receive model-provider keys, database service credentials, or privileged backend secrets. No always-on component may depend on the owner's PC.

## Implementation phases

### 1. Make the core safe to host
- Add configuration validation and a startup/health endpoint.
- Replace implicit single-owner identity assumptions with an authenticated actor context passed through each request and task.
- Add tests for permission boundaries, user isolation, and event/task behavior.
- Keep privileged actions (spending, permission changes, foundation/self-modification, high-impact actions) owner-gated.

### 2. Add durable cloud persistence
- Implement a production database-backed store for conversations, private memories, tasks, events, world state, notifications, and approvals.
- Separate records by user/tenant and enforce access in the backend, not just the interface.
- Define which business records are shared with the team and which personal records remain private.
- Add migrations, backups, retention/deletion behavior, and tests. Do not use local files as the source of truth in production.

### 3. Add secure web API and accounts
- Build an HTTPS API around NexusCore; preserve the current CLI as a development tool.
- Add secure sign-in, session/token handling, rate limits, input validation, audit logs, and account recovery.
- Create distinct accounts for Hilal, Hamza, Talha, Zachariah, and Mustafa, with role-specific permissions:
  - Hilal: owner/admin and sensitive approvals.
  - Hamza: website/technical work, not calling.
  - Talha: calling and building.
  - Zachariah and Mustafa: calling/workers.
- Treat these roles as authorization rules enforced server-side, not labels in the UI.

### 4. Connect OmniRoute remotely
- Choose a hosted/private OmniRoute deployment or another reachable secured endpoint.
- Configure the backend with the endpoint and secret through the hosting provider's secret manager.
- Remove localhost assumptions from production configuration; keep localhost only for local development.
- Add a connection/health check, timeouts, error handling, and usage limits. Never commit real API keys.

### 5. Deploy the backend and scheduled work
- Deploy the API, durable database, and background worker/scheduler to cloud services.
- Use event-triggered work for important changes and a scheduled reconciliation loop for missed or pending work.
- Ensure jobs resume safely after restarts and cannot run twice in unsafe ways.
- Verify the app continues operating while the owner's computer is powered off.

### 6. Build the NexusCore interface
- Add responsive sign-in and workspace UI for phone and desktop.
- Add the planned navigation: Home, Businesses, Calls, Finder Queue, Partners, Websites, Payments, Team, Leaderboard, Messages, Team Chat, Nexus, Settings, and Help.
- Build the animated Nexus neural-core presence as a UI component, with accessible reduced-motion behavior and clear microphone/privacy states.
- Keep team chat/shared business workspace separate from private personal Nexus conversations.

### 7. Add voice and business integrations safely
- Configure hosted speech-to-text and text-to-speech rather than assuming local Ollama/Kokoro/Deepgram services exist.
- Add visible recording/listening indicators, directed-speech behavior, opt-in permissions, and private AirPods mode.
- Add business integrations incrementally, each with scoped credentials, logs, failure handling, and approval gates for consequential actions.
- Keep website deployment behind Hilal's preview approval as specified in the master vision.

### 8. Staging, verification, and release
- Deploy to a staging environment first; do not change production or merge directly to `main` as part of planning.
- Test mobile and desktop sign-in, all five roles, private-memory isolation, shared-business permissions, OmniRoute access, restart recovery, background jobs, and voice privacy.
- Run security checks and automated tests; fix failures before release.
- Document rollback, backups, account offboarding, and credential rotation.

## Release acceptance checklist

- [ ] Works from a phone when the owner's PC is off.
- [ ] Team members sign in individually.
- [ ] Personal conversations and memories cannot be read by other team members or by shared business workflows unless explicitly authorized.
- [ ] Shared business records are available only to permitted roles.
- [ ] Backend secrets never appear in browser code or Git history.
- [ ] OmniRoute is reachable securely from the hosted backend and no production path relies on localhost.
- [ ] Tasks, events, approvals, and scheduled checks survive backend restarts.
- [ ] High-impact actions remain approval-gated and audited.
- [ ] Staging checks pass before any production release.

## Immediate next engineering milestone

Implement the authenticated API and persistent storage foundation in a separate feature branch, with tests for actor-scoped access. Do not start with the animated UI: a polished interface must not mask missing account isolation or ephemeral data. Select specific hosting providers only after checking current free-tier limits, data persistence, sleep behavior, and whether private backend networking is supported.
