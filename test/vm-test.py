#!/usr/bin/python3
"""End-to-end test of the ISO in QEMU/KVM (runs inside the builder container).
Phase 1 boots the ISO through UEFI and lets it install unattended onto an empty disk.
Phase 2 boots that disk, unlocks it, logs into the desktop and runs the self-test."""
import glob, os, select, shutil, subprocess, sys, time

OUT, SRC = "/out", "/src/test"
VM = f"{OUT}/vm"
PASSWORD = "test-pass-123"
extras = "no" if "--no-extras" in sys.argv else "yes"
phase = next((a.split("=")[1] for a in sys.argv if a.startswith("--phase=")), "all")
iso = sorted(glob.glob(f"{OUT}/amadeus-os-*.iso"))[-1]
os.makedirs(VM, exist_ok=True)
disk, auto, nvram = f"{VM}/disk.qcow2", f"{VM}/auto.img", f"{VM}/OVMF_VARS.fd"

BASE = ["qemu-system-x86_64", "-enable-kvm", "-machine", "q35", "-cpu", "host", "-smp", "6", "-m", "6G",
        "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd",
        "-drive", f"if=pflash,format=raw,file={nvram}",
        "-drive", f"file={disk},if=virtio,format=qcow2,discard=unmap",
        "-drive", f"file={auto},if=virtio,format=raw",
        "-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0",
        "-monitor", "none", "-serial", "stdio", "-no-reboot"]
# The compositor needs 3D acceleration. Use an Intel render node from the machine running the test when there is one.
node = next((f"/dev/dri/{os.path.basename(r)}" for r in sorted(glob.glob("/sys/class/drm/renderD*"))
             if open(f"{r}/device/vendor").read().strip() == "0x8086"), None)
BASE += ["-device", "virtio-vga-gl", "-display", f"egl-headless,rendernode={node}"] if node else ["-device", "virtio-vga", "-display", "none"]


def run(cmd, log, timeout, feed=None, until=None):
    """Run QEMU, mirror the serial console to a log, optionally answer a prompt."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    os.set_blocking(p.stdout.fileno(), False)
    buf, t0, fed = b"", time.time(), False
    with open(log, "wb") as f:
        while p.poll() is None and time.time() - t0 < timeout:
            if select.select([p.stdout], [], [], 2)[0]:
                chunk = p.stdout.read() or b""
                f.write(chunk); f.flush()
                buf = (buf + chunk)[-4000:]
                if feed and not fed and feed[0].encode() in buf:
                    time.sleep(1)
                    p.stdin.write((feed[1] + "\n").encode()); p.stdin.flush()
                    fed = True
                if until and until.encode() in buf:
                    try:
                        p.wait(60)
                    except subprocess.TimeoutExpired:
                        pass
                    break
    if p.poll() is None:
        p.kill()
        return False, time.time() - t0
    return True, time.time() - t0


def take_from(image, name):
    out = f"{VM}/{name}"
    if os.path.exists(out):
        os.remove(out)
    subprocess.run(["mcopy", "-n", "-o", "-i", image, f"::{name}", out], capture_output=True)
    return open(out, errors="replace").read() if os.path.exists(out) and name.endswith(".log") else ""


def take(name):
    if os.path.exists(f"{VM}/{name}"):
        os.remove(f"{VM}/{name}")
    subprocess.run(["mcopy", "-n", "-o", "-i", auto, f"::{name}", f"{VM}/{name}"], capture_output=True)
    return open(f"{VM}/{name}", errors="replace").read() if os.path.exists(f"{VM}/{name}") else ""


if phase in ("all", "try"):
    # Try mode: the ISO's default entry, no disk to install onto, and a small disk the session reports onto.
    print("phase 0: try Amadeus OS from the ISO ...", flush=True)
    trydisk, tryvars = f"{VM}/try.img", f"{VM}/OVMF_VARS.try.fd"
    if os.path.exists(trydisk):
        os.remove(trydisk)
    subprocess.run(["truncate", "-s", "64M", trydisk], check=True)
    subprocess.run(["mkfs.fat", "-n", "AMADEUSTRY", trydisk], check=True, capture_output=True)
    shutil.copy("/usr/share/edk2/x64/OVMF_VARS.4m.fd", tryvars)
    trycmd, i = [], 0
    while i < len(BASE):
        if BASE[i] == "-drive" and (disk in BASE[i + 1] or auto in BASE[i + 1]):
            i += 2
            continue
        trycmd.append(BASE[i].replace(nvram, tryvars))
        i += 1
    trycmd += ["-drive", f"file={trydisk},if=virtio,format=raw", "-cdrom", iso]
    run(trycmd, f"{VM}/try-serial.log", 900)
    log = take_from(trydisk, "try.log")
    take_from(trydisk, "try.png")
    print(log[:1500] or "the try session never reported", flush=True)
    if "TRY-OK" not in log:
        sys.exit(1)
    if "dependency failures: 0" not in log:
        print("the try boot reported failed dependencies", flush=True)
        sys.exit(1)
    # The terminal, the Install menu and sound are what the try session is judged on first.
    for good in ("foot config: ok", "sound: active active active ", "aur build tools: 2"):
        if good not in log:
            print(f"the try session reported '{good}' missing", flush=True)
            sys.exit(1)
    for count in ("package lists:", "catalogue entries:"):
        line = next((l for l in log.splitlines() if l.startswith(count)), "")
        if not line or line.split(":", 1)[1].strip() in ("", "0"):
            print(f"the try session has no {count.rstrip(':')}: {line or 'no line'}", flush=True)
            sys.exit(1)

if phase in ("all", "install"):
    for f in (disk, auto, nvram):
        if os.path.exists(f):
            os.remove(f)
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", disk, "40G"], check=True)
    shutil.copy("/usr/share/edk2/x64/OVMF_VARS.4m.fd", nvram)
    subprocess.run(["truncate", "-s", "64M", auto], check=True)
    subprocess.run(["mkfs.fat", "-n", "AMADEUSAUTO", auto], check=True, capture_output=True)
    answers = f"""DISK=vda
