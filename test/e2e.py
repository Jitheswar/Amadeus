#!/usr/bin/python3
"""End-to-end AI requests on the installed system, with a scripted model.
Runs as the desktop user inside the VM. A local server stands in for the model and
returns fixed tool calls; everything else is real: the daemon, policy, approvals, the
tools, the compositor, the undo journal and the audit log. The client speaks the same
protocol as the Amadeus panel. Prints PASS/FAIL lines for the self-test to count."""
import json, os, queue, socket, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOME = Path.home()
FILES = {k: HOME / f"amadeus-e2e-{k}.txt" for k in ("write", "deny", "slow")}
SCRIPT = {      # scenario -> the one tool call the "model" makes before it answers
    "read": ("sys_status", {}),
    "write": ("fs_write", {"path": str(FILES["write"]), "content": "one"}),
    "deny": ("fs_write", {"path": str(FILES["deny"]), "content": "no"}),
    "slow": ("fs_write", {"path": str(FILES["slow"]), "content": "late"}),
    "launch": ("desktop_launch", {"app": "foot"}),
    "setting": ("desktop_settings", {"area":"text", "action":"set", "value":16}),
    "task-save": ("task_manage", {"action":"save", "id":"e2e-daily", "label":"VM test", "prompt":"E2E:read", "calendar":"daily"}),
    "task-enable": ("task_manage", {"action":"enable", "id":"e2e-daily"}),
    "task-disable": ("task_manage", {"action":"disable", "id":"e2e-daily"}),
    "event-save": ("task_manage", {"action":"save", "id":"e2e-focus", "prompt":"E2E:read", "trigger":"event", "event":"app-focused", "match":"e2e-only", "enabled":True}),

}


