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
}


class Model(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        msgs = body["messages"]
        last_user = max(i for i, m in enumerate(msgs) if m["role"] == "user")
        scenario = msgs[last_user]["content"].split("E2E:")[-1].split()[0]
        answered = any(m["role"] == "tool" for m in msgs[last_user:])
        if scenario == "slow" and not answered:
            time.sleep(4)
        if answered:
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


def niri(*args):
    try:
        return json.loads(subprocess.run(["niri", "msg", "--json", *args], capture_output=True, text=True).stdout or "null")
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
            opened = next((w for w in niri("windows") or [] if w.get("app_id") == "foot"), None)
            if opened:
                break
            time.sleep(0.5)
        check("the AI opens an application on the desktop", bool(opened), err or r)
        if opened:
            subprocess.run(["niri", "msg", "action", "close-window", "--id", str(opened["id"])])

        rid = c.send("ask", prompt="E2E:slow", session="e2e-slow", interactive=True)
        time.sleep(1)
        c.call("stop", session="e2e-slow")
        r, err, ev = c.wait(rid, approve="yes", timeout=30)
        check("a stopped task ends and runs no further steps", bool(r) and r.get("stopped") and not FILES["slow"].exists(), err or r)

        a, b = (c.send("ask", prompt="E2E:read", session=s, interactive=True) for s in ("e2e-p1", "e2e-p2"))
        ra, rb = c.wait(a)[0], c.wait(b)[0]
        check("two tasks run side by side on one connection", bool(ra and rb) and ra["session"] != rb["session"], (ra, rb))

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


main()
