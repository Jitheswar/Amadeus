# Hardware: GPU, power, displays, audio, network, Bluetooth

Read this before touching drivers, power behaviour or devices.

## GPU

- In automatic mode the desktop runs on the integrated GPU and single applications are
  sent to the dedicated one, NVIDIA or AMD (`amadeus-gpu-run`, or the launcher does it for
  games). Only the user's explicit choice through `amadeus-gpu set dedicated` puts it in
  charge of everything; `amadeus-gpu set integrated` keeps it asleep.
- Never run a tool that wakes the NVIDIA card just to read its state. `sys_status` and
  the map read it from sysfs.
- A GPU mode change takes effect at the next login. Say so.

## Power

- `sys_power_profile` reads or sets the profile. Do not install another power manager
  beside the one the system uses; `ama doctor` flags conflicts.
- Battery, thermals and failed services are in `sys_status`.

## Devices

- Displays: `amadeus-display`, or `desktop_settings` for scale. A display the user never
  set up gets its scale and text size chosen automatically at session start; a setting
  made by hand always wins, so change it rather than fighting the automatic choice.
- Audio: the bar's sound control lists real inputs and outputs. For faults, check the
  user's audio services with `sys_services` (user scope).
- Network: `net_status` reads, `net_control` changes. Bluetooth: `bluetooth_control`.
- A device that is missing in a virtual machine or the Try session is usually just
  absent. Check that the hardware exists before calling it a fault.

## Drivers

- `amadeus-hardware` lists what was detected; `amadeus-hardware missing` names drivers
  that should be installed and are not. `amadeus-hardware setup` installs them and applies
  the hardware's settings; it needs root, a snapshot first, and a restart afterwards.
- A new graphics card or a moved disk is handled the same way: run the setup, then restart.

## Pitfalls

- Driver, kernel-parameter and boot changes need root mode, a snapshot first, and a
  restart. Confirm before each.
- Start with `ama doctor`: it separates real failures from notes that are expected in
  the Try session.