class Model(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        msgs = body["messages"]
        last_user = max(i for i, m in enumerate(msgs) if m["role"] == "user" and isinstance(m["content"], str))
        text = msgs[last_user]["content"]
        scenario = text.split("E2E:")[-1].split()[0] if "E2E:" in text else "read"
        answered = any(m["role"] == "tool" for m in msgs[last_user:])
        if scenario == "slow" and not answered:
            time.sleep(4)
        if scenario == "visual":
            results = [m for m in msgs[last_user:] if m["role"] == "tool"]
            if not results:
                name, args = "desktop_observe", {}
            elif len(results) == 1:
                observation = json.loads(results[0]["content"])["observation"]
                Model.saw_image = any(isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"]) for m in msgs[last_user:])
                name, args = "desktop_interact", {"observation":observation, "steps":[{"type":"type", "text":"native-input"}, {"type":"key", "key":"Return"}]}
            else:
                name, args = None, None
            msg = {"role":"assistant", "content":"done visual"} if name is None else {"role":"assistant", "content":None, "tool_calls":[{"id":"visual-"+str(len(results)), "type":"function", "function":{"name":name, "arguments":json.dumps(args)}}]}
        elif answered:
            msg = {"role": "assistant", "content": f"done {scenario}"}
        else:
            name, args = SCRIPT[scenario]
            msg = {"role": "assistant", "content": None,
                   "tool_calls": [{"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
        out = json.dumps({"choices": [{"message": msg}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class Client:
    """The daemon protocol as the panel uses it: one connection, many requests, events by request id."""
    def __init__(self):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(os.path.join(os.environ["XDG_RUNTIME_DIR"], "amadeus/daemon.sock"))
        self.n, self.q, self.lock = 0, {}, threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.s.makefile():
            m = json.loads(line)
            self.q.setdefault(m.get("id"), queue.Queue()).put(m)

    def send(self, method, **params):
        with self.lock:
            self.n += 1
            self.q.setdefault(self.n, queue.Queue())
            self.s.sendall((json.dumps({"id": self.n, "method": method, "params": params}) + "\n").encode())
            return self.n

    def wait(self, rid, approve=None, timeout=60):
        """Collect events until the result. approve answers any approval request ("yes" / "no")."""
        events, end = [], time.time() + timeout
        while time.time() < end:
            try:
                m = self.q[rid].get(timeout=1)
            except queue.Empty:
                continue
            if "event" in m:
                events.append(m)
                if m["event"] == "approval" and approve:
                    self.send("approve", aid=m["data"]["aid"], decision=approve)
            else:
                return m.get("result"), m.get("error"), events
        return None, "timed out", events

    def call(self, method, **params):
        return self.wait(self.send(method, **params))[0]

    def ask(self, scenario, session, approve=None):
        return self.wait(self.send("ask", prompt=f"E2E:{scenario}", session=session, interactive=True), approve)


fails = 0


def check(name, ok, detail=""):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else ' — ' + str(detail)[:300]}", flush=True)


def hyprctl(*args):
    try:
        return json.loads(subprocess.run(["hyprctl", "-j", *args], capture_output=True, text=True).stdout or "null")
    except (OSError, json.JSONDecodeError):
        return None


def main():
    srv = HTTPServer(("127.0.0.1", 0), Model)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = HOME / ".config/amadeus/config.toml"
    before = cfg.read_text() if cfg.exists() else None
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(f'[ai]\nprovider = "local"\n[providers.local]\ntype = "openai"\nbase_url = "http://127.0.0.1:{srv.server_port}/v1"\nmodel = "scripted"\n')
    for f in FILES.values():
        f.unlink(missing_ok=True)
    c = Client()
    try:
        c.call("reload")

        r, err, ev = c.ask("read", "e2e-read")
        check("a request runs a tool and comes back with an answer",
              r and r["text"] == "done read" and any(e["event"] == "tool" and e["data"]["name"] == "sys_status" for e in ev), err or r)

        r, err, ev = c.ask("write", "e2e-write", approve="yes")
        check("a file write asks first, and happens once approved",
              any(e["event"] == "approval" for e in ev) and FILES["write"].exists() and FILES["write"].read_text() == "one", err or ev)
        check("the task reports what it changed", bool(r) and r.get("changed") == 1, r)
        undone = c.call("undo", session="e2e-write")
        check("undoing the task removes the file it created", not FILES["write"].exists(), undone)

        r, err, ev = c.ask("deny", "e2e-deny", approve="no")
        check("a denied write does not happen, and the request still ends cleanly", bool(r) and not FILES["deny"].exists(), err or r)

        r, err, ev = c.ask("launch", "e2e-launch")
        opened = None
        for _ in range(20):
            opened = next((w for w in hyprctl("clients") or [] if w.get("class") == "foot"), None)
            if opened:
                break
            time.sleep(0.5)
        check("the AI opens an application on the desktop", bool(opened), err or r)
        if opened:
            subprocess.run(["hyprctl", "dispatch", 'hl.dsp.window.close({ window = "address:%s" })' % opened["address"]])

        rid = c.send("ask", prompt="E2E:slow", session="e2e-slow", interactive=True)
        time.sleep(1)
        c.call("stop", session="e2e-slow")
        r, err, ev = c.wait(rid, approve="yes", timeout=30)
        check("a stopped task ends and runs no further steps", bool(r) and r.get("stopped") and not FILES["slow"].exists(), err or r)

        a, b = (c.send("ask", prompt="E2E:read", session=s, interactive=True) for s in ("e2e-p1", "e2e-p2"))
        ra, rb = c.wait(a)[0], c.wait(b)[0]
        check("two tasks run side by side on one connection", bool(ra and rb) and ra["session"] != rb["session"], (ra, rb))

        # Native controls use the same wrappers as the human UI, including GTK undo.
        old_text = subprocess.check_output(["amadeus-display", "text"], text=True).strip()
        old_gtk = subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"], text=True).strip()
        r, err, ev = c.ask("setting", "e2e-setting", approve="yes")
        check("AI text changes reach the real desktop controls", subprocess.check_output(["amadeus-display", "text"], text=True).strip() == "16 px" and any(e["event"] == "approval" for e in ev), err or r)
        c.call("undo", session="e2e-setting")
        check("AI text undo restores the unified size", subprocess.check_output(["amadeus-display", "text"], text=True).strip() == old_text and subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"], text=True).strip() == old_gtk)

        for scenario, session in (("task-save","e2e-task-save"), ("task-enable","e2e-task-enable")):
            c.ask(scenario, session, approve="yes")
        timer = "amadeus-task-e2e-daily.timer"
        timer_active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", timer]).returncode == 0
        check("saved tasks enable a real user timer", timer_active and any(j["id"] == "e2e-daily" and j["enabled"] for j in c.call("tasks")))
        rr, ee, events = c.wait(c.send("task_run", id="e2e-daily", interactive=True), approve="yes")
        check("saved tasks run through the selected model and normal tools", bool(rr) and rr.get("text") == "done read" and any(e["event"] == "started" and e["data"]["origin"] == "automation:e2e-daily" for e in events), ee or rr)
        c.ask("task-disable", "e2e-task-disable", approve="yes")
        check("disabled tasks stop their user timer", subprocess.run(["systemctl", "--user", "is-active", "--quiet", timer]).returncode != 0)
        for session in ("e2e-task-disable", "e2e-task-enable", "e2e-task-save"): c.call("undo", session=session)
        check("undo removes saved task and its timer", not any(j["id"] == "e2e-daily" for j in c.call("tasks")) and not (HOME/".config/systemd/user"/timer).exists())
        c.ask("event-save", "e2e-event-save", approve="yes")
        empty = c.call("desktop_event", name="app-focused", data={"app":"different"})
        event = c.call("desktop_event", name="app-focused", data={"app":"e2e-only"})
        cooled = c.call("desktop_event", name="app-focused", data={"app":"e2e-only"})
        check("event tasks filter apps and respect cooldown", empty == [] and bool(event) and event[0].get("text") == "done read" and cooled == [], event)
        c.call("undo", session="e2e-event-save")

        target = HOME / "amadeus-e2e-input.txt"
        target.unlink(missing_ok=True)
        input_app = subprocess.Popen(["foot", "--app-id=amadeus-e2e-input", "sh", "-c", 'cat > "$1"', "sh", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            focused = None
            for _ in range(30):
                focused = hyprctl("activewindow") or {}
                if focused.get("class") == "amadeus-e2e-input": break
                time.sleep(0.2)
            r, err, ev = c.ask("visual", "e2e-visual", approve="yes")
            check("screen observation reaches the model as a native image", getattr(Model, "saw_image", False), err or r)
            check("approved input operates the observed application", target.exists() and "native-input" in target.read_text(), err or r)
            check("screen input asks approval separately from observation", len([e for e in ev if e["event"] == "approval"]) == 2, ev)
        finally:
            input_app.terminate(); input_app.wait(timeout=5); target.unlink(missing_ok=True)

        activity = json.loads((Path(os.environ["XDG_RUNTIME_DIR"])/"amadeus/activity.json").read_text())
        check("native activity returns to idle after completion", activity["running"] == 0, activity)

        kinds = {(x.get("kind"), x.get("tool")) for x in c.call("audit", n=200)}
        check("the audit log has the request, the action, the denial and the stop",
              {("request", None), ("action", "fs_write"), ("denied", "fs_write"), ("stopped", None)} <= kinds, sorted(map(str, kinds)))
        ok = c.call("audit_verify")
        check("the audit log chain is intact afterwards", bool(ok) and ok[0], ok)
    finally:
        cfg.write_text(before) if before is not None else cfg.unlink()
        try:
            c.call("reload")
        except Exception:
            pass
        for f in FILES.values():
            f.unlink(missing_ok=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
