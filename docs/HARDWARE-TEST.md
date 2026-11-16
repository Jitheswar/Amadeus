# First run on real hardware: what to test

Everything below has only been checked in a virtual machine or in unit tests, or not at
all. This file is the list to work through the first time Amadeus OS runs on the target
laptop. It is written so an AI agent on that machine can follow it with the user.

When a section is done, its result goes into the [README](../README.md#verification) and
the [roadmap](ROADMAP.md), and the section is removed from this file. An empty file
means the hardware pass is finished.

## How to work through this

- Read the `troubleshooting` and `hardware` guides first (`ama guide`).
- Go in order. The baseline comes first because a fault there explains later failures.
- **You** marks a step only the user can do: something to look at, press, plug in or
  sign in to. Ask for it, wait, and write down what they report in their words.
- Write each result as you get it into `~/amadeus-hardware-results.md`: the step, what
  was run, what was seen, and one of **works**, **fails** or **not tested** with the
  reason. Never write "works" for something that was not observed.
- A failure is a result, not a task. Record it with the evidence (the command, its
  output, the journal lines) and go on. Do not repair the system during the pass
  unless the user asks: a repair hides what the shipped system does.
- Do not wake the NVIDIA card to look at it. Read sysfs, `sys_status` or `ama status`.
- Nothing here needs root mode except where a step says so. Ask before turning it on.

## 1. Baseline

1. Record the machine: `fastfetch`, the kernel, and `pacman -Q amadeus amadeus-desktop`.
2. `ama doctor`. Record every line that is not a pass.
3. `systemctl --failed` and `systemctl --user --failed`. Both should be empty.
4. `journalctl -b -p warning`. Record errors that name a driver, firmware or a device.
5. Was the install online or offline, and were Optional extras chosen? **You**
6. Did the guided installer show anything confusing or wrong? Disk choice, password
   entry, the final summary, the first restart. **You**

## 2. Graphics and the two GPUs

1. `amadeus-gpu` should report automatic mode on a fresh install.
2. With nothing demanding running, the NVIDIA card's `power/runtime_status` in sysfs
   should read `suspended` within a minute of login. If it stays `active`, find what
   holds it (the journal, and which processes have its device node open) without
   running a tool that queries the card.
3. Start a graphical program with `amadeus-gpu-run`. While it runs the card's
   `power/runtime_status` should read `active`; after it closes, `suspended` again
   within a minute. Started without `amadeus-gpu-run`, the same program should leave
   the card asleep.
4. A game or a 3D program from the launcher: does it run on NVIDIA, and smoothly? **You**
5. `amadeus-gpu set nvidia`, log out and in: is the desktop drawn by NVIDIA, and is
   anything broken (bar, panel, screen sharing, video)? Then the same for `intel`,
   then back to `auto`. Each change needs a new login. **You**
6. External display, if one is available: plug it in, check `amadeus-display`, unplug
   it. Note which GPU the port belongs to. **You**

## 3. Power, battery and sleep

1. On battery with the desktop idle, read the draw from the battery's `power_now` in
   sysfs a few times over five minutes. Record the range, the brightness and the profile.
2. `sys_power_profile` for each profile: does the draw or the fan change? **You**
3. Close the lid for a minute and open it. Does it sleep, wake, ask for the password,
   and are Wi-Fi, Bluetooth, sound and the NVIDIA state right afterwards? **You**
4. The same from the power menu. Then leave it asleep for an hour and record the
   battery percentage before and after. **You**
5. Does the bar show the battery, and does the low-battery notice appear? **You**
6. On mains under load: is `nvidia-powerd` running, and does the card take more power
   than on battery (Dynamic Boost)?

## 4. Wi-Fi, Bluetooth, sound, input

1. `amadeus-wifi list`, then connect to a network from the bar. **You**
2. Does the connection come back by itself after a restart and after sleep? **You**
3. Bluetooth from the bar: pair a device, play sound through it, reconnect after sleep. **You**
4. Speakers, headphone socket, internal microphone, and the bar's device list. **You**
5. Function keys: brightness, volume, mute, microphone mute, keyboard backlight. **You**
6. Touchpad: tap, two-finger scroll, gestures. Webcam in any application. **You**

## 5. The desktop by hand

1. Copy and paste shortcuts in a terminal, a browser and a text editor. **You**
2. Was the scale and text size chosen at first login sensible for this panel? Record
   what `amadeus-display scale` and `amadeus-display text` report. **You**
3. Change the theme and look at the shell, an open terminal, a GTK application, the
   lock screen and the login screen. **You**
4. Screenshot, screen recording with sound, and screen sharing in a browser call. **You**
5. The menu, launcher and panel: is motion smooth, and does anything flicker? **You**
6. Log out and in. If there is more than one account, try the profile chooser. **You**

## 6. The AI layer with a real model

Until now every AI check used a scripted model.

1. Sign in to one subscription provider and one API provider. Record what was needed
   and anything that did not match what Settings or `ama provider` said. **You**
2. A read-only request ("what is using my memory?"). Did it use the tools, and was the
   answer right?
3. A change that asks ("add a clock after the workspaces in the bar"). Was the approval
   clear, did the change happen, and does Undo put it back? **You**
4. Stop a long request from the panel, once for each kind of provider. The provider's
   process should be gone afterwards; check with `ama status` and the process list.
5. Each execution mode with the same small request: ask, sandbox, automatic.
6. In automatic mode, ask it to add a note to its own memory file with a file tool.
   It must still ask. This guard was added without a run on an installed system.
7. A goal that takes two or three rounds. Were the notes useful, and did it finish
   only after checking?
8. Trigger a notice (stop a harmless user service so that it fails) and click it. Does
   the panel open with the request? **You**
9. `desktop_observe` on a real application, then one approved action. Was the consent
   clear, and was the model's reading of the window right? **You**
10. `ama usage` after these: are the limits and token counts plausible?
11. Did the model read a guide before working in an area? `ama audit` shows the
    `system_guide` calls. The `files`, `screen` and `troubleshooting` guides have never
    been read by a live model: note anything in them that misled it.

## 7. Updates, mirrors and rollback

Do this last, on mains power, with nothing unsaved.

1. `amadeus-mirrors --print`. The Arch and CachyOS lists should name mirrors that are
   near this connection. Record them and how long it took. The ranking was checked
   in a container only.
2. `amadeus-update` in a terminal. Record the snapshot number, how long the mirror
   step took, and any package or AUR failure. **You**
3. Restart. Repeat the Baseline steps 2 to 4 and compare.
4. `amadeus-rollback`, choose the snapshot from before the update, restart. Is it the
   old system, and does it still work? Then update again. **You**
5. Start the install medium and run `amadeus-rollback` there against the installed
   disk, including the disk password prompt. **You**
6. With root mode on, ask the AI to install and then remove one small package. Record
   the snapshot numbers it reports and check that they exist.

## 8. When the pass is done

1. Give the user `~/amadeus-hardware-results.md` and a short list: what fails, what
   was not tested and why.
2. The results belong in the repository, written by whoever next works on it there:
   the README's verification account, the roadmap, and a fix or an issue per failure.
