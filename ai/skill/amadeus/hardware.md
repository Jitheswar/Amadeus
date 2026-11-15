# Hardware: GPU, power, displays, audio, network, Bluetooth

Read this before touching drivers, power behaviour or devices.

## GPU

- In automatic mode the desktop runs on the integrated GPU and single applications are
  sent to NVIDIA (`amadeus-gpu-run`, or the launcher does it for games). Only the user's
  explicit choice through `amadeus-gpu` puts NVIDIA in charge of everything.
- Never run a tool that wakes the NVIDIA card just to read its state. `sys_status` and
  the map read it from sysfs.
- A GPU mode change takes effect at the next login. Say so.

## Power

- `sys_power_profile` reads or sets the profile. Do not install another power manager
  beside the one the system uses; `ama doctor` flags conflicts.
- Battery, thermals and failed services are in `sys_status`.

## Devices

- Displays: `amadeus-display`, or `desktop_settings` for scale.
- Audio: the bar's sound control lists real inputs and outputs. For faults, check the
  user's audio services with `sys_services` (user scope).
- Network: `net_status` reads, `net_control` changes. Bluetooth: `bluetooth_control`.
- A device that is missing in a virtual machine or the Try session is usually just
  absent. Check that the hardware exists before calling it a fault.

## Pitfalls

- Driver, kernel-parameter and boot changes need root mode, a snapshot first, and a
  restart. Confirm before each.
- Start with `ama doctor`: it separates real failures from notes that are expected in
  the Try session.
