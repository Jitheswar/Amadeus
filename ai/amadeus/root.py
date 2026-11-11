"""Client for the privileged helper. Root mode is a transient root service that
exists only while the user has switched it on; it is never enabled at boot, so a
shutdown always turns it off."""
import json, socket
from . import config


def enabled():
    return config.PRIV_SOCK.exists()


def call(op, timeout=900, **args):
    if not enabled():
        return {"ok": False, "error": "root mode is off"}
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(timeout)
    try:
        s.connect(str(config.PRIV_SOCK))
        s.sendall((json.dumps({"op": op, "args": args}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf or b'{"ok": false, "error": "no reply from helper"}')
    except OSError as e:
        return {"ok": False, "error": f"helper unreachable: {e}"}
    finally:
        s.close()
