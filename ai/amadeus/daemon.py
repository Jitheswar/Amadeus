"""amadeusd: the session daemon. One Unix socket, newline-delimited JSON.

  request   {"id", "method", "params"}
  reply     {"id", "result"} | {"id", "error"}
  event     {"id", "event", "data"}        (during `ask`: text, tool, approval)

Everything the AI does goes through `Daemon.execute`, which is the single place
where policy, approval and audit are enforced."""
import json, os, socket, socketserver, subprocess, sys, threading, time, uuid, shutil
from . import config, audit, policy as P, providers, tools as T, agent, root, apps
from .tools import files as F
from .tools import ToolError


class Ctx:
    def __init__(self, daemon, session, origin):
        self.daemon, self.session, self.origin, self.policy = daemon, session, origin, daemon.policy


class Daemon:
    def __init__(self):
        config.ensure_dirs()
        self.reload()
        T.load_all()
        self.sessions = {}          # id -> {"history": [...], "conn": Conn | None}
        self.pending = {}           # approval id -> {"event", "decision"}
        self.app_servers = {}
        self.lock = threading.Lock()

    def reload(self):
        self.cfg = config.load()
        grants = getattr(getattr(self, "policy", None), "session_grants", set())
        self.policy = P.Policy(self.cfg)
        self.policy.session_grants = grants
        return "reloaded"

    # ---- the enforcement point -------------------------------------------
    def execute(self, name, args, session="-", origin="ai", allowed=None):
        t = T.REGISTRY.get(name)
        if not t or (allowed is not None and name not in allowed):
            return f"tool {name} is not available", True
        if not isinstance(args, dict):
            return "arguments must be an object", True
        missing = [k for k in t["schema"]["required"] if k not in args]
        if missing:
            return f"missing arguments: {missing}", True
        try:
            cap = t["cap"](args) if callable(t["cap"]) else t["cap"]
            risk = T.risk_of(t, args)
        except Exception as e:
            return f"invalid arguments: {e}", True
        decision, reason = self.policy.decide(cap, risk, args, root_on=root.enabled())
        if origin.startswith("app:") and decision == "allow" and risk != "read":
            decision, reason = "ask", "requested by an app"
        if decision == "ask":
            answer = self.ask_user(session, origin, name, args, cap, risk, reason)
            if answer == "always":
                self.policy.grant_session(cap, risk)
            decision = "allow" if answer in ("yes", "always") else "deny"
            reason = "user approved" if decision == "allow" else "user declined"
        if decision == "deny":
            audit.record("denied", tool=name, args=args, cap=cap, risk=risk, reason=reason, session=session, origin=origin)
            return f"Not done: {reason}.", True
        if self.sessions.get(session, {}).get("cancel", threading.Event()).is_set():
            return "Not done: the user stopped this task.", True
        t0 = time.time()
        F.current.session = session
        try:
            result = t["fn"](args, Ctx(self, session, origin))
            if isinstance(result, dict) and result.get("ok") is False:      # root helper refusal
                raise ToolError(result.get("error", "failed"))
            content, err = agent.render(result), False
        except ToolError as e:
            content, err = str(e), True
        except Exception as e:
            content, err = f"{type(e).__name__}: {e}", True
        if risk != "read" or err:
            audit.record("action", tool=name, args=args, cap=cap, risk=risk, ok=not err, ms=int((time.time() - t0) * 1000),
                         result=content[:300], session=session, origin=origin, approved=reason)
        return content, err

    # ---- approvals ---------------------------------------------------------
    def ask_user(self, session, origin, name, args, cap, risk, reason):
        aid = uuid.uuid4().hex[:12]
        ev = threading.Event()
        self.pending[aid] = {"event": ev, "decision": "no"}
        data = {"aid": aid, "tool": name, "args": args, "capability": cap, "risk": risk, "reason": reason, "origin": origin}
        s = self.sessions.get(session, {})
        conn = s.get("conn")
        try:
            if conn and conn.alive and conn.interactive:
                conn.event(s.get("rid"), "approval", data)
            else:
                threading.Thread(target=self._dialog, args=(aid, data), daemon=True).start()
            ev.wait(timeout=300)
            return self.pending[aid]["decision"]          # timeout -> "no"
        finally:
            self.pending.pop(aid, None)

    def resolve(self, aid, decision):
        p = self.pending.get(aid)
        if not p:
            return False
        p["decision"] = decision if decision in ("yes", "no", "always") else "no"
        p["event"].set()
        return True

    def _dialog(self, aid, data):
        """Desktop prompt for requests that did not come from an interactive terminal."""
        qml = config.SHARE / "shell" / "approve.qml"
        env = dict(os.environ, AMA_REQ=json.dumps(data), **apps.theme_env())
        try:
            p = subprocess.run(["quickshell", "-p", str(qml)], env=env, capture_output=True, text=True, timeout=290)
            import re
            out = re.findall(r"DECISION (yes|no|always)", p.stdout + p.stderr)
            self.resolve(aid, out[-1] if out else "no")
        except Exception:
            self.resolve(aid, "no")

    # ---- conversations -----------------------------------------------------
    def ask(self, conn, rid, prompt, session=None, provider=None):
        session = session or uuid.uuid4().hex[:10]
        s = self.sessions.setdefault(session, {"history": [], "conn": None, "cancel": threading.Event(), "proc": None})
        if s.get("running"):
            raise RuntimeError("this task is still running")
        s.update(conn=conn, rid=rid, running=True, proc=None)
        s["cancel"].clear()
        s["history"].append({"role": "user", "text": prompt})
        pname = provider or self.cfg["ai"]["provider"]
        audit.record("request", session=session, provider=pname, prompt=prompt)

        def emit(kind, data):
            if kind == "_proc":          # a subscription provider's process, kept so the task can be stopped
                s["proc"] = data
            else:
                conn.event(rid, kind, data)

        def execute(name, args):
            emit("tool", {"name": name, "args": args})
            return self.execute(name, args, session=session)
        try:
            prov = providers.make(pname, self.cfg)
            if prov.kind == "chat":
                text = agent.run_chat(prov, s["history"], execute, emit, int(self.cfg["ai"].get("max_steps", 40)), stopped=s["cancel"].is_set)
            else:
                text = prov.run(agent.system_prompt(), s["history"], session, emit)
                s["history"].append({"role": "assistant", "text": text, "calls": []})
            return {"session": session, "provider": pname, "text": text, "stopped": s["cancel"].is_set(), "changed": F.changed_by(session)}
        except providers.ProviderError as e:
            if s["cancel"].is_set():
                return {"session": session, "provider": pname, "text": "", "stopped": True, "changed": F.changed_by(session)}
            s["history"].pop()
            raise RuntimeError(str(e))
        finally:
            s["running"] = False

    def stop(self, session):
        """Stop a running task: no further tool runs for it, and its provider process ends."""
        s = self.sessions.get(session)
        if not s or not s.get("running"):
            return False
        s["cancel"].set()
        audit.record("stopped", session=session)
        if s.get("proc"):
            try:
                s["proc"].terminate()
            except OSError:
                pass
        return True

    # ---- generated apps ----------------------------------------------------
    def run_app(self, app_id):
        m = apps.manifest(app_id)
        sock = config.RUN / f"app-{app_id}.sock"
        if app_id not in self.app_servers:
            sock.unlink(missing_ok=True)
            srv = socketserver.ThreadingUnixStreamServer(str(sock), make_handler(self, app=app_id))
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.app_servers[app_id] = srv
        subprocess.Popen(apps.command(app_id, sock), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=open(config.STATE / f"app-{app_id}.log", "w"), start_new_session=True)
        audit.record("app_run", app=app_id, permissions=m["permissions"])
        return f"opened {m['name']}"

    # ---- plain methods -----------------------------------------------------
    def status(self):
        from .tools.system import status
        return {"version": __import__("amadeus").__version__, "provider": self.cfg["ai"]["provider"],
                "providers": sorted(self.cfg["providers"]), "root_mode": root.enabled(),
                "session_grants": sorted(self.policy.session_grants), "sessions": len(self.sessions), "system": status()}


