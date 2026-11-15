#!/usr/bin/python3
"""Preselect a real login profile without changing authentication or storing a password."""
import json, os, pwd, sys, tempfile, tomllib
from pathlib import Path


def prepare(path, accounts=None):
    accounts = pwd.getpwall() if accounts is None else accounts
    names = [p.pw_name for p in sorted(accounts, key=lambda p: p.pw_uid)
             if 1000 <= p.pw_uid < 65534 and p.pw_dir.startswith("/home/")
             and not p.pw_shell.endswith(("/nologin", "/false"))]
    if not names: return "multi"
    try: state = tomllib.loads(path.read_text())
    except (OSError, ValueError): state = {}
    if state.get("last_user") not in names:
        # Only a display preference is seeded. greetd/PAM still authenticates every real account.
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "last_user = " + json.dumps(names[0]) + "\n[user_to_last_sess]\n"
        for name in names: text += json.dumps(name) + ' = "Amadeus"\n'
        fd, temp = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "w") as file: file.write(text)
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
    return "single" if len(names) == 1 else "multi"


if __name__ == "__main__":
    print(prepare(Path(sys.argv[1])))
