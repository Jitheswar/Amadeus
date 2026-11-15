# Generated apps: small programs built on request

Read this before building or changing an app for the user.

1. Call `app_guide` first. It returns the current structure, component library, OS
   bridge and permission rules. Follow it over anything you remember.
2. `app_list` and `app_read` before writing: update an existing app by sending only the
   files that change, do not rewrite it.
3. Use the shared components and the theme values so the app looks like part of the
   system and follows a theme change. No colours or sizes of your own.
4. Ask for the fewest permissions that work. An app runs in a sandbox with only what
   its manifest declares; granting a tool or AI access is a guarded action the user
   approves.
5. `app_save`, then `app_run`, then check the app's log if it does not appear.
6. `app_rollback` restores an earlier version; `app_remove` is destructive.

An app is the right answer for a panel, a dashboard or a small tool. A one-off answer
or a single setting change is not an app.
