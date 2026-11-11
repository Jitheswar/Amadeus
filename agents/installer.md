# Changing the installer and the package set

Read `AGENTS.md` first.

`installer/` is the definition of the system: the package lists say what is on it, and
`installer/amadeus-install` says how the disk is laid out and configured.

## Rules

- **Every package needs a reason.** A package goes in only if a requirement in
  `README.md` needs it or a listed package cannot work without it. Add it to the list
  whose header comment matches, and extend that comment if the reason is not obvious.
  Removing a package is as welcome as adding one.
- **Lists, not script bodies.** The script reads the lists. It does not name packages,
  except where a package is conditional on detected hardware.
- **Applications outside the Arch repositories** go in the list for those. Each must have
  a recipe that downloads the publisher's own release; read the recipe before adding it.
  No third-party package repository is ever added to the installed system.
- **The installer erases a disk.** Interactive runs must make the user type the disk
  name. Nothing may weaken that prompt. Unattended mode exists for the VM harness.
- **Recovery is a feature of the layout.** Subvolume names, the copy of the boot
  partition inside the root filesystem, and snapshot hooks are relied on by
  `desktop/bin/amadeus-rollback`. Change them together or not at all.
- Settings written into the new system belong in a file under a `.d` directory when the
  program supports one, so the package's own file stays untouched.

## Checking your change

`./build.sh check`, then `./build.sh iso` and `./build.sh test`. An installer change
that has not been through the VM is not finished. Never try it on a real disk yourself.
