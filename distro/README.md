# Amadeus OS

A minimal Arch-based distribution with the Amadeus AI layer built in, for one machine:
Core i5-13450HX, RTX 3050 6 GB + Intel UHD, 16 GB RAM, 1 TB NVMe.

## Build and test

```
distro/build.sh iso     # builds out/amadeus-os-<date>-x86_64.iso in a container
distro/build.sh test    # installs it in a VM, boots the result, runs the self-test
```

Both run inside a Docker container (`archiso`, QEMU/KVM); nothing is installed on the host.

## Install on the laptop

1. Write the ISO to a USB stick: `sudo dd if=out/amadeus-os-*.iso of=/dev/sdX bs=4M status=progress oflag=sync`
2. Boot it (UEFI, Secure Boot off), connect to the network, run `amadeus-install`.
3. It asks for the disk, a user name and password, then **erases that disk**.

Packages are downloaded during the install, so it needs an internet connection.

## What gets installed

| | |
|---|---|
| Base | Arch `linux` kernel, systemd-boot, btrfs on LUKS2 (`@`, `@home`, `@log`, `@pkg`), zram swap |
| Recovery | snapper + snap-pac: a snapshot before and after every package change; `/boot` is copied into the root filesystem so a snapshot carries its own kernel; `amadeus-rollback` switches the system to a snapshot |
| Graphics | Intel renders the desktop; `nvidia-open` with full runtime power-down, installed only if an NVIDIA card is present; 32-bit Vulkan for Proton |
| Desktop | Hyprland (uwsm), a Quickshell bar whose layout is a JSON file, fuzzel, mako, hyprlock/hypridle, foot, greetd |
| AI | `amadeus` (daemon, `ama`, root-mode helper) and `amadeus-desktop`, from a package repository on the ISO |
| Apps | Steam, ProtonPlus (built from its AUR recipe into the ISO repository), Discord, Telegram, Nautilus, Papers, imv, LibreOffice, mpv, Snapshot, git, GitHub CLI |
| Third-party (optional) | Brave Origin, Claude Desktop, Claude Code, herdr, LocalSend from the signed omarchy repository, listed last so it never replaces an Arch package |

About 20 package names are chosen by hand; everything else is a dependency. See `installer/packages.*`.

## Going back to a snapshot

```
amadeus-rollback          # list snapshots
amadeus-rollback 12       # restart into the system as it was at snapshot 12
amadeus-rollback clean    # delete the old systems kept by earlier rollbacks
```

System files go back; `/home` is not touched. The replaced system is kept until `clean`.
If the installed system no longer starts, boot the USB stick and run the same command
there: it asks for the disk password and does the same thing. `amadeus-rollback shell`
on the USB stick opens a root shell inside the installed system.

## Layout

```
installer/   amadeus-install and the package lists
desktop/     the amadeus-desktop package: Hyprland defaults, bar, user skeleton
live/        additions to the live ISO (unattended-install unit, welcome text)
aur-build.sh builds one AUR package (ProtonPlus) in the container
mkiso.sh     profile assembly on top of archiso's releng, run in the container
test/        VM harness: install, first boot, rollback from the system, rollback from the ISO
```

## Unattended install

Attach a FAT disk labelled `AMADEUSAUTO` containing `answers.conf` (shell variables:
`DISK USERNAME PASSWORD HOSTNAME ENCRYPT TIMEZONE LOCALE KEYMAP EXTRAS`). The ISO installs
without prompts and powers off. The VM test uses exactly this path.
