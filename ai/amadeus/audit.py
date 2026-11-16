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


def _tail(p):
    """(hash of the last whole record, whether the file ends mid-line).

    A power cut can leave half a record at the end. That must not stop the log: the next
    record starts on its own line and continues from the last whole one, and the damaged
    line stays in place for verify() to report."""
    if not p.exists() or p.stat().st_size == 0:
        return "0" * 64, False
    with open(p, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos, buf = f.tell(), b""
        while pos > 0:
            # Records can exceed one read window, so grow it until a whole record is inside.
            step = min(65536, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            lines = buf.split(b"\n")
            for line in reversed(lines if pos == 0 else lines[1:]):     # the first may be cut by the window
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and isinstance(rec.get("hash"), str):
                    return rec["hash"], not buf.endswith(b"\n")
    return "0" * 64, not buf.endswith(b"\n")


def record(kind, **fields):
    p = _path()
    with _lock:
        p.parent.mkdir(parents=True, exist_ok=True)
        prev, torn = _tail(p)
        rec = {"ts": round(time.time(), 3), "kind": kind, **_scrub(fields), "prev": prev}
        rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as f:
            os.fchmod(f.fileno(), 0o600)    # also close the descriptor if chmod fails
            f.write(("\n" if torn else "") + json.dumps(rec) + "\n")
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
        try:
            rec = json.loads(line)
            if not isinstance(rec, dict):
                return False, i, i
            h = rec.pop("hash")
            if rec["prev"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest() != h:
                return False, i, i
        except (json.JSONDecodeError, KeyError, TypeError):
            return False, i, i
        prev = h
    return True, i, None
