"""Append-only, hash-chained audit log. Each record commits to the previous one,
so edits or deletions are detectable with `ama audit verify`."""
import json, hashlib, time, threading, os
from . import config

_lock = threading.Lock()
SECRET_KEYS = ("key", "token", "password", "secret", "authorization")


def _path():
    return config.STATE / "audit.jsonl"


def _scrub(v, depth=0):
    if isinstance(v, dict):
        return {k: ("<redacted>" if any(s in k.lower() for s in SECRET_KEYS) else _scrub(x, depth + 1)) for k, x in v.items()}
    if isinstance(v, list):
        return [_scrub(x, depth + 1) for x in v[:50]]
    if isinstance(v, str) and len(v) > 2000:
        return v[:2000] + f"...<{len(v)} chars>"
    return v


def _last_hash(p):
    if not p.exists() or p.stat().st_size == 0:
        return "0" * 64
    with open(p, "rb") as f:
        f.seek(max(0, p.stat().st_size - 65536))
        last = f.read().splitlines()[-1]
    return json.loads(last)["hash"]


def record(kind, **fields):
    p = _path()
    with _lock:
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": round(time.time(), 3), "kind": kind, **_scrub(fields), "prev": _last_hash(p)}
        rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def read(n=50):
    p = _path()
    if not p.exists() or n <= 0:
        return []
    out = []
    for line in reversed(p.read_text().splitlines()):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue        # verify() reports the bad line; the viewer still shows the rest
        if isinstance(rec, dict) and "ts" in rec and "kind" in rec:
            out.append(rec)
            if len(out) >= n:
                break
    return out[::-1]


def verify():
    """Return (ok, count, first_bad_line)."""
    p = _path()
    prev, i = "0" * 64, 0
    if not p.exists():
        return True, 0, None
    for i, line in enumerate(p.read_text().splitlines(), 1):
        rec = json.loads(line)
        h = rec.pop("hash")
        if rec["prev"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest() != h:
            return False, i, i
        prev = h
    return True, i, None
