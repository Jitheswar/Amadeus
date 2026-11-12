# Build and test environment for the Amadeus OS ISO. Nothing is installed on the host.
# The second package line is for ./build.sh preview (a headless compositor to draw the shell in)
# and ./build.sh usb (a window to show the installer in).
FROM archlinux:latest
RUN pacman -Syu --noconfirm --needed archiso base-devel git python qemu-base qemu-hw-display-virtio-gpu qemu-hw-display-virtio-vga qemu-hw-display-virtio-gpu-gl qemu-hw-display-virtio-vga-gl qemu-ui-egl-headless qemu-ui-opengl edk2-ovmf dosfstools mtools rsync \
    qemu-ui-gtk sway grim quickshell qt6-wayland foot libnotify inter-font ttf-jetbrains-mono noto-fonts \
 && useradd -m build && pacman -Scc --noconfirm
