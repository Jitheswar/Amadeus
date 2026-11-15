"""Model tuning and execution modes. The two are separate: tuning chooses how a
provider thinks, a mode chooses how much of the configured policy a request may skip."""
import copy
from . import config, policy as P

# What each provider type accepts; an empty choice leaves the provider's own default.
EFFORTS = {
    "claude-cli": ["low", "medium", "high", "xhigh", "max"],
    "codex-cli": ["minimal", "low", "medium", "high", "xhigh"],
    "antigravity-cli": ["low", "medium", "high", "xhigh", "max"],
    "anthropic": ["low", "medium", "high", "xhigh", "max"],
    "openai": ["minimal", "low", "medium", "high", "xhigh"],
}
MODES = ("ask", "sandbox", "auto", "full")
# Journalled or trivially reversed user-level changes: what "auto" may run unasked.
AUTO = {"fs.write", "desktop.control", "desktop.config", "apps.launch", "app.build", "shell.sandbox"}
# Capabilities that decide what the AI may do or see. No mode skips their policy.
GUARDED = {"ai.configure", "ai.memory", "app.grant", "tasks.manage", "screen.observe", "screen.interact"}


def validate(pcfg, model, effort):
    if not isinstance(model, str) or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ValueError("model must be a single model name, or blank for the provider's default")
    if not isinstance(effort, str) or effort not in ["", *EFFORTS.get(pcfg.get("type"), [])]:
        raise ValueError("that effort level is not available for this provider")
    model = model.strip()
    if not model and pcfg.get("type") in ("anthropic", "openai"):
        raise ValueError("enter a model name")
    return model, effort


def save(name, model, effort):
    providers = config.load()["providers"]
    if name not in providers:
        raise ValueError("choose a configured provider")
    model, effort = validate(providers[name], model, effort)
    config._table_update("providers." + name, {"model": model, "effort": effort})


def saved_mode(cfg):
    mode = cfg["ai"].get("mode", "ask")
    return mode if mode in MODES and mode != "full" else "ask"


def save_mode(mode):
    if mode == "full":
        raise ValueError("full access is confirmed for one request at a time and is never saved")
    if mode not in MODES:
        raise ValueError("unknown execution mode")
    config._table_update("ai", {"mode": mode})


def request_config(cfg, name, options=None, default_mode="ask"):
    """The configuration one request runs with: saved settings plus its own overrides."""
    options = options or {}
    if not isinstance(options, dict) or set(options) - {"model", "effort", "mode", "confirm_full_access"}:
        raise ValueError("invalid request options")
    if name not in cfg["providers"]:
        raise ValueError("choose a configured provider")
    pcfg = cfg["providers"][name]
    model, effort = validate(pcfg, options.get("model", pcfg.get("model", "")), options.get("effort", pcfg.get("effort", "")))
    mode = options.get("mode", default_mode)
    if mode not in MODES:
        raise ValueError("unknown execution mode")
    if mode == "full" and options.get("confirm_full_access") is not True:
        raise ValueError("full access needs an explicit confirmation for this request")
    result = copy.deepcopy(cfg)
    result["providers"][name].update(model=model, effort=effort)
    return result, {"model": model, "effort": effort, "mode": mode}


def decision(policy, mode, cap, risk, args, root_on):
    """The configured policy, adjusted by the request's mode. A mode never overrides a
    denial, a destructive or privileged prompt, or a guarded capability."""
    normal, reason = policy.decide(cap, risk, args, root_on=root_on)
    if normal == "deny" or mode == "ask":
        return normal, reason
    if mode == "sandbox":
        if cap == "shell.sandbox" and not args.get("network") and not args.get("nvidia"):
            return "allow", "isolated sandbox"
        if risk == "read" and cap != "shell.host":
            return normal, reason
        return "deny", "sandbox mode does not change this computer"
    if normal == "allow" or risk != "modify" or cap in GUARDED:
        return normal, reason
    # A request must not be able to rewrite the rules it runs under.
    if any(key in args and P._under(args[key], [config.CONFIG]) for key in ("path", "src", "dst")):
        return normal, reason
    if mode == "full":
        return "allow", "full access confirmed for this request"
    if cap in AUTO:
        return "allow", "automatic mode: reversible change"
    return normal, reason
