# Building and testing

Read `AGENTS.md` first.

`build.sh` is the entry point; its header lists the subcommands. `iso/` holds the image
build and what is added to the live medium. `test/` holds the VM harness and the
self-test that runs inside the installed system.

## Rules

- **Nothing is installed on the machine doing the build.** Builds run in the container
  defined in `iso/Dockerfile`; the system under test runs in a VM. If you need a tool,
  add it to the container, not to your machine.
- **`./build.sh check` needs no container** and must stay fast: syntax, unit tests, and
  the guide checks in `test/check.py`. Put slow things in the VM test.
- **The self-test is the definition of "works".** `test/selftest.sh` runs on the
  installed system at first boot, then again after each rollback. A check must test the
  behaviour, print something useful when it fails, and never depend on hardware the VM
  lacks.
- **The VM has no NVIDIA card, no battery and no Wi-Fi.** A passing VM test says nothing
  about them. Say so when you report a result.
- **Verdicts come from files, not the console.** The harness reads logs the guest writes
  to the answers disk. Keep it that way.
- **`./build.sh preview` shows what the shell looks like**, not how windows behave: it
  runs in a stand-in compositor with a scripted model. Motion can only be judged on a
  real session.
- **To try a compositor or package question quickly**, use `./build.sh shell` and install
  what you need inside the container.
- The harness reuses downloaded packages from the build machine's cache read-only. It
  must never write to it.

## Reading a failure

Start from the first failing line, not the last. The logs are in `out/vm/`. Fix the
system if the system is wrong and the test if the test is wrong, and say which it was in
the commit.
