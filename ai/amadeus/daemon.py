"""amadeusd: the session daemon. One Unix socket, newline-delimited JSON.

  request   {"id", "method", "params"}
  reply     {"id", "result"} | {"id", "error"}
  event     {"id", "event", "data"}        (during `ask`: text, tool, approval)

Everything the AI does goes through `Daemon.execute`, which is the single place
where policy, approval and audit are enforced."""
import json, os, socket, socketserver, subprocess, sys, threading, time, uuid, shutil
from . import config, audit, policy as P, preferences, providers, tools as T, agent, root, apps
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
        self.publish_activity()

    def publish_activity(self):
        with self.lock:
            running = [{"session": key, "provider": value.get("provider", ""), "origin": value.get("origin", "ai"),
                        "tool": value.get("tool", ""), "stopping": value.get("cancel", threading.Event()).is_set()}
                       for key, value in self.sessions.items() if value.get("running")]
        try:
            config._atomic_config(config.RUN / "activity.json", json.dumps({"running": len(running), "tasks": running}))
        except OSError:
            pass

    def reload(self):
        self.cfg = config.load()
        grants = getattr(getattr(self, "policy", None), "session_grants", set())
        self.policy = P.Policy(self.cfg)
        self.policy.session_grants = grants
        return "reloaded"

    # ---- the enforcement point -------------------------------------------
    def execute(self, name, args, session="-", origin="ai", allowed=None):
        name, args = T.unwrap(name, args)
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
        mode = self.sessions.get(session, {}).get("mode", "ask")
        decision, reason = preferences.decision(self.policy, mode, cap, risk, args, root.enabled())
        if (origin.startswith("app:") or origin.startswith("automation:")) and decision == "allow" and risk != "read":
            decision, reason = "ask", "requested by an app or automation"
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
        active = self.sessions.get(session)
        if active:
            active["tool"] = name
            self.publish_activity()
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
        if active:
            active["tool"] = ""
            self.publish_activity()
        if risk != "read" or err:
            audit.record("action", tool=name, args=args, cap=cap, risk=risk, ok=not err, ms=int((time.time() - t0) * 1000),
                         result=("Screen observation captured" if name == "desktop_observe" and not err else content[:300]), session=session, origin=origin, approved=reason)
        return content, err

    # ---- approvals ---------------------------------------------------------
    def ask_user(self, session, origin, name, args, cap, risk, reason):
        aid = uuid.uuid4().hex[:12]
        ev = threading.Event()
        self.pending[aid] = {"event": ev, "decision": "no", "session": session}
        data = {"aid": aid, "tool": name, "args": args, "capability": cap, "risk": risk, "reason": reason, "origin": origin, "rememberable": not origin.startswith(("app:", "automation:"))}
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
        process = None
        try:
            process = subprocess.Popen(["quickshell", "-p", str(qml)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            pending = self.pending.get(aid)
            if not pending:
                process.terminate()
            else:
                pending["dialog"] = process
                if pending["event"].is_set(): process.terminate()
            stdout, stderr = process.communicate(timeout=290)
            import re
            out = re.findall(r"DECISION (yes|no|always)", stdout + stderr)
            self.resolve(aid, out[-1] if out else "no")
        except Exception:
            if process and process.poll() is None:
                process.kill(); process.communicate()
            self.resolve(aid, "no")

    # ---- conversations -----------------------------------------------------
    def ask(self, conn, rid, prompt, session=None, provider=None, origin="ai", options=None):
        session = session or uuid.uuid4().hex[:10]
        pname = provider or self.cfg["ai"]["provider"]
        # Only the user's own requests follow the saved mode; automations keep the plain policy.
        cfg, chosen = preferences.request_config(self.cfg, pname, options, preferences.saved_mode(self.cfg) if origin == "ai" else "ask")
        # Requests have independent threads; reserving a session must be atomic.
        with self.lock:
            s = self.sessions.setdefault(session, {"history": [], "conn": None, "cancel": threading.Event(), "proc": None})
            if s.get("running"):
                raise RuntimeError("this task is still running")
            s.update(conn=conn, rid=rid, running=True, proc=None, origin=origin, provider=pname, mode=chosen["mode"])
            s["cancel"].clear()
            start = len(s["history"])
            s["history"].append({"role": "user", "text": prompt, "at": agent.now()})
        self.publish_activity()

        usage = {}

        def emit(kind, data):
            if kind == "_proc":
                s["proc"] = data
            elif kind == "usage":
                usage.update(data)
            else:
                conn.event(rid, kind, data)

        def execute(name, args):
            name, args = T.unwrap(name, args)
            emit("tool", {"name": name, "args": args})
            return self.execute(name, args, session=session, origin=origin)
        completed, agent_started = False, False
        try:
            emit("started", {"session": session, "provider": pname, "origin": origin, **chosen})
            audit.record("request", session=session, provider=pname, prompt=prompt, **chosen)
            prov = providers.make(pname, cfg)
            if prov.kind == "chat":
                text = agent.run_chat(prov, s["history"], execute, emit, int(self.cfg["ai"].get("max_steps", 40)), stopped=s["cancel"].is_set,
                                      budget=int(self.cfg["ai"].get("context_chars", 200000)))
            else:
                agent_started = True
                text = prov.run(agent.system_prompt(), s["history"], session, emit)
                s["history"].append({"role": "assistant", "text": text, "calls": []})
            completed = True
            if usage:
                audit.record("usage", session=session, provider=pname, **usage)
            return {"session": session, "provider": pname, "text": text, "stopped": s["cancel"].is_set(), "changed": F.changed_by(session), "usage": usage}
        except providers.ProviderError as e:
            if s["cancel"].is_set():
                return {"session": session, "provider": pname, "text": "", "stopped": True, "changed": F.changed_by(session)}
            raise RuntimeError(str(e))
        finally:
            if not completed:
                if agent_started:
                    # CLI tools may already have run; preserve their request for the next turn.
                    s["history"].append({"role": "assistant", "text": "The agent did not complete this request. Tool actions may have run; check the audit log before retrying.", "calls": []})
                else:
                    del s["history"][start:]    # never replay half-finished API tool calls
            with self.lock:
                s["running"] = False
                s.pop("mode", None)     # a mode covers one request, not later calls naming its session
            self.publish_activity()

    def stop(self, session):
        """Stop a running task: no further tool runs for it, and its provider process ends."""
        s = self.sessions.get(session)
        if not s or not s.get("running"):
            return False
        s["cancel"].set()
        audit.record("stopped", session=session)
        self.publish_activity()
        for aid, pending in list(self.pending.items()):
            if pending.get("session") == session:
                self.resolve(aid, "no")
                dialog = pending.get("dialog")
                if dialog and dialog.poll() is None:
                    try: dialog.terminate()
                    except OSError: pass
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
        argv = apps.command(app_id, sock)
        log = config.STATE / f"app-{app_id}.log"
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)        # os.open's mode only applies when it creates the file
        err = os.fdopen(fd, "w")
        try:
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=err, start_new_session=True)
        finally:
            err.close()
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
                return d.ask(conn, rid, p["prompt"], p.get("session"), p.get("provider"), options=p.get("options"))
            if m == "approve":
                return d.resolve(p["aid"], p["decision"])
            if m == "tool":      # MCP bridge and `ama tool`: same policy path as the built-in loop
                s = p.get("session") or "-"
                sess = d.sessions.get(s, {})
                owner = sess.get("conn")
                name, args = T.unwrap(p["name"], p.get("args") or {})
                if owner and owner.alive:
                    owner.event(sess.get("rid"), "tool", {"name": name, "args": args})
                content, err = d.execute(p["name"], p.get("args") or {}, session=s, origin=sess.get("origin", p.get("origin", "ai")))
                return {"content": content, "is_error": err}
            if m == "tasks":
                from . import tasks
                return tasks.listing()
            if m == "task_run":
                conn.interactive = bool(p.get("interactive"))
                from . import tasks
                return tasks.run(d, conn, rid, p["id"])
            if m == "desktop_event":
                from . import tasks
                return tasks.event(d, conn, rid, p["name"], p.get("data") or {})
            if m == "providers":
                return config.provider_info()
            if m == "provider_default":
                config.set_default_provider(p["name"])
                d.reload()
                return config.provider_info()
            if m == "provider_save":
                config.save_provider(p["name"], p["settings"], p.get("api_key", ""))
                d.reload()
                return config.provider_info()
            if m == "provider_tune":
                preferences.save(p["name"], p.get("model", ""), p.get("effort", ""))
                d.reload()
                return config.provider_info()
            if m == "mode_default":
                preferences.save_mode(p["mode"])
                d.reload()
                return config.provider_info()
            if m == "usage":
                from .usage import collect
                return collect(d.cfg, force=bool(p.get("force")))
            if m == "tools":
                return T.specs()
            if m == "memory":
                from . import memory
                if p.get("forget"):
                    memory.forget(int(p["forget"]))
                elif p.get("clear"):
                    memory.clear()
                return memory.notes()
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
                d.reload()
                audit.record("undo", result=msg, session=p.get("session"))
                return msg
            if m == "stop":
                return d.stop(p.get("session"))
            if m == "stop_all":
                return sum(d.stop(session) for session in list(d.sessions))
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
        (config.RUN / "activity.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
