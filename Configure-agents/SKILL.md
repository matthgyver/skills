---
name: codebase-architecture-agent
description: >
  Analyzes a software codebase and produces three artifacts that let AI agents work in it effectively - (1) a technical architecture document written for LLM consumption, (2) a root-level agent instruction file (AGENTS.md / CLAUDE.md style), and (3) a set of scoped sub-agent definition files (Claude Code subagent format). Use this skill whenever the user asks to document a codebase's architecture for an AI, wants an AGENTS.md or CLAUDE.md generated, wants to "onboard" or "prepare" a repo for AI agents, asks to set up sub-agents for a project, or wants Claude to map out and formalize how a codebase is structured so future agent sessions ramp up fast. This also applies to phrasing in other languages, for example French requests such as "analyse cette codebase et fais un document d'architecture", "prépare ce repo pour des agents IA", or "crée-moi un fichier agent et des sous-agents".
---

# Codebase Architecture & Agent Setup

## Purpose

Given access to a codebase, produce a small set of files that let AI agents (Claude Code, Cowork, or any LLM-based coding agent) understand and work in the project without re-discovering it from scratch every session. The deliverables are optimized for a language model to *read and act on*, not for a human to skim in a slide deck.

Three deliverables, in this order:

1. **`ARCHITECTURE.md`** - a dense, factual technical architecture document.
2. **`AGENTS.md`** the root file an agent reads first when it starts working in the repo.
3. **Sub-agent files** in `.agents/*.md` - narrow, scoped agents for specific domains of the codebase (backend, frontend, infra, data, tests, etc.).

Don't skip straight to writing these from assumptions. The value of this skill comes from grounding every claim in the actual code, not from producing a plausible-looking template filled with generic boilerplate.

## Workflow

### Step 1 - Locate and inventory the codebase

Confirm what you're working with: a path already on disk, an uploaded archive, or a repository URL to fetch. If nothing is available yet, ask before proceeding - don't invent a codebase.

