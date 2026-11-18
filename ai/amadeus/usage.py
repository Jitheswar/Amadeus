"""Display-only subscription limits, read from each provider's own native source.

Queried on demand and cached for a minute. Tokens remain inside the collector;
only bounded quota records reach the shell. No timer, credential refresh or model call.
"""
import concurrent.futures, json, math, os, select, shutil, subprocess, time, urllib.request
from pathlib import Path
from . import config, audit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_json(path):
    try:
        if path.stat().st_size > 1_048_576:
            return {}
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def fraction(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return max(0.0, min(1.0, number)) if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def request(url, token, body=None, extra=None):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json", **(extra or {})}
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urllib.request.build_opener(NoRedirect).open(req, timeout=8) as response:
        data = response.read(1_048_577)
    if len(data) > 1_048_576:
        raise ValueError("oversized usage response")
    return json.loads(data)


def claude():
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    auth = read_json(home / ".credentials.json").get("claudeAiOauth") or {}
    token = auth.get("accessToken")
    if not token:
        return [], "Sign in with Claude Code", ""
    data = request("https://api.anthropic.com/api/oauth/usage", token, extra={"anthropic-beta": "oauth-2025-04-20"})
    windows = []
    for key, title in (("five_hour", "Session"), ("seven_day", "Weekly")):
        bucket = data.get(key) or {}
        value = bucket.get("utilization")
        percent = fraction(float(value) / 100) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        if percent is not None:
            windows.append({"label": title, "used": percent, "resets": str(bucket.get("resets_at") or "")[:80]})
    return windows, "Current limits" if windows else "No usage limits returned", str(auth.get("subscriptionType") or "")[:60]


def codex(command):
    # Ask the official app-server; never scrape or print an OAuth token.
    if not shutil.which(command):
        return [], "Install Codex from Harness", ""
    path = Path(shutil.which(command))
    if path.is_symlink() and path.resolve().name == "mise":
        result = subprocess.run(["mise", "which", "codex"], env=dict(os.environ, MISE_OFFLINE="1"), capture_output=True, text=True, timeout=5)
        if result.returncode:
            return [], "Install Codex from Harness", ""
        command = result.stdout.strip()
    process = subprocess.Popen([command, "-s", "read-only", "-a", "on-request", "app-server"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    buffer = b""
    def rpc(ident, method, params):
        nonlocal buffer
        process.stdin.write((json.dumps({"id": ident, "method": method, "params": params}) + "\n").encode())
        process.stdin.flush()
        end = time.monotonic() + 8
        while time.monotonic() < end:
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                message = json.loads(line)
                if message.get("id") == ident:
                    if message.get("error"):
                        raise ValueError("sign-in or limits unavailable")
                    return message.get("result") or {}
            if not select.select([process.stdout], [], [], max(0, end - time.monotonic()))[0]:
                break
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > 1_048_576:
                raise ValueError("oversized app-server message")
        raise TimeoutError("Codex limits timed out")
    try:
        rpc(1, "initialize", {"clientInfo": {"name": "amadeus-usage", "version": "1"}})
        process.stdin.write(b'{"method":"initialized","params":{}}\n'); process.stdin.flush()
        data = rpc(2, "account/rateLimits/read", {})
        buckets = data.get("rateLimitsByLimitId") or {"codex": data.get("rateLimits") or {}}
        windows, plan = [], ""
        for name, bucket in list(buckets.items())[:6]:
            if not isinstance(bucket, dict):
                continue
            plan = plan or str(bucket.get("planType") or "")[:60]
            for key, label in (("primary", "Session"), ("secondary", "Weekly")):
                window = bucket.get(key) or {}
                raw = window.get("usedPercent")
                used = fraction(float(raw) / 100) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
                if used is not None:
                    windows.append({"label": label if name == "codex" else str(name)[:50] + " " + label,
                                    "used": used, "resets": str(window.get("resetsAt") or "")[:80]})
        return windows, "Current limits" if windows else "No subscription limits returned", plan
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        process.stdin.close(); process.stdout.close()


def quota_used(bucket):
    if bucket.get("disabled") is True:
        return None
    remaining = bucket.get("remainingFraction", bucket.get("remaining_fraction"))
    amount = bucket.get("remainingAmount", bucket.get("remaining_amount"))
    if remaining is None and amount is not None:
        return 1.0 if amount in (0, "0") and not isinstance(amount, bool) else None
    # Proto3 omits a zero remainder. A reset time still identifies an exhausted window.
    if remaining is None and (bucket.get("resetTime") or bucket.get("reset_time")):
        return 1.0
    value = fraction(remaining)
    return 1 - value if value is not None else None


def antigravity():
    home = Path(os.environ.get("AGY_DIR", str(Path.home() / ".gemini/antigravity-cli")))
    auth = {}
    if shutil.which("secret-tool"):
        result = subprocess.run(["secret-tool", "lookup", "service", "gemini", "username", "antigravity"],
                                capture_output=True, text=True, timeout=3)
        try:
            auth = json.loads(result.stdout) if result.stdout.strip() else {}
        except ValueError:
            pass
    auth = auth if isinstance(auth, dict) and auth else read_json(home / "antigravity-oauth-token")
    token = (auth.get("token") or {}).get("access_token") or auth.get("access_token")
    if not token:
        return [], "Sign in with Antigravity", ""
    base = "https://daily-cloudcode-pa.googleapis.com/v1internal:"
    assist = request(base + "loadCodeAssist", token, {}, {"User-Agent": "antigravity"})
    project = assist.get("cloudaicompanionProject")
    project = project.get("id") if isinstance(project, dict) else project
    data = request(base + "retrieveUserQuotaSummary", token, {"project": project} if project else {}, {"User-Agent": "antigravity"})
    groups = data.get("groups") or [{"displayName": "Gemini", "buckets": data.get("buckets", [])}]
    windows = []
    for group in groups[:6]:
        for bucket in group.get("buckets", [])[:4]:
            used = quota_used(bucket)
            if used is not None:
                windows.append({"label": (str(group.get("displayName", "")) + " " + str(bucket.get("window") or bucket.get("displayName") or "Limit"))[:80],
                                "used": used, "resets": str(bucket.get("resetTime") or bucket.get("reset_time") or "")[:80]})
    tier = assist.get("currentTier") or {}
    return windows, "Current limits" if windows else "No quota windows returned", str(tier.get("name") or tier.get("id") or "")[:60]


def collect(cfg, force=False):
    cache = config.STATE / "usage.json"
    saved = read_json(cache)
    checked = saved.get("checked")
    if not force and isinstance(checked, (float, int)) and isinstance(saved.get("providers"), list) and 0 <= time.time() - checked < 60:
        saved["default"] = cfg["ai"]["provider"]
        return saved
    infos = config.provider_info()
    old_records = saved.get("providers")
    previous = {x["name"]: x for x in old_records if isinstance(x, dict) and isinstance(x.get("name"), str)} if isinstance(old_records, list) else {}
    def one(info):
        item = {"name": info["name"], "label": info["label"], "kind": info["kind"], "limits": [], "plan": "", "status": "API usage is billed by its provider"}
        try:
            if info["type"] == "claude-cli":
                item["limits"], item["status"], item["plan"] = claude()
            elif info["type"] == "codex-cli":
                item["limits"], item["status"], item["plan"] = codex(info["command"])
            elif info["type"] == "antigravity-cli":
                item["limits"], item["status"], item["plan"] = antigravity()
            if info["kind"] == "Local":
                item["status"] = "Local model; no subscription quota"
        except Exception:
            item = dict(previous.get(info["name"], item), status="Usage unavailable; check sign-in or refresh later")
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(one, infos["providers"]))
    requests = sum(r.get("kind") == "request" for r in audit.read(1000))
    result = {"default": infos["default"], "providers": records, "checked": time.time(), "recentRequests": requests}
    config._atomic_config(cache, json.dumps(result))
    return result
