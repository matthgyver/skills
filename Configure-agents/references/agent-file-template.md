# AGENTS.md / CLAUDE.md template and writing guide

This is the first file an agent reads when it starts working in the repository. It must be short enough to fully absorb before doing anything else, and directive enough that the agent doesn't have to guess. Think "onboarding doc for a very fast, very literal new hire with zero context and no memory of the last session."

Keep this file under roughly 150 lines. Anything that needs more depth belongs in `ARCHITECTURE.md` or a sub-agent file, referenced from here - not inlined.

## Template

```markdown
# <Project name> - Agent Instructions

## What this is

1-2 sentences on what the project does and who/what uses it.

## Setup

\`\`\`bash
<exact install command, verified against manifest files>
\`\`\`

## Common commands

| Task | Command |
|---|---|
| Run locally | `...` |
| Run tests | `...` |
| Run a single test | `...` |
| Lint | `...` |
| Format | `...` |
| Build | `...` |

## Before you make changes

- <Project-specific rule, e.g. "Run `npm run lint` before committing - CI will reject unlinted code.">
- <e.g. "New DB changes always go through a migration file in `migrations/`, never a manual schema edit.">
- <e.g. "This repo uses conventional commits.">

## Directory guide

Short version of the architecture doc's directory guide - just enough to route a task to the right place. Link to `ARCHITECTURE.md` for the full picture.

| Path | Purpose |
|---|---|
| `src/api/` | HTTP routes |
| `src/services/` | Business logic |
| `tests/` | Test suite, mirrors `src/` structure |

## Boundaries

Things an agent should not do without explicit confirmation, e.g.:
- Don't modify files under `vendor/` or `generated/` - they're not hand-maintained.
- Don't change public API signatures in `src/api/` without flagging it - they're versioned/consumed externally.
- Don't touch `infra/` (Terraform) without human review.

## For deeper context

- Full architecture and system design: see `ARCHITECTURE.md`.
- Specialized work: see the sub-agents in `.agents/` - <one-line pointer to when to use each, e.g. "use `backend-api-agent` for anything under `src/api/` or `src/services/`, `frontend-agent` for `src/ui/`.">

## Keeping this documentation current

`ARCHITECTURE.md` and this file are generated from a point-in-time analysis - they do not update themselves. If your change adds, removes, or moves a module; changes a documented flow (see `ARCHITECTURE.md` "Key flows"); adds an external integration; or changes a command listed above, update the relevant section of `ARCHITECTURE.md` (and this file, if the command/directory guide is affected) as part of the same task, before considering the task done. Small internal refactors that don't change the documented shape of the system don't need a doc update.
```

## Writing guidance

- **Verify every command.** Pull install/test/build/lint commands from the actual manifest (`package.json` scripts, `Makefile`, `pyproject.toml`, CI config) rather than assuming the framework's defaults - projects deviate from defaults often enough that this matters.
- **State boundaries explicitly.** Agents will happily edit generated code, vendored dependencies, or public API contracts unless told not to - list these deviations if the project has them.
- **Don't duplicate `ARCHITECTURE.md`.** This file routes and directs; the architecture doc explains. If you find yourself writing more than a couple of sentences on *why* something is structured a certain way, that content belongs in `ARCHITECTURE.md` with a link from here.
- **Update, don't overwrite blindly.** If an `AGENTS.md`/`CLAUDE.md` already exists, preserve any project-specific rules a maintainer has already written into it - merge in what's missing rather than replacing it wholesale.
- **Always include the "Keeping this documentation current" section.** These files aren't regenerated automatically - the only thing that keeps them from going stale as coding agents modify the project is an explicit instruction to update them when a structural change is made. Don't drop this section, and don't water it down to "keep docs up to date" - it needs to say *what kinds of changes* trigger an update, or it will be ignored in practice.
