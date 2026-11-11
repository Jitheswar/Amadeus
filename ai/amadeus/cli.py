"""ama: the command-line face of Amadeus."""
import json, os, re, socket, subprocess, sys, time
from . import config

HELP = """ama — talk to and control Amadeus. El Psy Kongroo.

  ama <request...>            do something ("free up disk space", "put a clock widget after the workspaces")
  ama chat                    interactive session
  ama status                  daemon, provider, root mode, machine state
  ama provider [use NAME | key NAME]
  ama root on [--full] [--ttl MIN] | off | status
  ama app list | run ID | history ID | rollback ID [N] | remove ID
  ama audit [N] | audit verify
  ama undo                    restore the last file the AI changed (the panel can undo a whole task)
  ama tool NAME [JSON]        call one tool directly (same policy as the AI)
  ama doctor                  verify drivers, GPU, sandbox and providers
  ama discover [--json]       a live map of this system: commands, files, tools, policy
  ama skill                   print the built-in guide that teaches an AI agent to manage this system
  ama panel [toggle | show | hide | window | state]
                              the docked panel; `window` makes the next request about the focused window
  ama reload | daemon | mcp
"""
C = {"dim": "\033[2m", "b": "\033[1m", "y": "\033[33m", "r": "\033[31m", "g": "\033[32m", "0": "\033[0m"} if sys.stdout.isatty() else dict.fromkeys(["dim", "b", "y", "r", "g", "0"], "")


class Client:
    def __init__(self, timeout=None):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.settimeout(timeout)
        try:
            self.s.connect(str(config.SOCK))
        except OSError:
            subprocess.run(["systemctl", "--user", "start", "amadeusd"], capture_output=True)
            for _ in range(30):
                try:
                    self.s.connect(str(config.SOCK))
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                sys.exit("amadeusd is not running. Start it with: systemctl --user start amadeusd  (or `ama daemon`)")
        self.f = self.s.makefile("rwb")
        self.n = 0

    def send(self, method, **params):
        self.n += 1
        self.f.write((json.dumps({"id": self.n, "method": method, "params": params}) + "\n").encode())
        self.f.flush()
        return self.n

    def call(self, method, on_event=None, **params):
        rid = self.send(method, **params)
        for line in self.f:
            m = json.loads(line)
            if m.get("id") != rid:
                continue
            if "event" in m:
                if on_event:
                    on_event(m["event"], m["data"])
                continue
            if "error" in m:
                raise RuntimeError(m["error"])
            return m["result"]
        raise RuntimeError("connection closed")


def short(v, n=90):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + "…"


def ask(c, prompt, session=None, provider=None):
    tty = sys.stdin.isatty()

    def on_event(kind, d):
        if kind == "text":
            print(d["text"], flush=True)
        elif kind == "tool":
            print(f"{C['dim']}  · {d['name']} {short(d['args'])}{C['0']}", flush=True)
        elif kind == "approval":
            print(f"\n{C['y']}{C['b']}Amadeus wants to: {d['tool']}{C['0']}  {C['dim']}[{d['capability']} · {d['risk']}]{C['0']}")
            for k, v in d["args"].items():
                print(f"    {k}: {short(v, 400)}")
            opts = "[y]es / [n]o" + ("" if d["risk"] in ("destructive", "privileged") else " / [a]lways this session")
            try:
                ans = input(f"  Allow? {opts} ").strip().lower()[:1]
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            c.send("approve", aid=d["aid"], decision={"y": "yes", "a": "always"}.get(ans, "no"))
    r = c.call("ask", on_event, prompt=prompt, session=session, provider=provider, interactive=tty)
    return r["session"]


