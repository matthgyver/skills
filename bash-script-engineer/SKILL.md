---
name: bash-script-engineer
description: Use this skill whenever the user asks to write, generate, or refactor a bash/shell script (.sh), or describes automation, deployment, backup, cleanup, or system-administration tasks that should become a bash script. It enforces a consistent, production-grade structure for every script produced — config-file overloading (.env by default, overridable), colored output, --dry-run/--verbose/--help flags, automatic timestamped backups before any file modification, and both an interactive mode and a flag-driven mode. Trigger this even if the user only asks for "a quick script" or "a one-liner" that touches files, config, or system state — the standard applies regardless of how small the request sounds.
---

# Bash Script Engineer

This skill defines the house style for every bash script Claude writes. The
goal is that any two scripts written under this skill feel like they came
from the same senior engineer: same flags, same log format, same safety
rails — so whoever runs them next (including the user, six months later)
never has to relearn how the script behaves.

## Workflow

1. Copy `scripts/template.sh` to the target filename rather than writing a
   script from scratch. It already implements every requirement below and
   is heavily commented — read it once, then fill in the `TODO` sections
   and delete what genuinely doesn't apply (e.g. drop the backup helper
   entirely for a script that never touches files).
2. Fill in the script-specific defaults, config keys, argument handling,
   interactive prompts, and main logic.
3. Run `shellcheck` on the result if it's available (`shellcheck ./script.sh`)
   and fix anything it flags. If it's not installed, at minimum re-read the
   script once looking specifically for unquoted variables and unchecked
   command substitutions.
4. Do a mental (or actual, with `--dry-run`) walkthrough of the happy path
   and at least one failure path (missing file, bad permission, interrupted
   run) before handing the script back.

Below is the reasoning behind each required behavior — read it so
customizations stay consistent with the intent, not just the letter, of the
template.

## Required behaviors and why

### Config file overloading

Every script must accept its settings in three layers, each overriding the
last: **built-in defaults → config file → CLI flags**. The config file
defaults to `.env` in the working directory but must always be redefinable
with `-c/--config FILE`. This lets the exact same script run unmodified
across environments (dev/staging/prod) just by pointing it at a different
file, while still allowing a one-off override from the command line without
editing any file.

The template loads the config file by reading it line-by-line as `KEY=VALUE`
pairs and only assigning to variables that already exist as a default —
never by `source`-ing it. A config file is data, not code; `source`-ing an
`.env` would let it execute arbitrary commands, which is a real risk if the
file ever comes from a shared repo or a less-trusted teammate.

The template's `parse_args` function is written so it can safely be called
twice — once before loading the config (to learn `--config`'s value) and
once after (so any flag actually typed on the command line wins over the
config file). Because the function only touches a variable when its flag is
present in `argv`, calling it again with the same arguments is safe and is
exactly what produces the defaults → config → CLI precedence.

### Color

All user-facing output goes through `log_info` / `log_success` /
`log_warn` / `log_error` / `log_debug`, never raw `echo`. Color makes
scanning a long run's output dramatically faster (errors in red jump out
immediately), but it must degrade gracefully: colors are auto-disabled when
stdout isn't a terminal (piped to a file, run in CI, etc.) or when
`NO_COLOR` is set, and can always be force-disabled with `--no-color`. Never
hardcode raw ANSI escapes inline in script logic — always go through the
`COLOR_*` variables so this stays centrally controllable.

### `--dry-run`, `--verbose`, `--help`

- **`--dry-run` / `-n`**: any command that changes state (writes a file,
  deletes something, calls an API, restarts a service) must be routed
  through the `run_cmd` wrapper instead of being called directly. This is
  what makes dry-run trustworthy — there's a single choke point, so nothing
  can slip through and run unintended.
- **`--verbose` / `-v`**: gates `log_debug` output. Verbose should show
  *why* the script is doing what it's doing (variable values, decisions
  taken), not just repeat what already prints normally.
- **`--help` / `-h`**: always present, always accurate, and generated from
  the same option list the parser actually implements — update `usage()`
  the moment a flag is added or removed so it never drifts out of sync.

### Backups before modifying files

Any script that edits, overwrites, or deletes a file must support
`-b/--backup`. When enabled, `backup_file <path>` copies the file into a
`backups/` subdirectory next to it (created automatically if missing)
before the modification happens, with a timestamped filename in
`DDMMYYYY-HH-MM` format (e.g. `myfile.conf.05092026-14-32.bak`), so a
mistaken run can always be undone by hand. Call `backup_file` immediately
before the modifying command, not at the top of the script, so the
backup reflects the file's state right before that specific change.
Backups respect `--dry-run` too — they only print what *would* be backed
up rather than actually copying anything.

### Interactive mode and flag mode

Every script must work two ways:
- **Flag mode**: all behavior configurable via CLI flags / config file, for
  scripting and automation (cron, CI, calling from other scripts).
- **Interactive mode** (`-i/--interactive`): prompts for the important
  choices with `read`, showing the current default and accepting Enter to
  keep it. This is what makes the script approachable for someone running
  it by hand who doesn't want to memorize flags.

Interactive mode should only ask about things that matter for that run —
don't prompt for every single variable if most have sensible defaults; ask
about the ones a human would actually want to weigh in on (destructive
actions, target paths, yes/no confirmations).

## Additional conventions applied by the template

These weren't explicitly requested but are standard practice for
production-quality bash and are included by default — mention them to the
user if they ask what else the skill adds, and drop any that genuinely
don't fit the task:

- `set -euo pipefail` and `IFS=$'\n\t'` at the top, so failures stop the
  script instead of silently continuing with bad state.
- An `ERR` trap that reports the failing line number, and an `EXIT` trap
  that cleans up any temp files registered in `TMP_FILES`.
- Logging functions write to **stderr**, keeping stdout clean for any real
  output a caller might want to pipe or capture.
- A `die()` helper for "log an error and exit 1" in one call.
- `--version` flag alongside `--help`.
- Quoting every variable expansion and using `[[ ]]` over `[ ]` throughout.
- Confirming destructive actions in interactive mode via `prompt_yn`
  (defaults to "no" for anything destructive).

## When a script doesn't need every feature

Not every script touches files (skip backups) or has enough moving parts to
warrant interactive prompts beyond the standard ones already in the
template. Keep the parts that don't apply out of the final script rather
than leaving dead code — but keep the *pattern* (config loading, logging,
dry-run, help) even in a short script, since consistency across scripts is
the whole point of this skill. If a request is genuinely a 5-line one-liner
with no state change and no config, it's fine to say so and offer the plain
version alongside the full-template version, letting the user pick.
