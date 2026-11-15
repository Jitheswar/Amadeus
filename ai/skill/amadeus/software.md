# Software: installing, removing, updating

Read this before any package or tool change.

## Sources, in order

1. The system repositories (`pacman`). Always first.
2. The AUR through `amadeus-aur`. Recipes are written by users: read the recipe before
   building, and never build something the repositories already carry.
3. Language runtimes and coding agents through mise, wrapped by `amadeus-harness`.
4. Web apps through `amadeus-webapp`.

The curated choices a person sees under Install are catalogue files;
`amadeus-catalog` lists the categories and resolves each entry to the first source
that exists now.

## Method

- Search and inspect with `sys_packages` (it only reads).
- Install, remove or upgrade with `pkg_manage`. It needs root mode, asks the user, and
  attempts a snapshot before and after. Report the snapshot numbers it actually
  returns; a snapshot attempt can fail.
- A full update is `amadeus-update`, run as the user in a terminal. It snapshots first
  and updates repository packages, AUR packages and tools together.
- After installing a graphical application, confirm it appears with `desktop_apps`.

## Pitfalls

- Root mode off means stop and say what is needed. Do not look for another route.
- Removing a package is destructive: name exactly what goes, including what depends on it.
- A manual `pacman` run in a terminal takes no snapshot. Take one first when it matters.
- The Try session keeps nothing after a restart and takes no snapshots.
- Never add a package inside a script; installed-by-default software is a package list.