def mcp():
    """Model Context Protocol server on stdio, so Claude Code, Claude Desktop, Codex and
    any other MCP client drive the OS through the same policy as the built-in agent."""
    c = Client()
    session = os.environ.get("AMADEUS_SESSION", "mcp")
    out = sys.stdout
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid, m, p = req.get("id"), req.get("method", ""), req.get("params") or {}
        if rid is None:
            continue
        try:
            if m == "initialize":
                res = {"protocolVersion": p.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                       "serverInfo": {"name": "amadeus", "version": "0.1.0"},
                       "instructions": "Tools for operating this computer. Every call is checked against the user's policy and may wait for their approval."}
            elif m == "tools/list":
                res = {"tools": [{"name": t["name"], "description": t["description"], "inputSchema": t["schema"]} for t in c.call("tools")]}
            elif m == "tools/call":
                r = c.call("tool", name=p["name"], args=p.get("arguments") or {}, session=session, origin="mcp")
                res = {"content": [{"type": "text", "text": r["content"]}], "isError": r["is_error"]}
            elif m == "ping":
                res = {}
            else:
                out.write(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown method {m}"}}) + "\n")
                out.flush()
                continue
            out.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}) + "\n")
        except Exception as e:
            out.write(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": str(e)}}) + "\n")
        out.flush()


PRIV_DIR = "/usr/lib/amadeus"


def root_cmd(args):
    from . import root
    sub = args[0] if args else "status"
    if sub == "status":
        if not root.enabled():
            return print("root mode: off")
        r = root.call("info")
        return print(f"root mode: ON ({'unrestricted' if r.get('full') else 'restricted to system tools'})"
                     + (f", turns off in {r['ttl_left'] // 60} min" if r.get("ttl_left") else ", until shutdown or `ama root off`"))
    if sub == "off":
        print(root.call("shutdown").get("result", "root mode: off") if root.enabled() else "root mode: off")
        return
    if sub == "on":
        if not os.path.exists(f"{PRIV_DIR}/root-mode"):
            sys.exit(f"The privileged helper is not installed; it is part of the amadeus system package.")
        cmd = ["pkexec", f"{PRIV_DIR}/root-mode", "on", "--uid", str(os.getuid())]
        if "--full" in args:
            cmd.append("--full")
        if "--ttl" in args:
            cmd += ["--ttl", str(int(args[args.index("--ttl") + 1]))]
        if subprocess.run(cmd).returncode == 0:
            for _ in range(30):
                if root.enabled():
                    break
                time.sleep(0.1)
            root_cmd(["status"])
        return
    sys.exit(HELP)


def panel_cmd(args):
    """Drive the docked Amadeus panel, starting it on first use."""
    from . import apps
    qml = str(config.SHARE / "shell" / "panel.qml")
    action = args[0] if args else "toggle"
    extra = []
    if action == "window":          # the next request is about the window that has focus right now
        from .tools import desktop
        try:
            w = desktop.nj("focused-window") or {}
        except Exception:
            w = {}
        if w:
            extra = [json.dumps({"id": w.get("id"), "app": w.get("app_id") or "", "title": (w.get("title") or "")[:120]})]
        else:
            action = "show"
    if action not in ("toggle", "show", "hide", "window", "state"):
        sys.exit(HELP)

    def call(fn, *a):
        return subprocess.run(["quickshell", "ipc", "-p", qml, "call", "panel", fn, *a], capture_output=True, text=True)
    p = call(action, *extra)
    if p.returncode:                # not running yet
        if action == "hide":
            return
        subprocess.Popen(["quickshell", "-p", qml], env=dict(os.environ, **apps.theme_env()), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        first = "show" if action == "toggle" else action
        for _ in range(50):
            time.sleep(0.1)
            p = call(first, *extra)
            if not p.returncode:
                break
        else:
            sys.exit("the Amadeus panel could not be started")
    if p.stdout.strip():
        print(p.stdout.strip())


def provider_cmd(c, args):
    cfg = config.load()
    if not args:
        for name, p in sorted(cfg["providers"].items()):
            mark = "*" if name == cfg["ai"]["provider"] else " "
            print(f" {mark} {name:<14} {p['type']:<11} {p.get('model') or p.get('base_url', '')}")
        return
    if args[0] == "use" and len(args) == 2:
        if args[1] not in cfg["providers"]:
            sys.exit(f"no provider {args[1]}")
        f = config.CONFIG / "config.toml"
        text, n = re.subn(r'(?m)^(provider\s*=\s*)"[^"]*"', rf'\1"{args[1]}"', f.read_text(), count=1)
        f.write_text(text if n else f'[ai]\nprovider = "{args[1]}"\n' + text)
        c.call("reload")
        return print(f"provider: {args[1]}")
    if args[0] == "key" and len(args) == 2:
        import getpass
        key = getpass.getpass(f"API key for {args[1]} (stored in ~/.config/amadeus/secrets, mode 600): ").strip()
        f = config.CONFIG / "secrets" / args[1]
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(fd, key.encode())
        os.close(fd)
        return print("saved")
    sys.exit(HELP)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help", "help"):
        return print(HELP)
    cmd, rest = a[0], a[1:]
    if cmd == "daemon":
        from .daemon import main as dmain
        return dmain()
    if cmd == "mcp":
        return mcp()
    if cmd == "root":
        return root_cmd(rest)
    if cmd == "discover":
        from .discover import main as disc
        return disc(rest)
    if cmd == "skill":
        return print((config.SHARE / "skill" / "amadeus" / "SKILL.md").read_text())
    if cmd == "doctor":
        from .doctor import main as doc
        return doc()
    if cmd == "panel":
        return panel_cmd(rest)
    c = Client()
    if cmd == "status":
        r = c.call("status")
        s = r.pop("system")
        print(f"amadeus {r['version']} · provider {r['provider']} · root mode {'ON' if r['root_mode'] else 'off'} · session grants {r['session_grants'] or 'none'}")
        print(f"load {s['load'][0]:.2f} · mem {s['mem_mb']['MemAvailable']} MB free of {s['mem_mb']['MemTotal']} · disk {s['disk_root_gb']['free']} GB free · "
              f"profile {s['power_profile']} · nvidia {s['gpu'].get('nvidia')} · battery {s['battery'].get('percent', '?')}% {s['battery'].get('status', '')}")
        if s["failed_units"]:
            print(f"{C['r']}failed units: {', '.join(s['failed_units'])}{C['0']}")
    elif cmd == "provider":
        provider_cmd(c, rest)
    elif cmd == "reload":
        print(c.call("reload"))
    elif cmd == "undo":
        print(c.call("undo"))
    elif cmd == "audit":
        if rest[:1] == ["verify"]:
            ok, n, bad = c.call("audit_verify")
            print(f"{n} records, chain intact" if ok else f"{C['r']}TAMPERED at record {bad}{C['0']}")
            sys.exit(0 if ok else 1)
        for r in c.call("audit", n=int(rest[0]) if rest else 30):
            ts = time.strftime("%m-%d %H:%M:%S", time.localtime(r["ts"]))
            body = {k: v for k, v in r.items() if k not in ("ts", "kind", "prev", "hash")}
            print(f"{C['dim']}{ts}{C['0']} {r['kind']:<8} {short(body, 160)}")
    elif cmd == "tool":
        if not rest:
            for t in c.call("tools"):
                print(f"{t['name']:<24} {t['description'][:90]}")
            return
        r = c.call("tool", name=rest[0], args=json.loads(rest[1]) if len(rest) > 1 else {}, origin="user-cli")
        print(r["content"])
        sys.exit(1 if r["is_error"] else 0)
    elif cmd == "app":
        from . import apps
        sub = rest[0] if rest else "list"
        if sub == "list":
            for m in apps.list_apps():
                p = m["permissions"]
                grants = [k for k in ("network", "nvidia", "ai") if p[k]] + [f"{f['mode']}:{f['path']}" for f in p["files"]] + p["tools"]
                print(f"{m['id']:<20} v{m['version']:<3} {m['name']:<24} {', '.join(grants) or 'no permissions'}")
        elif sub == "run":
            print(c.call("app_run", id=rest[1]))
        elif sub == "history":
            print("\n".join(apps.history(rest[1])))
        elif sub == "rollback":
            print(apps.rollback(rest[1], rest[2] if len(rest) > 2 else None)["version"])
        elif sub == "remove":
            print(apps.remove(rest[1]))
        elif sub == "command":
            print(" ".join(apps.command(rest[1])))
        else:
            sys.exit(HELP)
    elif cmd == "chat":
        session = None
        print(f"{C['dim']}Amadeus. Ctrl-D to leave, /new for a fresh conversation.{C['0']}")
        while True:
            try:
                line = input(f"{C['g']}› {C['0']}").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line == "/new":
                session = None
            elif line:
                try:
                    session = ask(c, line, session)
                except RuntimeError as e:
                    print(f"{C['r']}{e}{C['0']}")
    else:
        prompt = " ".join(a[1:] if cmd == "ask" else a)
        try:
            ask(c, prompt)
        except RuntimeError as e:
            sys.exit(f"{C['r']}{e}{C['0']}")


if __name__ == "__main__":
    main()
