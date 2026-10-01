import ast
import http.client
import re
import ssl
import ipaddress
import json
import logging
import math
import operator
import os
import signal
import socket
import subprocess
import sys
import tempfile
from urllib.parse import urljoin, urlsplit

from src.registry import SHARED_REGISTRY, WORKSPACE_DIR

logger = logging.getLogger("nexus.tools")
MAX_PAGE_BYTES = 1 * 1024 * 1024
MAX_PAGE_TEXT = 3500
MAX_SEARCH_OUTPUT = 5000
MAX_RUNNER_OUTPUT = 1000


class ToolSystem:
    def __init__(self):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.workspace_root = os.path.realpath(WORKSPACE_DIR)
        self.memory_file = os.path.abspath(os.path.join(self.workspace_root, "nexus_memory.json"))
        self.allowed_operators = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
        self.allowed_nodes = (ast.Expression, ast.Constant, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)
        self.dispatch_table = {"web_search": self.tool_web_search, "read_page": self.tool_read_page, "calculator": self.tool_calculator, "file_system": self.tool_file_system, "memory_store": self.tool_memory_store, "code_tester": self.tool_code_tester}

    def _validate_args(self, tool_name, args):
        spec = SHARED_REGISTRY.get(tool_name)
        if spec is None: return False, "Tool is not registered."
        if not isinstance(args, dict): return False, "Tool arguments must be a dictionary."
        for required in spec["required_args"]:
            if required not in args: return False, f"Missing required argument: {required}."
            if isinstance(args[required], str) and not args[required].strip(): return False, f"Required argument '{required}' cannot be empty."
        for key, value in args.items():
            if key not in spec["types"]: return False, f"Unknown argument: {key}."
            if not isinstance(value, spec["types"][key]): return False, f"Invalid type for argument: {key}."
            limit = spec["limits"].get(key)
            if isinstance(limit, int) and len(value) > limit: return False, f"Argument '{key}' exceeds its size limit."
        action_limit = spec["limits"].get("action")
        if action_limit is not None and "action" in args and args["action"] not in action_limit: return False, "Requested action is not permitted."
        return True, None

    def execute(self, tool_name, args):
        if tool_name not in self.dispatch_table: return {"success": False, "result": "", "error": "Tool is not registered."}
        valid, error = self._validate_args(tool_name, args)
        if not valid: return {"success": False, "result": "", "error": f"Schema Error: {error}"}
        try:
            result = self.dispatch_table[tool_name](**args)
            return result if isinstance(result, dict) else {"success": False, "result": "", "error": "Internal Tool Error: Invalid response structure."}
        except Exception:
            logger.exception("Unhandled tool crash within %s", tool_name)
            return {"success": False, "result": "", "error": "Internal Tool Error: Tool execution failed safely."}

    def _is_safe_ip(self, ip_str):
        try:
            ip = ipaddress.ip_address(ip_str)
            return not (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved)
        except ValueError: return False

    def _resolve_and_validate_url(self, url):
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"}: return {"valid": False, "error": "Security Error: Only HTTP and HTTPS are permitted.", "ip": None}
            if parsed.username is not None or parsed.password is not None: return {"valid": False, "error": "Security Block: URL credentials are forbidden.", "ip": None}
            hostname = parsed.hostname
            if not hostname: return {"valid": False, "error": "Network Error: URL has no valid hostname.", "ip": None}
            try: port = parsed.port
            except ValueError: return {"valid": False, "error": "Network Error: URL port is invalid.", "ip": None}
            port = port or (443 if parsed.scheme == "https" else 80)
            if not 1 <= port <= 65535: return {"valid": False, "error": "Network Error: URL port is outside valid bounds.", "ip": None}
            if hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"): return {"valid": False, "error": "Security Block: Localhost targeting is forbidden.", "ip": None}
            try:
                direct = ipaddress.ip_address(hostname)
                if not self._is_safe_ip(str(direct)): return {"valid": False, "error": "Security Block: Internal network targeting is forbidden.", "ip": None}
                return {"valid": True, "error": None, "ip": str(direct)}
            except ValueError: pass
            infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            addresses = []
            for item in infos:
                resolved_ip = item[4][0]
                if not self._is_safe_ip(resolved_ip): return {"valid": False, "error": "Security Block: Forbidden internal network targeting.", "ip": None}
                if resolved_ip not in addresses: addresses.append(resolved_ip)
            return {"valid": bool(addresses), "error": None if addresses else "Network Error: Host did not resolve.", "ip": addresses[0] if addresses else None}
        except socket.gaierror: return {"valid": False, "error": "Network Error: Host resolution failed.", "ip": None}
        except Exception:
            logger.exception("DNS validation failure.")
            return {"valid": False, "error": "Network Error: URL validation failed.", "ip": None}

    def tool_web_search(self, query):
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                # Keep existing installations usable until they install the renamed package.
                from duckduckgo_search import DDGS
            with DDGS() as ddgs: results = list(ddgs.text(query, max_results=3, backend="auto"))
            cleaned = []
            for item in results:
                if isinstance(item, dict) and all(isinstance(item.get(k), str) for k in ("title", "href", "body")) and item["title"].strip() and item["href"].strip():
                    cleaned.append({"title": item["title"][:250], "url": item["href"][:500], "snippet": item["body"][:650]})
            if not cleaned:
                logger.warning("Search provider returned no usable results for query.")
                return {"success": False, "result": "", "error": "Search Provider Error: No search results were returned."}
            payload = {"query": query, "results": cleaned[:3]}
            encoded = json.dumps(payload, ensure_ascii=False)
            while len(encoded) > MAX_SEARCH_OUTPUT and payload["results"]:
                payload["results"].pop()
                encoded = json.dumps(payload, ensure_ascii=False)
            return {"success": True, "result": encoded, "error": None}
        except Exception:
            logger.exception("Search provider failure.")
            return {"success": False, "result": "", "error": "Search Provider Error: Unable to complete operation."}

    def _fetch_page(self, url, validated_ip):
        parsed = urlsplit(url); hostname = parsed.hostname
        if not hostname: raise ValueError("invalid hostname")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            sock = socket.create_connection((validated_ip, port), timeout=4)
            try: tls_sock = context.wrap_socket(sock, server_hostname=hostname)
            except Exception: sock.close(); raise
            conn = http.client.HTTPSConnection(hostname, port=port, timeout=4, context=context); conn.sock = tls_sock
        else:
            conn = http.client.HTTPConnection(hostname, port=port, timeout=4); conn.sock = socket.create_connection((validated_ip, port), timeout=4)
        target = parsed.path or "/"
        if parsed.query: target += "?" + parsed.query
        host_header = hostname
        if ":" in hostname and not hostname.startswith("["): host_header = f"[{hostname}]"
        default_port = 443 if parsed.scheme == "https" else 80
        if port != default_port: host_header = f"{host_header}:{port}"
        try:
            conn.request("GET", target, headers={"User-Agent": "Nexus/1.4.1", "Host": host_header, "Accept-Encoding": "identity", "Connection": "close"})
            response = conn.getresponse(); headers = {k: v for k, v in response.getheaders()}
            if headers.get("Content-Length"):
                try:
                    if int(headers["Content-Length"]) > MAX_PAGE_BYTES: raise ValueError("payload too large")
                except ValueError as exc:
                    if str(exc) == "payload too large": raise
            if headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}: raise ValueError("compressed responses are not accepted")
            body = response.read(MAX_PAGE_BYTES + 1)
            if len(body) > MAX_PAGE_BYTES: raise ValueError("payload too large")
            return response.status, headers, body
        finally: conn.close()

    def tool_read_page(self, url):
        visited = set(); current_url = url
        for _ in range(5):
            if current_url in visited: return {"success": False, "result": "", "error": "Network Error: Cyclic redirection intercepted."}
            visited.add(current_url); check = self._resolve_and_validate_url(current_url)
            if not check["valid"]: return {"success": False, "result": "", "error": check["error"]}
            try:
                status, headers, raw = self._fetch_page(current_url, check["ip"])
                if status in {301,302,303,307,308}:
                    location = headers.get("Location", "")
                    if not location or len(location) > 200: return {"success": False, "result": "", "error": "Network Error: Invalid redirect destination."}
                    current_url = urljoin(current_url, location); continue
                if status < 200 or status >= 300: return {"success": False, "result": "", "error": "Network Error: Server returned a non-success response."}
                html = raw.decode("utf-8", errors="ignore")
                html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I|re.S)
                html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.I|re.S)
                text = re.sub(r"<[^>]+>", " ", html)
                body = "\n".join(line.strip() for line in text.splitlines() if line.strip())[:MAX_PAGE_TEXT]
                return {"success": True, "result": json.dumps({"origin": current_url, "resolved_ip": check["ip"], "body": body}, ensure_ascii=False), "error": None}
            except (TimeoutError, socket.timeout): return {"success": False, "result": "", "error": "Network Error: Request timed out."}
            except ValueError as exc:
                if str(exc) in {"payload too large", "compressed responses are not accepted"}: return {"success": False, "result": "", "error": "Data Limit Error: Response violates safe retrieval limits."}
                return {"success": False, "result": "", "error": "Network Error: Invalid response payload."}
            except Exception:
                logger.exception("HTTP request failure.")
                return {"success": False, "result": "", "error": "Network Error: Failed to retrieve page safely."}
        return {"success": False, "result": "", "error": "Network Error: Maximum redirect limit exceeded."}

    def tool_calculator(self, expression):
        try:
            tree = ast.parse(expression, mode="eval"); nodes = list(ast.walk(tree))
            if len(nodes) > 100: return {"success": False, "result": "", "error": "Security Block: Expression complexity exceeds limits."}
            if any(not isinstance(node, self.allowed_nodes) for node in nodes): return {"success": False, "result": "", "error": "Security Block: Forbidden expression operation."}
            result = self._eval_ast(tree.body)
            if not isinstance(result, (int,float)) or isinstance(result, bool): return {"success": False, "result": "", "error": "Math Error: Invalid numeric result."}
            if not math.isfinite(float(result)) or abs(result) > 1_000_000_000: return {"success": False, "result": "", "error": "Arithmetic Error: Result exceeds safe limits."}
            return {"success": True, "result": str(result), "error": None}
        except ZeroDivisionError: return {"success": False, "result": "", "error": "Arithmetic Error: Division by zero encountered."}
        except (SyntaxError, TypeError): return {"success": False, "result": "", "error": "Math Error: Invalid expression syntax."}
        except ValueError as exc: return {"success": False, "result": "", "error": f"Math Boundary Fault: {str(exc)[:200]}"}
        except Exception:
            logger.exception("Calculator failure.")
            return {"success": False, "result": "", "error": "Internal Math Error: Calculation failed safely."}

    def _eval_ast(self, node, depth=0):
        if depth > 30: raise ValueError("Expression nesting depth exceeds limits.")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int,float)): raise ValueError("Only numeric constants are permitted.")
            if abs(node.value) > 1_000_000: raise ValueError("Numeric literal magnitude exceeds limits.")
            return node.value
        if isinstance(node, ast.UnaryOp):
            fn = self.allowed_operators.get(type(node.op))
            if fn is None: raise ValueError("Unary operator is not permitted.")
            value = fn(self._eval_ast(node.operand, depth+1))
            if not math.isfinite(float(value)) or abs(value) > 1_000_000_000: raise ValueError("Unary operation exceeded numerical limits.")
            return value
        if isinstance(node, ast.BinOp):
            left, right = self._eval_ast(node.left, depth+1), self._eval_ast(node.right, depth+1)
            if isinstance(node.op, ast.Pow) and (right > 10 or right < -10 or abs(left) > 1000): raise ValueError("Security Block: Power calculation boundaries exceeded.")
            fn = self.allowed_operators.get(type(node.op))
            if fn is None: raise ValueError("Binary operator is not permitted.")
            result = fn(left, right)
            if not math.isfinite(float(result)) or abs(result) > 1_000_000_000: raise ValueError("Intermediate numerical execution result overflow.")
            return result
        raise ValueError("Unsupported expression structure.")

    def _safe_workspace_path(self, path):
        if not isinstance(path, str) or not path or "\x00" in path or os.path.isabs(path): return None
        candidate = os.path.realpath(os.path.join(self.workspace_root, path))
        try:
            if os.path.commonpath([self.workspace_root, candidate]) != self.workspace_root: return None
        except ValueError: return None
        current = self.workspace_root
        for component in os.path.relpath(candidate, self.workspace_root).split(os.sep):
            current = os.path.join(current, component)
            if os.path.lexists(current) and os.path.islink(current): return None
        return candidate

    def tool_file_system(self, action, path, content=""):
        target = self._safe_workspace_path(path)
        if target is None: return {"success": False, "result": "", "error": "Security Block: Path escapes or links outside the Nexus workspace."}
        try:
            if action == "write":
                parent = os.path.dirname(target); os.makedirs(parent, exist_ok=True)
                if os.path.lexists(target) and os.path.islink(target): return {"success": False, "result": "", "error": "Security Block: Symlink target refused."}
                fd, temp_name = tempfile.mkstemp(dir=parent, prefix=".nexus_write_", suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(content); handle.flush(); os.fsync(handle.fileno())
                    os.replace(temp_name, target)
                except Exception:
                    try: os.unlink(temp_name)
                    except OSError: pass
                    raise
                return {"success": True, "result": f"File written successfully: {path}", "error": None}
            if action == "read":
                if not os.path.isfile(target) or os.path.islink(target): return {"success": False, "result": "", "error": "Storage Error: File does not exist."}
                fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "r", encoding="utf-8") as handle: data = handle.read(3500)
                return {"success": True, "result": data, "error": None}
            return {"success": False, "result": "", "error": "File Error: Unsupported action."}
        except (OSError, UnicodeError):
            logger.exception("Filesystem operation failure.")
            return {"success": False, "result": "", "error": "Storage Error: Filesystem operation failed."}

    def _load_memory(self):
        if not os.path.exists(self.memory_file) or os.path.islink(self.memory_file): return {"conversations": [], "facts": {}}
        try:
            with open(self.memory_file, "r", encoding="utf-8") as handle: loaded = json.load(handle)
            if isinstance(loaded, dict) and isinstance(loaded.get("conversations"), list) and isinstance(loaded.get("facts"), dict): return loaded
        except (OSError, UnicodeError, json.JSONDecodeError): logger.warning("Memory file could not be read; resetting in-memory state.")
        return {"conversations": [], "facts": {}}

    def _save_memory(self, data):
        parent = os.path.dirname(self.memory_file); os.makedirs(parent, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=parent, prefix=".nexus_memory_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle: json.dump(data, handle, indent=2, ensure_ascii=False); handle.flush(); os.fsync(handle.fileno())
            os.replace(temp_name, self.memory_file)
        except Exception:
            try: os.unlink(temp_name)
            except OSError: pass
            raise

    def tool_memory_store(self, action, key, value=""):
        data = self._load_memory()
        if action == "read":
            if key == "chat_context": return {"success": True, "result": json.dumps(data["conversations"][-10:]), "error": None}
            return {"success": True, "result": str(data["facts"].get(key, "No matching memory record found."))[:1500], "error": None}
        if key == "chat_context": data["conversations"] = (data["conversations"] + [value])[-10:]
        else:
            if len(data["facts"]) >= 30 and key not in data["facts"]: return {"success": False, "result": "", "error": "Storage Overflow Error: Memory limit reached."}
            data["facts"][key] = value
        try:
            self._save_memory(data); return {"success": True, "result": "Memory entry stored successfully.", "error": None}
        except OSError:
            logger.exception("Memory persistence failure.")
            return {"success": False, "result": "", "error": "Memory Error: Unable to persist memory."}

    def _terminate_process(self, process):
        if process.poll() is not None: return
        try:
            if os.name == "nt": subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            else: os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            try: process.kill()
            except OSError: pass

    def tool_code_tester(self, python_code):
        with tempfile.TemporaryDirectory(prefix="nexus_runner_") as tmpdir:
            code_path = os.path.join(tmpdir, "sandbox.py")
            try:
                with open(code_path, "w", encoding="utf-8") as handle: handle.write(python_code)
                process = subprocess.Popen([sys.executable, "-I", code_path], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={}, cwd=tmpdir, text=True, start_new_session=(os.name != "nt"), creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                try: stdout, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    self._terminate_process(process); process.communicate(timeout=1)
                    return {"success": False, "result": "", "error": "Untrusted Runner Error: Execution exceeded 3 seconds."}
                stdout, stderr = (stdout or "")[:MAX_RUNNER_OUTPUT], (stderr or "")[:MAX_RUNNER_OUTPUT]
                payload = {"status": "success" if process.returncode == 0 else "failed", "returncode": process.returncode, "stdout": stdout, "stderr": stderr}
                if process.returncode == 0: return {"success": True, "result": json.dumps(payload), "error": None}
                return {"success": False, "result": json.dumps(payload), "error": "Untrusted Runner Error: Test process returned a failure code."}
            except (OSError, subprocess.SubprocessError):
                logger.exception("Untrusted runner failure.")
                return {"success": False, "result": "", "error": "Untrusted Runner Error: Unable to execute test process."}
