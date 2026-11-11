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
max_steps = 40               # tool-call budget per request

# --- Providers. Switch with `ama provider use <name>`. ---------------------
[providers.claude-cli]       # Claude subscription, through the Claude Code login
type = "claude-cli"

[providers.codex-cli]        # ChatGPT/Codex subscription, through the codex login
type = "codex-cli"

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
        "~/.claude", "~/.codex", "~/.config/gh", "~/.password-store"]
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