class Conn:
    def __init__(self, wfile):
        self.w, self.lock, self.alive, self.interactive, self.ask_id = wfile, threading.Lock(), True, False, None

    def send(self, obj):
        try:
            with self.lock:
                self.w.write((json.dumps(obj, ensure_ascii=False, default=str) + "\n").encode())
                self.w.flush()
        except OSError:
            self.alive = False

    def event(self, rid, kind, data):
        self.send({"id": rid, "event": kind, "data": data})


def make_handler(d, app=None):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            conn = Conn(self.wfile)
            for raw in self.rfile:
                try:
                    req = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                threading.Thread(target=self.dispatch, args=(conn, req), daemon=True).start()
            conn.alive = False

        def dispatch(self, conn, req):
            rid, m, p = req.get("id"), req.get("method"), req.get("params") or {}
            try:
                if app:
                    conn.send({"id": rid, "result": self.app_call(m, p)})
                else:
                    conn.send({"id": rid, "result": self.call(conn, rid, m, p)})
            except Exception as e:
                conn.send({"id": rid, "error": str(e)})

        def app_call(self, m, p):
            """Sandboxed apps reach only what their manifest names."""
            perms = apps.manifest(app)["permissions"]
            if m == "tool":
                content, err = d.execute(p.get("name"), p.get("args") or {}, session=f"app:{app}", origin=f"app:{app}", allowed=set(perms["tools"]))
                if err:
                    raise RuntimeError(content)
                try:
                    return json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    return content
            if m == "ask" and perms["ai"]:
                prov = providers.make(d.cfg["ai"]["provider"], d.cfg)
                hist = [{"role": "user", "text": str(p.get("prompt", ""))[:20000]}]
                if prov.kind == "chat":
                    return prov.chat("You are a text function inside an app. Answer directly and briefly.", hist, [])["text"]
                raise RuntimeError("the active provider cannot answer app queries; switch to an API or local provider")
            raise RuntimeError("not permitted by this app's manifest")

        def call(self, conn, rid, m, p):
            if m == "ask":
                conn.interactive = bool(p.get("interactive"))
                return d.ask(conn, rid, p["prompt"], p.get("session"), p.get("provider"))
            if m == "approve":
                return d.resolve(p["aid"], p["decision"])
            if m == "tool":      # MCP bridge and `ama tool`: same policy path as the built-in loop
                s = p.get("session") or "-"
                sess = d.sessions.get(s, {})
                owner = sess.get("conn")
                if owner and owner.alive:
                    owner.event(sess.get("rid"), "tool", {"name": p["name"], "args": p.get("args") or {}})
                content, err = d.execute(p["name"], p.get("args") or {}, session=s, origin=p.get("origin", "ai"))
                return {"content": content, "is_error": err}
            if m == "tools":
                return T.specs()
            if m == "status":
                return d.status()
            if m == "reload":
                return d.reload()
            if m == "audit":
                return audit.read(int(p.get("n", 30)))
            if m == "audit_verify":
                return audit.verify()
            if m == "undo":
                msg = F.undo_session(p["session"]) if p.get("session") else F.undo_last()
                audit.record("undo", result=msg, session=p.get("session"))
                return msg
            if m == "stop":
                return d.stop(p.get("session"))
            if m == "app_run":
                return d.run_app(p["id"])
            if m == "new_session":
                d.sessions.pop(p.get("session"), None)
                return True
            raise RuntimeError(f"unknown method {m}")
    return Handler


def main():
    d = Daemon()
    config.SOCK.unlink(missing_ok=True)
    old = os.umask(0o177)
    srv = socketserver.ThreadingUnixStreamServer(str(config.SOCK), make_handler(d))
    os.umask(old)
    srv.daemon_threads = True
    audit.record("daemon_start", version=__import__("amadeus").__version__, provider=d.cfg["ai"]["provider"])
    try:
        import signal
        signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        config.SOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