Once you have access, build an inventory using `bash_tool` (don't read every file - sample strategically):

- Top-level structure: `find . -maxdepth 3 -type d | sort`, or a `tree`-style listing.
- Manifest / dependency files: `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`, `composer.json`, lockfiles - these reveal language, framework, and dependency footprint precisely rather than by guessing from file extensions.
- Entry points: `main.*`, `index.*`, `app.*`, server bootstrap files, CLI entry files.
- Existing docs: `README*`, `docs/`, `CONTRIBUTING*`, any existing `CLAUDE.md`/`AGENTS.md`/`.cursorrules` - reuse and update rather than contradict what's already there.
- Config & infra: `Dockerfile`, `docker-compose*`, CI config (`.github/workflows`, `.gitlab-ci.yml`), IaC folders, env samples.
- Test setup: test folders, test runner config, coverage config.
- Size signal: rough file/line counts per top-level folder (`find <dir> -name '*.ext' | wc -l`) to gauge where the real weight of the codebase lives.
- Never read `.env` files

From this, identify: languages and frameworks, package/build system, whether it's a monolith, a monorepo, or a multi-service system, the data layer (DB, ORM, migrations), external integrations, and the testing/deployment setup.

### Step 2 - Trace representative flows

Don't infer architecture purely from folder names - verify it. Pick 2-4 flows that matter (e.g. "an incoming HTTP request end to end", "the CLI's main command", "the CI build/deploy pipeline", "how a background job gets scheduled and processed") and actually trace them through the code: which file receives the request, what it calls next, where it touches the data layer, what it returns. This is what makes the architecture doc trustworthy instead of a rephrased README.

### Step 3 - Confirm scope for large or ambiguous codebases

If the codebase is large, multi-service, or the user hasn't said what to focus on, ask one clarifying question before generating everything (e.g. "This looks like a monorepo with 4 services - do you want one architecture doc covering all of them, or should I scope this to a specific service?"). For a single, reasonably-sized repo, proceed with sensible defaults without asking.

### Step 4 - Write `ARCHITECTURE.md`

Follow the structure and principles in `references/architecture-doc-template.md`. The short version:

- Write for a model, not a person: dense bullets over prose, exact file paths over descriptions, exact commands over "you can run the tests".
- Every non-trivial claim should be groundable in a real path (e.g. "routing is defined in `src/router/index.ts`", not "the app uses a router").
- Include a system map of components/services and how they relate.
- Include an "invariants and gotchas" section - the non-obvious rules a newcomer (human or agent) could easily violate (e.g. "never write to `legacy_users`, only read"; "migrations must be added, never edited, after merge").
- Date the document and note that source code is the ground truth - the doc should be regenerated or refreshed periodically, not treated as permanently authoritative.

### Step 5 - Write the agent file (`AGENTS.md`)

This is the first file an agent reads when it opens the repo, so it must be short, directive, and immediately actionable. Follow `references/agent-file-template.md`.

Naming: check what the codebase or user's tooling already expects.
- If a `CLAUDE.md` or `AGENTS.md` already exists, update that one and keep its name.
- Otherwise default to `AGENTS.md` at the repo root.
- If genuinely unclear, ask.

Content: what the project is (1-2 sentences), how to set up/build/run/test/lint (exact commands, verified against the manifest files - don't guess a command that isn't actually defined), key conventions and boundaries (what not to touch, style rules that matter), a short directory guide, and pointers to `ARCHITECTURE.md` for depth and to the relevant sub-agents for specialized work. All agents and sub-agents must include a directive prohibiting the reading of files `.env`

Always include a **"Keeping this documentation current"** section (see `references/agent-file-template.md`). These deliverables are a point-in-time snapshot - nothing regenerates them automatically. Without an explicit instruction, coding agents that later modify the project will silently let `ARCHITECTURE.md` and this file drift out of date. The instruction must name concrete triggers (new/removed/moved modules, changed flows, new integrations, changed commands) rather than a vague "keep docs updated," or it won't reliably fire.

### Step 6 - Design and write sub-agents

Partition the codebase into natural domains based on what you found in Step 1-2 (common patterns: `backend`/`api`, `frontend`/`ui`, `data`/`db`, `infra`/`devops`, `tests`/`qa` - but derive this from the actual codebase, don't force a fixed template onto a project that doesn't fit it). Aim for 3-6 sub-agents; one-per-file or one-per-folder granularity is almost always too fine and defeats the purpose.

For each sub-agent, write a file at `.agents/<name>.md` following `references/subagent-template.md`:

- **`name`**: kebab-case, specific (e.g. `backend-api-agent`, not `helper`).
- **`description`**: written for the *orchestrating* agent that will decide whether to invoke this sub-agent - state clearly when it should be used, not just what it does. This field drives automatic selection, so be concrete about triggering scenarios.
- **`tools`**: scope to what the role actually needs. A review-only sub-agent gets read/search tools; a sub-agent that ships code gets edit/run tools too. Don't grant broad tool access by default.
- **System prompt body**: the domain's specific file paths, conventions, and boundaries - plus a pointer back to `ARCHITECTURE.md`/`AGENTS.md` for shared context, so you're not duplicating the whole architecture doc in every sub-agent.

### Step 7 - Save and present

Save the three deliverables to sensible locations in the codebase:
- `ARCHITECTURE.md` at the repo root (or `docs/ARCHITECTURE.md` if the project keeps docs there).
- `AGENTS.md` / `CLAUDE.md` at the repo root.
- Sub-agents under `.agents/`.


## Principles to keep in mind throughout

- **Ground everything in code, not conventions.** A framework's usual folder layout is a hypothesis to verify, not a fact to assert.
- **Optimize for machine consumption.** These documents will mostly be read by models loading context, not by humans reading top to bottom. Favor structured, scannable, unambiguous text over narrative prose.
- **Keep it current by design.** Note explicitly in the outputs that they reflect a point-in-time analysis and should be refreshed as the codebase evolves - don't let the documents imply a permanence the code doesn't have. Concretely, this means: the "Keeping this documentation current" section in `AGENTS.md` is not optional, and if the user has CI or a hook mechanism available, mention that they can also trigger a periodic re-run of this skill as a backstop, since agent-driven updates alone are not guaranteed to catch everything.
- **Don't over-fragment sub-agents.** More sub-agents isn't better; each one should correspond to a real, recurring type of work in this specific codebase.
