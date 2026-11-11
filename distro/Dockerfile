# Build and test environment for the Amadeus OS ISO. Nothing is installed on the host.
FROM archlinux:latest
RUN pacman -Syu --noconfirm --needed archiso base-devel git python qemu-base qemu-hw-display-virtio-gpu qemu-hw-display-virtio-vga qemu-hw-display-virtio-gpu-gl qemu-hw-display-virtio-vga-gl qemu-ui-egl-headless qemu-ui-opengl edk2-ovmf dosfstools mtools rsync \
 && useradd -m build && pacman -Scc --noconfirm
