"""Paths and configuration. Everything is plain TOML the user can read and edit."""
import os, tomllib, subprocess
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("AMADEUS_CONFIG", HOME / ".config/amadeus"))
STATE = Path(os.environ.get("AMADEUS_STATE", HOME / ".local/state/amadeus"))
DATA = Path(os.environ.get("AMADEUS_DATA", HOME / ".local/share/amadeus"))
RUN = Path(os.environ.get("AMADEUS_RUN", Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "amadeus"))
SOCK = RUN / "daemon.sock"
PRIV_SOCK = Path(os.environ.get("AMADEUS_PRIV_SOCK", "/run/amadeus/priv.sock"))
APPS = DATA / "apps"
WORKSPACE = DATA / "workspace"
SHARE = Path(os.environ.get("AMADEUS_SHARE", Path(__file__).resolve().parent.parent))

DEFAULT = """\
# Amadeus configuration. Edit freely; `ama reload` applies it.

[ai]
provider = "claude-cli"      # any key under [providers]
mode = "ask"                 # ask | sandbox | auto; full access is confirmed per request, never saved
max_steps = 40               # tool-call budget per request
goal_rounds = 8              # rounds a background goal may work before it checks back with you
notices = true               # offer to look into a failed service or a nearly full disk
context_chars = 200000       # older tool results are dropped from a conversation beyond this

# --- Providers. Switch with `ama provider use <name>`. ---------------------
[providers.claude-cli]       # Claude subscription, through the Claude Code login
type = "claude-cli"

[providers.codex-cli]        # ChatGPT/Codex subscription, through the codex login
type = "codex-cli"

[providers.antigravity-cli]  # Google subscription, through the agy login
type = "antigravity-cli"

[providers.anthropic]        # Claude API key
type = "anthropic"
model = "claude-opus-5-5"
key_env = "ANTHROPIC_API_KEY"

[providers.openai]
type = "openai"
base_url = "https://api.openai.com/v1"
model = ""                   # set the model you want
key_env = "OPENAI_API_KEY"

[providers.openrouter]
type = "openai"
base_url = "https://openrouter.ai/api/v1"
model = "anthropic/claude-opus-5.5"
key_env = "OPENROUTER_API_KEY"

[providers.local]            # any OpenAI-compatible local server (ollama, llama.cpp)
type = "openai"
base_url = "http://127.0.0.1:11434/v1"
model = "qwen2.5-coder:7b"

# --- Policy: allow | ask | deny per capability. ----------------------------
# Destructive actions always ask, whatever is written here.
[policy]
"sys.read" = "allow"
"sys.manage" = "ask"
"fs.read" = "allow"
"fs.write" = "ask"
"shell.sandbox" = "allow"
"shell.host" = "ask"
"desktop.read" = "allow"
"desktop.control" = "allow"
"desktop.config" = "ask"
"ai.configure" = "ask"
"ai.memory" = "ask"
"screen.observe" = "ask"
"screen.interact" = "ask"
"tasks.manage" = "ask"
"net.read" = "allow"
"net.manage" = "ask"
"apps.launch" = "allow"
"app.build" = "allow"
"app.grant" = "ask"
"pkg.manage" = "ask"
"snapshot" = "ask"

[policy.paths]
# The AI can never read these, even with fs.read = allow.
deny = ["~/.ssh", "~/.gnupg", "~/.config/amadeus/secrets", "~/.local/share/keyrings",
        "~/.claude", "~/.codex", "~/.gemini", "~/.config/gh", "~/.password-store"]
# Writes here need no approval.
free = ["~/.local/share/amadeus/workspace"]
"""


def ensure_dirs():
    for d in (CONFIG, STATE, DATA, APPS, WORKSPACE, CONFIG / "secrets"):
        d.mkdir(parents=True, exist_ok=True)
    RUN.mkdir(parents=True, exist_ok=True)
    os.chmod(RUN, 0o700)
    os.chmod(CONFIG / "secrets", 0o700)
    f = CONFIG / "config.toml"
    if not f.exists():
        f.write_text(DEFAULT)


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def load():
    cfg = tomllib.loads(DEFAULT)
    f = CONFIG / "config.toml"
    if f.exists():
        _merge(cfg, tomllib.loads(f.read_text()))
    return cfg


