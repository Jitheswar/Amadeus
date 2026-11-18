# Symbolizing a Backtrace

This is Arch, which runs a public debuginfod server:

```bash
core=$(mktemp -t crash-XXXXXX.core)
trap 'rm -f "$core"' EXIT
coredumpctl dump <pid> --output="$core"
DEBUGINFOD_URLS="https://debuginfod.archlinux.org" \
  gdb -q <executable> "$core" \
  -batch -ex 'set debuginfod enabled on' -ex 'bt'
```

A core is a verbatim copy of the process's memory and can hold passwords, tokens,
and private documents. Write it to a fresh `mktemp` path rather than a predictable
shared one, and delete it when you are done — never leave it lying in `/tmp`.

Many packages publish no debug symbols. When frames stay unresolved, say so —
never invent function names to fill the gap. An unsymbolized stack still has
shape: which library each frame belongs to, and whether the crash came from a
signal handler, a main loop, or a worker thread.
