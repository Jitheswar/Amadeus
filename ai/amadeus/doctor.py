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
    results.clear()
    live = Path(os.environ.get("AMADEUS_TRY_MARKER", "/run/amadeus-try")).exists()
    print("Base system" + (" (temporary Try session)" if live else ""))
    fs = out("findmnt", "-no", "FSTYPE", "/")
    if live:
        check("temporary live root", OK if fs == "overlay" else WARN, fs + "; changes disappear at shutdown")
        check("system snapshots", WARN, "not used in the temporary Try session")
        usage = shutil.disk_usage("/")
        check("live writable space", WARN if usage.free < 1024**3 else OK, f"{usage.free // 1024**2} MiB free; large downloads use RAM")
    else:
        check("root filesystem is btrfs", OK if fs == "btrfs" else BAD, fs)
        check("snapshot config for /", OK if os.path.exists("/etc/snapper/configs/root") else BAD)
    check("automatic snapshots around package changes", OK if have("snap-pac") or out("systemctl", "is-active", "limine-snapper-sync") == "active" else WARN)
    check("compressed swap in RAM (zram)", OK if "zram" in rd("/proc/swaps") else WARN)
    check("microcode loaded", OK if "microcode" in rd("/proc/cpuinfo") else WARN)
    failed = out("systemctl", "--failed", "--no-legend", "--plain")
    check("no failed system units", OK if not failed else WARN, failed.replace("\n", "; ")[:120])

    print("\nGraphics")
    gpus = [Path(d).parent for d in glob.glob("/sys/bus/pci/devices/*/class") if rd(d).startswith("0x03")]
    makers = {rd(g / "vendor") for g in gpus}
    nv = next((g for g in gpus if rd(g / "vendor") == "0x10de"), None)
    hybrid = len(gpus) >= 2
    if not nv:
        check("NVIDIA card", WARN, "none in this machine; NVIDIA checks skipped")
    else:
        check("NVIDIA driver loaded", OK if os.path.isdir("/sys/module/nvidia") else BAD, rd("/sys/module/nvidia/version"))
        check("NVIDIA kernel modesetting", OK if rd("/sys/module/nvidia_drm/parameters/modeset") == "Y" else WARN)
        if hybrid:
            ctl, st = rd(nv / "power/control"), rd(nv / "power/runtime_status")
            check("NVIDIA runtime power management", OK if ctl == "auto" else BAD, f"control={ctl}, currently {st}")
    missing = out("amadeus-hardware", "missing")
    check("drivers for this hardware installed", OK if not missing else WARN, ("missing: " + missing.replace("\n", " ") + "; run amadeus-hardware setup") if missing else "")
    if hybrid:
        panel = [rd(Path(c).parent / "device/device/boot_vga") for c in glob.glob("/sys/class/drm/card*-eDP-*/status")]
        check("laptop panel is driven by the integrated GPU", OK if panel and all(v == "1" for v in panel) else WARN, "desktop renders on integrated graphics")
        forced = [k for k in ("__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME", "LIBVA_DRIVER_NAME", "AQ_DRM_DEVICES", "DRI_PRIME") if os.environ.get(k)]
        check("no global variable forces apps onto the dedicated GPU", OK if not forced else BAD, ", ".join(forced))
    icd = os.listdir("/usr/share/vulkan/icd.d") if os.path.isdir("/usr/share/vulkan/icd.d") else []
    need = [n for v, n in (("0x8086", "intel"), ("0x1002", "radeon"), ("0x10de", "nvidia")) if v in makers]
    check("Vulkan drivers for every graphics card", OK if all(any(n in i for i in icd) for n in need) else BAD, ", ".join(sorted(icd)))
    lib32 = {"0x8086": "lib32-vulkan-intel", "0x1002": "lib32-vulkan-radeon", "0x10de": "lib32-nvidia-utils"}
    have32 = all(have(lib32[m]) or (m == "0x10de" and have("lib32-nvidia-580xx-utils")) for m in makers if m in lib32)
    check("32-bit Vulkan/GL for Steam and Proton", OK if have32 else (WARN if live else BAD), "optional gaming libraries are not included on the live medium" if live else "")
    if "0x8086" in makers:
        check("Intel video decode (VA-API)", OK if os.path.exists("/usr/lib/dri/iHD_drv_video.so") or os.path.exists("/usr/lib/dri/i965_drv_video.so") else BAD, "intel-media-driver")
    if "0x1002" in makers:
        check("AMD video decode (VA-API)", OK if os.path.exists("/usr/lib/dri/radeonsi_drv_video.so") else WARN, "mesa")
    if nv:
        check("NVIDIA video decode (VA-API over NVDEC)", OK if have("libva-nvidia-driver") else WARN)
    check("CUDA toolkit", OK if have("cuda") else WARN, "" if have("cuda") else "not installed (about 5 GB); install when needed: pacman -S cuda cudnn")
    if "--gpu" in sys.argv:
        smi = out("nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader")
        check("NVIDIA responds", OK if smi else BAD, smi)

    print("\nPower and thermals")
    profile = out("powerprofilesctl", "get")
    service = out("systemctl", "is-active", "power-profiles-daemon")
    check("power profiles daemon", OK if service == "active" else WARN)
    check("power profile control", OK if profile else BAD, profile or "powerprofilesctl failed; check python-gobject and the service")
    bluetooth = out("systemctl", "is-enabled", "bluetooth.service")
    check("Bluetooth activation", OK if bluetooth == "enabled" else WARN, bluetooth)
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
    apps = {"nautilus": "Files (Nautilus)", "foot": "Terminal (foot)",
            "papers": "Documents (Papers)", "imv": "Images (imv)", "libreoffice": "LibreOffice", "mpv": "mpv",
            "snapshot": "Camera (Snapshot)", "git": "git", "btop": "btop", "fastfetch": "fastfetch"}
    missing = [label for exe, label in apps.items() if not shutil.which(exe)]
    check(f"{len(apps) - len(missing)}/{len(apps)} essential applications present", OK if not missing else WARN, "missing: " + ", ".join(missing) if missing else "")

    bad_n = sum(r == BAD for r in results)
    print(f"\n{len(results)} checks, {bad_n} failed, {sum(r == WARN for r in results)} notes.")
    sys.exit(1 if bad_n else 0)
