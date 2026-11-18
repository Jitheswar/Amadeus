#!/usr/bin/python3
"""Guest-side checks of real logout/login; physical input comes from QEMU QMP."""
import json, pwd, subprocess, sys, time, traceback
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

def present(name, owner=None):
    args = ["pgrep", "-x", name] + (["-u", owner] if owner else [])
    return subprocess.run(args, stdout=subprocess.DEVNULL).returncode == 0

def desktop():
    """The user's own desktop; the login screen runs a compositor of its own as sddm."""
    return present("Hyprland", user)

GREETER = "sddm-greeter-qt6"

def request(action):
    with open("/dev/ttyS0", "w") as console:
        console.write("\nAMADEUS-UI " + action + "\n"); console.flush()

try:
    if mode == "installed":
        as_user("amadeus-menu", "summon", "root")
        time.sleep(1)
        as_user("amadeus-menu", "close")
        log("GUI: the menu opens and closes")
    as_user("uwsm", "stop")
    wait_for(lambda: not desktop() and present(GREETER), "the login screen did not replace the desktop")
    time.sleep(3)
    # QMP cannot read back the GL scanout. Capture the login screen through its compositor.
    pid = run("pgrep", "-x", GREETER).splitlines()[0]
    entries = Path("/proc/" + pid + "/environ").read_bytes().split(b"\0")
    env = dict(entry.decode().split("=", 1) for entry in entries if b"=" in entry)
    args = ["sudo", "-u", "sddm", "env", "XDG_RUNTIME_DIR=" + env["XDG_RUNTIME_DIR"], "WAYLAND_DISPLAY=" + env["WAYLAND_DISPLAY"], "grim", "-"]
    image = subprocess.check_output(args)
    assert image.startswith(b"\x89PNG\r\n\x1a\n"), "login screen capture was not a PNG"
    target = Path("/mnt/try" if mode == "try" else "/mnt/auto") / ("greeter-" + mode + ".png")
    target.write_bytes(image)
    if mode == "installed":
        cursor = run("journalctl", "-b", "-n", "0", "--show-cursor", "--quiet").strip().removeprefix("-- cursor: ")
        request("wrong-login")
        # PAM logs the failure before its delay ends and SDDM tells the theme.
        def rejected():
            journal = run("journalctl", "-b", "--after-cursor", cursor, "--no-pager")
            return "authentication failure" in journal
        wait_for(rejected, "SDDM never finished rejecting the wrong password")
        assert not desktop(), "wrong password started a desktop"
        log("GUI: wrong password refused")
    request("login-" + mode)
    wait_for(lambda: desktop() and not present(GREETER), "graphical login did not return to the desktop", 35)
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
    log(run("journalctl", "-b", "-u", "sddm", "--no-pager", check=False)[-5000:])
    raise
