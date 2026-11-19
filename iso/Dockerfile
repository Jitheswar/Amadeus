# Build and test environment for the Amadeus OS ISO. Nothing is installed on the host.
# The second package line is for ./build.sh preview (a headless compositor to draw the shell in)
# and ./build.sh usb (a window to show the installer in). The third is what ./build.sh system's tests call.
FROM archlinux:latest
RUN pacman -Syu --noconfirm --needed archiso base-devel git python qemu-base qemu-hw-display-virtio-gpu qemu-hw-display-virtio-vga qemu-hw-display-virtio-gpu-gl qemu-hw-display-virtio-vga-gl qemu-ui-egl-headless qemu-ui-opengl edk2-ovmf dosfstools mtools rsync \
    qemu-ui-gtk sway grim sddm librsvg wtype quickshell qt6-wayland foot libnotify inter-font ttf-jetbrains-mono noto-fonts \
    jq lua ripgrep nodejs imagemagick socat libxkbcommon mise glib2 ffmpeg tmux openssh inotify-tools chromium libarchive gum sudo bc \
 && systemd-machine-id-setup && useradd -m build && install -d -m 700 -o build -g build /run/user/$(id -u build) && pacman -Scc --noconfirm