HOSTNAME=amadeus-vm
USERNAME=tester
PASSWORD={PASSWORD}
ENCRYPT=yes
TIMEZONE=UTC
LOCALE=en_US.UTF-8
KEYMAP=us
EXTRAS={extras}
CACHE_DIR="/mnt/vmcache /mnt/hostcache"
EXTRA_CMDLINE="console=tty0 console=ttyS0,115200"
POST_HOOK=/run/amadeus-auto/posthook.sh
"""
    open(f"{VM}/answers.conf", "w").write(answers)
    for src in (f"{VM}/answers.conf", f"{SRC}/posthook.sh", f"{SRC}/selftest.sh", f"{SRC}/e2e.py"):
        subprocess.run(["mcopy", "-i", auto, src, "::"], check=True)
    # The install runs with no way out to the internet: everything must come from the ISO.
    cmd = [x.replace("user,id=n0", "user,id=n0,restrict=on") for x in BASE] + ["-cdrom", iso]
    # Downloads from this run are kept for the next one.
    os.makedirs(f"{OUT}/vmcache", exist_ok=True)
    cmd += ["-virtfs", f"local,path={OUT}/vmcache,mount_tag=vmcache,security_model=none"]
    if os.path.isdir("/hostcache"):
        cmd += ["-virtfs", "local,path=/hostcache,mount_tag=hostcache,security_model=none,readonly=on"]
    print(f"phase 1: installing from {os.path.basename(iso)} ...", flush=True)
    done, secs = run(cmd, f"{VM}/install-serial.log", 3600)
    # The verdict comes from the installer's own log on the answers disk; the serial
    # console is taken over by a login prompt partway through and is not reliable.
    if os.path.exists(f"{VM}/install.log"):
        os.remove(f"{VM}/install.log")
    subprocess.run(["mcopy", "-n", "-o", "-i", auto, "::install.log", f"{VM}/install.log"], capture_output=True)
    log = open(f"{VM}/install.log", errors="replace").read() if os.path.exists(f"{VM}/install.log") else open(f"{VM}/install-serial.log", errors="replace").read()
    ok = "Amadeus OS is installed on" in log
    print(f"phase 1: {'OK' if ok else 'FAILED'} in {secs / 60:.1f} min (vm exited: {done})", flush=True)
    if not ok:
        print(log[-3000:])
        sys.exit(1)

def boot_disk(stage, what):
    print(f"phase {stage + 1}: {what} ...", flush=True)
    run(BASE, f"{VM}/boot-serial-{stage}.log", 900, feed=("passphrase", PASSWORD))
    log = take(f"selftest-{stage}.log")
    if "AMADEUS-SELFTEST-BEGIN" in log:
        print(log[log.index("AMADEUS-SELFTEST-BEGIN"):][-6000:], flush=True)
    else:
        print("self-test never started. Console tail:\n" + open(f"{VM}/boot-serial-{stage}.log", errors="replace").read()[-2500:])
    if not ("AMADEUS-SELFTEST-END" in log and "fail=0" in log):
        print(take("desktop-debug.log")[-3000:])
        sys.exit(1)


if phase in ("all", "boot"):
    for name in ("stage", "rescue.conf", "rescue.log", "selftest-1.log", "selftest-2.log", "selftest-3.log", "desktop.png", "journal-warnings.log"):
        subprocess.run(["mdel", "-i", auto, f"::{name}"], capture_output=True)
    boot_disk(1, "first boot of the installed system")
    take("desktop.png"); take("journal-warnings.log")
    boot_disk(2, "boot after a rollback made from the running system")

    print("phase 4: rollback from the ISO ...", flush=True)
    conf = take("rescue.conf")
    open(f"{VM}/rescue.conf", "w").write(conf.strip() + f"\nLUKS_PASS={PASSWORD}\n")
    subprocess.run(["mcopy", "-o", "-i", auto, f"{VM}/rescue.conf", "::"], check=True)
    shutil.copy("/usr/share/edk2/x64/OVMF_VARS.4m.fd", f"{VM}/OVMF_VARS.iso.fd")
    cmd = [a.replace(nvram, f"{VM}/OVMF_VARS.iso.fd") for a in BASE]
    cmd += ["-drive", f"file={iso},media=cdrom,if=none,id=cd,readonly=on", "-device", "ide-cd,drive=cd,bootindex=0"]
    run(cmd, f"{VM}/rescue-serial.log", 900)
    log = take("rescue.log")
    print(log[-2500:] or open(f"{VM}/rescue-serial.log", errors="replace").read()[-2500:], flush=True)
    if "AMADEUS-RESCUE-RESULT: OK" not in log:
        sys.exit(1)
    boot_disk(3, "boot after the rollback made from the ISO")
    print("ALL PHASES PASSED")
