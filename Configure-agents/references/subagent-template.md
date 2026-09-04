# Sub-agent template and writing guide

Sub-agents live at `.agents/<name>.md` (Claude Code's subagent format: YAML frontmatter + a system prompt body). Each one is a narrow specialist scoped to one domain of the codebase, invoked automatically by an orchestrating agent based on its `description`, or explicitly by name.

## Template

```markdown
---
name: <kebab-case-name>
description: <When the orchestrator should invoke this sub-agent. Be concrete and scenario-based - this is a routing signal, not a job title. E.g. "Use for any change to REST endpoints, request validation, or the service layer under src/api/ and src/services/. Also use to investigate backend bugs or design new backend features.">
tools: <comma-separated tool names this sub-agent may use, scoped to its role - e.g. "Read, Grep, Glob, Bash, Edit" for a hands-on implementer, or "Read, Grep, Glob" for a read-only reviewer>
---

# <Sub-agent display name>

## Scope

What this sub-agent owns, in concrete terms: which directories, which layer of the system, which type of task. State what's explicitly *out* of scope too, and which sub-agent to defer to instead.

## Context

- Points to `ARCHITECTURE.md` and `AGENTS.md` for shared project context - don't restate the whole architecture doc here.
- Domain-specific facts this sub-agent needs on every invocation: key file paths, the conventions specific to this layer, relevant invariants from `ARCHITECTURE.md` section 9 that apply to this domain.

## Conventions specific to this domain

Anything this sub-agent must follow that's specific to its area and wouldn't be obvious from the root agent file - e.g. for a backend agent: "All new endpoints require a schema in `src/api/schemas/` and an integration test in `tests/api/`." For a frontend agent: "Components go in `src/ui/components/`, one component per file, co-located with a `.test.tsx`."

## Boundaries

What this sub-agent should not do without confirmation - mirrors the root `AGENTS.md` boundaries but made specific to this domain (e.g. a data/db sub-agent: "never write a migration that drops a column outright - add a deprecation step first").
```

## Choosing the sub-agent split

Derive the split from what Step 1-2 of the skill actually found in the codebase - don't apply a fixed list blindly. Common, reasonable splits:

- **By layer**: `backend-agent`, `frontend-agent`, `data-agent` - fits a classic web app.
- **By service**: one sub-agent per service in a microservices/monorepo setup - fits when services are largely independent.
- **By concern**: `feature-agent`, `test-agent`, `infra-agent` - fits when cross-cutting concerns (testing, deployment) are distinct enough from feature work to warrant their own specialist.

Guidelines:
- 3-6 sub-agents is the sweet spot for most projects. Fewer than that and the split isn't adding value over the root agent file; more than that and the orchestrator has too many similar-sounding options to choose between correctly.
- Each sub-agent's `description` is what drives automatic selection - write it as "use this when X", covering the realistic range of tasks that should route here, not just a restatement of the name.
- Scope `tools` to the role. A sub-agent that only reviews or investigates doesn't need write/execute tools; one that ships code does. Narrower tool access reduces the blast radius of a mistake.
- If the codebase is small or genuinely undifferentiated (e.g. a single-file script, a small library with no layers), it's fine to produce fewer sub-agents than the "sweet spot" above, or to note in the output that sub-agents aren't a good fit and a single `AGENTS.md` is sufficient.
