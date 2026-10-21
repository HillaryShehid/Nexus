"""Docker-isolated execution for untrusted AI-generated code.

This module intentionally fails closed when Docker or the required image is absent.
It never falls back to executing untrusted code directly on the host.
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Any


class SecureCodeSandbox:
    def __init__(
        self,
        image: str = "python:3.11-slim",
        timeout_seconds: float = 3.0,
        memory_limit: str = "128m",
        cpu_limit: float = 1.0,
        pids_limit: int = 64,
    ) -> None:
        self.image = image
        self.timeout_seconds = max(0.5, min(float(timeout_seconds), 10.0))
        self.memory_limit = memory_limit
        self.cpu_limit = max(0.1, min(float(cpu_limit), 1.0))
        self.pids_limit = max(16, min(int(pids_limit), 128))

    @staticmethod
    def _decode_logs(logs: Any) -> str:
        if isinstance(logs, tuple):
            chunks = []
            for part in logs:
                if isinstance(part, bytes):
                    chunks.append(part.decode("utf-8", errors="replace"))
            return "".join(chunks)
        if isinstance(logs, bytes):
            return logs.decode("utf-8", errors="replace")
        return str(logs or "")

    def execute_untrusted_code(self, script_contents: str) -> dict[str, Any]:
        if not isinstance(script_contents, str) or not script_contents.strip():
            return {"success": False, "result": "", "error": "Sandbox Error: Code must be non-empty text."}
        if len(script_contents) > 3000:
            return {"success": False, "result": "", "error": "Sandbox Error: Code exceeds the configured size limit."}

        try:
            import docker
        except ImportError:
            return {
                "success": False,
                "result": "",
                "error": "Secure sandbox unavailable: install the optional Docker SDK and run Docker Desktop. Untrusted code was not executed.",
            }

        client = None
        container = None
        try:
            client = docker.from_env()
            try:
                client.images.get(self.image)
            except Exception:
                return {
                    "success": False,
                    "result": "",
                    "error": f"Secure sandbox image '{self.image}' is not available locally. Pull it before running code tests.",
                }

            with tempfile.TemporaryDirectory(prefix="nexus_sandbox_") as temp_dir:
                script_path = os.path.join(temp_dir, "payload.py")
                with open(script_path, "w", encoding="utf-8", newline="") as handle:
                    handle.write(script_contents)
                os.chmod(script_path, 0o444)

                container = client.containers.create(
                    image=self.image,
                    command=["python", "-I", "/workspace/payload.py"],
                    working_dir="/workspace",
                    detach=True,
                    stdin_open=False,
                    tty=False,
                    network_mode="none",
                    mem_limit=self.memory_limit,
                    nano_cpus=int(self.cpu_limit * 1_000_000_000),
                    pids_limit=self.pids_limit,
                    read_only=True,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"],
                    user="65534:65534",
                    tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
                    environment={},
                    volumes={temp_dir: {"bind": "/workspace", "mode": "ro"}},
                    labels={"app": "nexus", "purpose": "untrusted-code-test"},
                )
                container.start()
                deadline = time.monotonic() + self.timeout_seconds
                timed_out = False
                while time.monotonic() < deadline:
                    container.reload()
                    if container.status == "exited":
                        break
                    time.sleep(0.05)
                else:
                    timed_out = True
                    try:
                        container.kill()
                    except Exception:
                        pass
                    try:
                        container.wait(timeout=1)
                    except Exception:
                        pass

                logs = self._decode_logs(
                    container.logs(stdout=True, stderr=True, demux=True)
                )
                try:
                    exit_code = int(container.attrs.get("State", {}).get("ExitCode", -1))
                except (TypeError, ValueError, AttributeError):
                    exit_code = -1

                if timed_out:
                    return {
                        "success": False,
                        "result": "",
                        "error": f"Untrusted Runner Error: Execution exceeded {self.timeout_seconds:g} seconds and was terminated.",
                    }

                output = logs[:1000]
                payload = {
                    "status": "success" if exit_code == 0 else "failed",
                    "returncode": exit_code,
                    "stdout": output,
                    "stderr": "",
                }
                import json
                encoded = json.dumps(payload, ensure_ascii=False)
                if exit_code == 0:
                    return {"success": True, "result": encoded, "error": None}
                return {
                    "success": False,
                    "result": encoded,
                    "error": "Untrusted Runner Error: Isolated test process returned a failure code.",
                }
        except Exception:
            return {
                "success": False,
                "result": "",
                "error": "Secure sandbox error: isolated execution failed safely; no host execution fallback was attempted.",
            }
        finally:
            if container is not None:
                try:
                    container.reload()
                    if getattr(container, "status", "") != "exited":
                        container.kill()
                except Exception:
                    pass
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
