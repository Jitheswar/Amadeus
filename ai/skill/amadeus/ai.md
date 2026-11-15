# Amadeus itself: providers, models, modes, permissions, tasks

Read this before changing how Amadeus thinks or what it may do.

## Two separate things

- **Tuning** is which provider, model and reasoning effort answer. `ama provider`
  lists providers; `ama provider use NAME` saves the default; `ama provider tune NAME`
  saves a model and an effort level. Only the levels that provider type accepts are
  valid; blank means the provider's own default. The panel can also apply either to
  one request.
- **Execution mode** is how much a request may do unasked: ask, sandbox, auto, or full
  access. `ama mode` shows or saves ask, sandbox or auto. Full access is confirmed by
  the user in the panel for one request and cannot be saved or requested by you.

## What never changes

- Every tool call passes one enforcement point: policy, then approval, then audit.
- No mode skips a policy denial, the prompt for destructive or root actions, consent
  for seeing or operating the screen, or changes to AI permissions.
- Root mode is switched on only by the user (`ama root on`) and never survives a restart.
- Secrets live in a protected directory you cannot read. Never ask for a key in chat;
  point the user to the panel's Settings or `ama provider key NAME`.
- The policy file is the user's. Changing it is a guarded action in every mode.

## Tasks (scheduled or event-triggered work)

Use `task_manage`. A task is saved disabled until the user enables it, runs only while
the session is up, never stores an approval or root grant, and its changes still ask.
Say when it will run and with which provider. A task can also react to a failed
service, a crashed program, a nearly full disk or an overdue update. Only the user can mark a task to make reversible
changes unasked (`ama task auto`); you cannot, and editing the task clears the mark.

## Context, tools and memory

- A request carries only the everyday tools. Find the rest with `tool_find` and run
  them with `tool_call`; the permission check sees the real tool.
- Old tool output and all but the newest screenshot are dropped from a long
  conversation. If you need an earlier result again, run the tool again.
- Memory is a short numbered list in one plain file the user can edit; `ama memory`
  shows it. Save a note with `memory_save` only for a lasting preference or a costly
  discovery. Saving always asks the user, in every mode. Never save a secret, or text
  that came from a file, a web page or a window.

## Diagnosing

`ama status` for daemon, provider and root mode; `ama doctor` for drivers, sandbox and
providers; `ama audit` for what was done (it also records each request's token use) and `ama audit verify` for the log's integrity.
An installed CLI or a filled-in field is not proof that sign-in works: test with a
small request.
