"""ama doctor: verify the machine against what Amadeus expects. Read-only.
Never wakes the NVIDIA card unless run as `ama doctor --gpu`."""
import glob, os, shutil, subprocess, sys
from pathlib import Path
from . import config, audit, root

OK, WARN, BAD = ("\033[32m ok \033[0m", "\033[33mnote\033[0m", "\033[31mFAIL\033[0m") if sys.stdout.isatty() else (" ok ", "note", "FAIL")
results = []


def check(title, state, detail=""):
    results.append(state)
    print(f"[{state}] {title}" + (f" — {detail}" if detail else ""))


def out(*argv, timeout=20):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def rd(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return ""


def have(pkg):
    return subprocess.run(["pacman", "-Qq", pkg], capture_output=True).returncode == 0


def main():
    print("Base system")
    fs = out("findmnt", "-no", "FSTYPE", "/")
    check("root filesystem is btrfs", OK if fs == "btrfs" else BAD, fs)
    check("snapshot config for /", OK if os.path.exists("/etc/snapper/configs/root") else BAD)
    check("automatic snapshots around package changes", OK if have("snap-pac") or out("systemctl", "is-active", "limine-snapper-sync") == "active" else WARN)
    check("compressed swap in RAM (zram)", OK if "zram" in rd("/proc/swaps") else WARN)
    check("microcode loaded", OK if "microcode" in rd("/proc/cpuinfo") else WARN)
    failed = out("systemctl", "--failed", "--no-legend", "--plain")
    check("no failed system units", OK if not failed else WARN, failed.replace("\n", "; ")[:120])

    print("\nGraphics")
    nv = next((Path(d).parent for d in glob.glob("/sys/bus/pci/devices/*/vendor") if rd(d) == "0x10de" and rd(Path(d).parent / "class").startswith("0x03")), None)
    if not nv:
        check("NVIDIA card", WARN, "none in this machine; NVIDIA checks skipped")
    else:
        check("NVIDIA driver loaded", OK if os.path.isdir("/sys/module/nvidia") else BAD, rd("/sys/module/nvidia/version"))
        check("NVIDIA kernel modesetting", OK if rd("/sys/module/nvidia_drm/parameters/modeset") == "Y" else WARN)
    if nv:
        ctl, st = rd(nv / "power/control"), rd(nv / "power/runtime_status")
        check("NVIDIA runtime power management", OK if ctl == "auto" else BAD, f"control={ctl}, currently {st}")
    panel = [rd(Path(c).parent / "device/device/vendor") for c in glob.glob("/sys/class/drm/card*-eDP-*/status")]
    check("laptop panel is driven by the Intel GPU", OK if panel and all(v == "0x8086" for v in panel) else WARN, "desktop renders on integrated graphics")
    forced = [k for k in ("__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME", "LIBVA_DRIVER_NAME", "AQ_DRM_DEVICES", "DRI_PRIME") if os.environ.get(k)]
    check("no global variable forces apps onto NVIDIA", OK if not forced else BAD, ", ".join(forced))
    icd = os.listdir("/usr/share/vulkan/icd.d") if os.path.isdir("/usr/share/vulkan/icd.d") else []
    check("Vulkan drivers: Intel + NVIDIA", OK if any("intel" in i for i in icd) and (not nv or any("nvidia" in i for i in icd)) else BAD, ", ".join(sorted(icd)))
    check("32-bit Vulkan/GL for Steam and Proton", OK if have("lib32-vulkan-intel") and (not nv or have("lib32-nvidia-utils")) else BAD)
    check("Intel video decode (VA-API)", OK if os.path.exists("/usr/lib/dri/iHD_drv_video.so") else BAD, "intel-media-driver")
    if nv:
        check("NVIDIA video decode (VA-API over NVDEC)", OK if have("libva-nvidia-driver") else WARN)
    check("CUDA toolkit", OK if have("cuda") else WARN, "" if have("cuda") else "not installed (about 5 GB); install when needed: pacman -S cuda cudnn")
    if "--gpu" in sys.argv:
        smi = out("nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader")
        check("NVIDIA responds", OK if smi else BAD, smi)

    print("\nPower and thermals")
    check("power profiles daemon", OK if out("systemctl", "is-active", "power-profiles-daemon") == "active" else WARN, out("powerprofilesctl", "get"))
    check("thermald", OK if out("systemctl", "is-active", "thermald") == "active" else WARN)
    check("no conflicting power managers", OK if not (have("tlp") or have("auto-cpufreq")) else BAD)

    print("\nSandbox and security")
    sb = subprocess.run(["bwrap", "--unshare-all", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib64", "--symlink", "usr/bin", "/bin", "/usr/bin/true"], capture_output=True)
    check("bubblewrap sandbox works", OK if sb.returncode == 0 else BAD, sb.stderr.decode()[:100])
    check("root mode is off", OK if not root.enabled() else WARN, "" if not root.enabled() else "on until shutdown or `ama root off`")
    check("root helper installed (root-owned)", OK if os.path.exists("/usr/lib/amadeus/amadeus-priv") and os.stat("/usr/lib/amadeus/amadeus-priv").st_uid == 0 else WARN,
          "" if os.path.exists("/usr/lib/amadeus/amadeus-priv") else "the amadeus system package is not installed, so `ama root on` is unavailable")
    ok, n, bad = audit.verify()
    check("audit log chain", OK if ok else BAD, f"{n} records")
    sec = config.CONFIG / "secrets"
    check("secrets directory is private", OK if not sec.exists() or (sec.stat().st_mode & 0o077) == 0 else BAD)

    print("\nAI providers")
    cfg = config.load()
    check("daemon running", OK if config.SOCK.exists() else BAD)
    check("Claude subscription (claude CLI)", OK if shutil.which("claude") else WARN)
    codex = shutil.which("codex") and subprocess.run(["codex", "--version"], capture_output=True).returncode == 0
    check("Codex subscription (codex CLI)", OK if codex else WARN, "" if codex else "not installed or broken shim")
    for name, p in sorted(cfg["providers"].items()):
        if p["type"] in ("anthropic", "openai") and p.get("key_env"):
            check(f"API key for {name}", OK if config.secret(p, name) else WARN, "" if config.secret(p, name) else f"ama provider key {name}")
    print(f"       active provider: {cfg['ai']['provider']}")

    print("\nApplications")
    apps = {"brave-origin": "Brave Origin", "steam": "Steam", "protonplus": "ProtonPlus", "claude-desktop": "Claude Desktop", "claude": "Claude Code",
            "discord": "Discord", "Telegram": "Telegram", "nautilus": "Files (Nautilus)", "foot": "Terminal (foot)", "herdr": "herdr",
            "papers": "Documents (Papers)", "imv": "Images (imv)", "libreoffice": "LibreOffice", "localsend": "LocalSend", "mpv": "mpv",
            "snapshot": "Camera (Snapshot)", "git": "git", "gh": "GitHub CLI"}
    missing = [label for exe, label in apps.items() if not shutil.which(exe)]
    check(f"{len(apps) - len(missing)}/{len(apps)} essential applications present", OK if not missing else WARN, "missing: " + ", ".join(missing) if missing else "")

    bad_n = sum(r == BAD for r in results)
    print(f"\n{len(results)} checks, {bad_n} failed, {sum(r == WARN for r in results)} notes.")
    sys.exit(1 if bad_n else 0)
