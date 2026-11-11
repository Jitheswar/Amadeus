"""bubblewrap sandboxes for AI-run commands and generated apps.

Default is: no network, no home directory, read-only system, a private tmp,
and only the paths explicitly granted. Nothing here needs root or a daemon."""
import os, glob
from pathlib import Path

UID = os.getuid()
XRD = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{UID}")


def _gpu_nodes(vendor):
    """DRM nodes belonging to one PCI vendor (0x8086 Intel, 0x10de NVIDIA).
    Reads sysfs only, so a suspended NVIDIA card is not woken."""
    out = []
    for dev in glob.glob("/sys/class/drm/*/device/vendor"):
        node = Path(dev).parent.parent.name
        if "-" in node:      # connectors such as card1-eDP-1
            continue
        try:
            if Path(dev).read_text().strip() == vendor and os.path.exists(f"/dev/dri/{node}"):
                out.append(f"/dev/dri/{node}")
        except OSError:
            pass
    return sorted(out)


def bwrap(cmd, *, rw=(), ro=(), net=False, gui=False, nvidia=False, cwd=None, env=None, home_tmpfs=True):
    home = str(Path.home())
    a = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all"]
    if net:
        a += ["--share-net"]
    a += ["--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib", "/lib64",
          "--symlink", "usr/bin", "/bin", "--symlink", "usr/bin", "/sbin", "--ro-bind", "/etc", "/etc",
          "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/run", "--dir", XRD,
          "--tmpfs", "/var", "--clearenv",
          "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", home, "--setenv", "LANG", os.environ.get("LANG", "C.UTF-8"),
          "--setenv", "XDG_RUNTIME_DIR", XRD, "--setenv", "TERM", "dumb"]
    if home_tmpfs:
        a += ["--tmpfs", home]
    if net and os.path.exists("/run/systemd/resolve"):
        a += ["--ro-bind", "/run/systemd/resolve", "/run/systemd/resolve"]
    if gui:
        wl = os.environ.get("WAYLAND_DISPLAY", "wayland-1")
        sock = f"{XRD}/{wl}"
        if os.path.exists(sock):
            a += ["--ro-bind", sock, sock, "--setenv", "WAYLAND_DISPLAY", wl]
        a += ["--setenv", "QT_QPA_PLATFORM", "wayland", "--setenv", "XDG_SESSION_TYPE", "wayland",
              "--ro-bind", "/sys", "/sys"]
        for node in _gpu_nodes("0x8086"):
            a += ["--dev-bind", node, node]
        for d in (f"{home}/.local/share/fonts", f"{home}/.config/fontconfig"):
            if os.path.isdir(d):
                a += ["--ro-bind", d, d]
    if nvidia:
        for node in _gpu_nodes("0x10de") + sorted(glob.glob("/dev/nvidia*")):
            a += ["--dev-bind", node, node]
        if not gui:
            a += ["--ro-bind", "/sys", "/sys"]
        a += ["--setenv", "__NV_PRIME_RENDER_OFFLOAD", "1", "--setenv", "__GLX_VENDOR_LIBRARY_NAME", "nvidia",
              "--setenv", "__VK_LAYER_NV_optimus", "NVIDIA_only"]
    for p in ro:
        p = str(Path(os.path.expanduser(str(p))).resolve())
        if os.path.exists(p):
            a += ["--ro-bind", p, p]
    for p in rw:
        p = str(Path(os.path.expanduser(str(p))).resolve())
        os.makedirs(p, exist_ok=True) if not os.path.exists(p) else None
        a += ["--bind", p, p]
    for k, v in (env or {}).items():
        a += ["--setenv", k, str(v)]
    if cwd:
        a += ["--chdir", str(cwd)]
    return a + ["--"] + list(cmd)