def secret(pcfg, name):
    """Resolve an API key: env var, then secrets file, then a command. Never logged."""
    env = pcfg.get("key_env")
    if env and os.environ.get(env):
        return os.environ[env]
    f = CONFIG / "secrets" / name
    if f.exists():
        return f.read_text().strip()
    if pcfg.get("key_cmd"):
        return subprocess.run(pcfg["key_cmd"], shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    return ""


def provider_info():
    """Display-safe provider choices. Credentials never leave this module."""
    from .providers.cli import find_cli
    from .preferences import EFFORTS, saved_mode
    from urllib.parse import urlparse
    cfg = load()
    labels = {"claude-cli": "Claude Code", "codex-cli": "Codex", "antigravity-cli": "Antigravity",
              "anthropic": "Claude API", "openai": "OpenAI API", "openrouter": "OpenRouter", "local": "Local model"}
    commands = {"claude-cli": "claude", "codex-cli": "codex", "antigravity-cli": "agy"}
    result = []
    for name, p in cfg["providers"].items():
        kind = "Subscription" if p.get("type") in commands else ("Local" if urlparse(p.get("base_url", "")).hostname in ("127.0.0.1", "localhost", "::1") else "API")
        command = p.get("command") or commands.get(p.get("type"), "")
        ready = bool(find_cli(command)) if command else bool(p.get("model"))
        if kind == "API":
            ready = ready and bool(os.environ.get(p.get("key_env", "")) or (CONFIG / "secrets" / name).is_file() or p.get("key_cmd"))
        result.append({"name": name, "label": labels.get(name, name), "kind": kind, "type": p.get("type", ""),
                       "model": p.get("model", ""), "effort": p.get("effort", ""),
                       "effort_levels": EFFORTS.get(p.get("type"), []), "base_url": p.get("base_url", ""), "ready": ready,
                       "default": name == cfg["ai"]["provider"], "command": command})
    return {"default": cfg["ai"]["provider"], "mode": saved_mode(cfg), "providers": result}


def _atomic_config(path, text):
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _table_update(table, values):
    import json, re
    ensure_dirs()
    text = (CONFIG / "config.toml").read_text()
    match = re.search(r"(?m)^\[" + re.escape(table) + r"\][ \t]*(?:#.*)?$", text)
    if match:
        end = re.search(r"(?m)^\[", text[match.end():])
        stop = match.end() + end.start() if end else len(text)
        body = text[match.end():stop]
        for key, value in values.items():
            line = key + " = " + json.dumps(value)
            pattern = r"(?m)^[ \t]*" + re.escape(key) + r"\s*=.*$"
            body, count = re.subn(pattern, lambda m: line, body, count=1)
            if not count:
                body = body.rstrip() + "\n" + line + "\n"
        text = text[:match.end()] + body + text[stop:]
    else:
        text = text.rstrip() + "\n\n[" + table + "]\n" + "\n".join(k + " = " + json.dumps(v) for k, v in values.items()) + "\n"
    tomllib.loads(text)
    _atomic_config(CONFIG / "config.toml", text)


def set_default_provider(name):
    if name not in load()["providers"]:
        raise ValueError("choose a configured provider")
    _table_update("ai", {"provider": name})


def save_provider(name, values, api_key=""):
    import re
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,40}", name):
        raise ValueError("provider name must use lowercase letters, digits and dashes")
    allowed = {"type", "model", "base_url"}
    if not isinstance(values, dict) or set(values) - allowed or any(not isinstance(v, str) for v in values.values()):
        raise ValueError("invalid provider settings")
    if values.get("type") not in ("anthropic", "openai"):
        raise ValueError("choose an API provider type")
    values = dict(values)
    if not values.get("base_url"):
        values["base_url"] = "https://api.anthropic.com" if values["type"] == "anthropic" else "https://api.openai.com/v1"
    if not values.get("model", "").strip():
        raise ValueError("enter a model name")
    from urllib.parse import urlparse
    address = urlparse(values["base_url"])
    if address.scheme not in ("http", "https") or not address.hostname or address.username or address.password:
        raise ValueError("the server address must start with http:// or https://")
    if not isinstance(api_key, str):
        raise ValueError("invalid API key")
    old = (CONFIG / "config.toml").read_text()
    try:
        _table_update("providers." + name, values)
        if api_key:
            _atomic_config(CONFIG / "secrets" / name, api_key.strip())
    except Exception:
        _atomic_config(CONFIG / "config.toml", old)
        raise
