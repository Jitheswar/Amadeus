#!/usr/bin/python3
"""Guest-side checks of real logout/login; physical input comes from QEMU QMP."""
import json, os, pwd, subprocess, sys, time, traceback
from pathlib import Path

mode = sys.argv[1]
user = "amadeus" if mode == "try" else "tester"
uid = pwd.getpwnam(user).pw_uid
runtime = f"/run/user/{uid}"
log_path = Path("/mnt/try" if mode == "try" else "/mnt/auto") / "ui-check.log"

def log(text):
    print(text, flush=True)
    with log_path.open("a") as file: file.write(str(text) + "\n")

def run(*args, check=True):
    return subprocess.run(args, capture_output=True, text=True, check=check).stdout

def as_user(*args):
    env = [f"XDG_RUNTIME_DIR={runtime}", f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus", f"HOME=/home/{user}"]
    displays = sorted((p for p in Path(runtime).glob("wayland-*") if p.is_socket()), key=lambda p: p.stat().st_mtime)
    if displays: env.append("WAYLAND_DISPLAY=" + displays[-1].name)
    instances = sorted(Path(runtime).glob("hypr/*/.socket.sock"), key=lambda p: p.stat().st_mtime)
    if instances: env.append("HYPRLAND_INSTANCE_SIGNATURE=" + instances[-1].parent.name)
    return run("sudo", "-u", user, "env", *env, *args)

def wait_for(test, label, timeout=25):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if test(): return
        time.sleep(0.3)
    raise RuntimeError(label)

def present(name):
    return subprocess.run(["pgrep", "-x", name], stdout=subprocess.DEVNULL).returncode == 0

def request(action):
    with open("/dev/ttyS0", "w") as console:
        console.write("\nAMADEUS-UI " + action + "\n"); console.flush()

try:
    if mode == "installed":
        as_user("sh", "-c", "amadeus-menu >/tmp/amadeus-menu-input-test.log 2>&1 &")
        def shell_state():
            return json.loads(as_user("quickshell", "ipc", "-p", "/usr/share/amadeus-os/shell", "call", "shell", "state"))
        wait_for(lambda: shell_state()["picker"], "menu did not open")
        request("menu-hover"); time.sleep(1)
        before = shell_state()
        request("menu-down"); time.sleep(1)
        after = shell_state()
        assert after["pickerIndex"] == min(before["pickerIndex"]+2, before["pickerItems"]-1), (before, after)
        as_user("quickshell", "ipc", "-p", "/usr/share/amadeus-os/shell", "call", "pick", "cancel")
        log("GUI: keyboard keeps selection with mouse over menu")
    as_user("uwsm", "stop")
    wait_for(lambda: not present("Hyprland") and present("regreet") and present("cage"), "graphical greeter did not replace the desktop")
    time.sleep(3)
    # QMP cannot read back the GL scanout. Capture the real greeter through Cage's screencopy API.
    pid = run("pgrep", "-x", "regreet").splitlines()[0]
    entries = Path("/proc/" + pid + "/environ").read_bytes().split(b"\0")
    env = dict(entry.decode().split("=", 1) for entry in entries if b"=" in entry)
    args = ["sudo", "-u", "greeter", "env", "XDG_RUNTIME_DIR=" + env["XDG_RUNTIME_DIR"], "WAYLAND_DISPLAY=" + env["WAYLAND_DISPLAY"], "grim", "-"]
    image = subprocess.check_output(args)
    assert image.startswith(b"\x89PNG\r\n\x1a\n"), "greeter capture was not a PNG"
    target = Path("/mnt/try" if mode == "try" else "/mnt/auto") / ("greeter-" + mode + ".png")
    target.write_bytes(image)
    if mode == "installed":
        request("wrong-login-auto" if Path("/usr/share/amadeus-os/greeter/profiles.py").exists() else "wrong-login")
        time.sleep(4)
        assert not present("Hyprland"), "wrong password started a desktop"
        journal = run("journalctl", "-b", "-u", "greetd", "--no-pager")
        assert "authentication failure" in journal.lower(), "wrong-password authentication was not exercised"
        log("GUI: wrong password refused")
    request("login-" + mode)
    wait_for(lambda: present("Hyprland") and not present("regreet"), "graphical login did not return to the desktop", 35)
    wait_for(lambda: Path(runtime + "/amadeus/daemon.sock").is_socket(), "AI session did not return")
    log("GUI: logout and graphical login passed (" + mode + ")")
except Exception as error:
    log(traceback.format_exc())
    if isinstance(error, subprocess.CalledProcessError): log(error.stderr)
    log(run("journalctl", "-b", "_UID=" + str(uid), "--no-pager", "-n", "150", check=False)[-16000:])
    for command in (("list-jobs",), ("list-units", "--failed", "--no-pager")):
        try: log(as_user("systemctl", "--user", *command))
        except Exception as error: log(error)
    try: log("VT text: " + Path("/dev/vcs1").read_text(errors="replace"))
    except OSError: pass
    log(run("journalctl", "-b", "-u", "greetd", "--no-pager", check=False)[-5000:])
    raise
