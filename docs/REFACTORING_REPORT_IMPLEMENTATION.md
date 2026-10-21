# Refactoring report implementation notes

This branch implements the report items that can be changed safely in the repository without pretending to configure external accounts or deploy infrastructure.

## Implemented in this branch

- **Transactional task persistence:** `TaskManager` now stores task records in SQLite with WAL mode and transaction boundaries. It imports a valid existing `nexus_tasks.json` file on first startup and leaves that file in place as a migration backup. If the legacy file is invalid, startup fails with an explicit error rather than silently overwriting task history.
- **Bounded model context:** `SlidingContextManager` compiles recent conversation turns under an approximate token budget. It does not delete or truncate the stored conversation log. Token estimation is a heuristic; provider tokenizers remain authoritative.
- **Isolated code execution:** `code_tester` now runs only through a Docker sandbox with no network, read-only root filesystem and workspace mount, dropped Linux capabilities, no-new-privileges, non-root user, CPU/memory/PID bounds, and a timeout. If Docker or the image is unavailable, the tool fails closed instead of executing code directly on the host.
- **Bounded OmniRoute waits:** model requests use a configurable timeout (`NEXUS_MODEL_TIMEOUT_SECONDS`, default 25 seconds) and disable nested SDK retries. OmniRoute remains the only model gateway; Nexus does not silently switch to local inference.
- **Regression tests:** added tests for context budgeting, SQLite persistence/migration, and sandbox restrictions.

## Important limits

- These changes are proposed on a branch and are not live until the pull request is reviewed and merged.
- The test suite has not been run in the user's Windows environment, and a real Docker daemon / OmniRoute provider has not been tested from this editing environment.
- SQLite WAL is appropriate for a single host with a persistent local disk. It is **not** a shared database for multiple cloud instances or a substitute for per-user authorization and memory isolation.
- This branch does not create partner login, per-user private Nexus instances, shared business workspace permissions, a public web app, or a hosted deployment. Those require a reviewed authentication/session design, a cloud database, secure secrets, and deployment choices.
- No Ollama/local model fallback was added because the project requirement is cloud-hosted inference without relying on the user's laptop.

## Local verification steps

From the repository root, after merging the branch:

1. Install Python 3.11+ and Docker Desktop for Windows. Start Docker Desktop.
2. Install project dependencies and the optional sandbox dependency:
   ```bash
   python -m pip install -e ".[dev,sandbox]"
   ```
3. Pull the sandbox image once:
   ```bash
   docker pull python:3.11-slim
   ```
4. Run tests:
   ```bash
   pytest -q
   ```
5. Start OmniRoute separately, connect at least one provider in its dashboard, then run:
   ```bash
   python scripts/check_omniroute.py
   python run.py
   ```

Do not commit `.env` or provider/API keys. The local default `http://127.0.0.1:20128/v1` only works when Nexus and OmniRoute are reachable on the same machine/network namespace.
