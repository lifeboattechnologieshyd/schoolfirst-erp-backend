# Shared Agent Context

This folder is the canonical repo-shared context for substantial work in this repository.

Use it so later agents and later sessions can recover plans, durable facts, decisions, and investigations without relying on ephemeral chat state.

## Write Rules

- Store only durable, non-sensitive technical context.
- Never store secrets, credentials, private tokens, or personal data.
- Update an existing file before creating a new one for the same live topic.
- Prefer concise bullets and short sections over long narratives.
- Write or update these docs only for substantial work such as multi-step tasks, debugging, design work, refactors, or session handoffs.
- `/memories` can still be used as an optional cache, but `docs/superpowers/` is the canonical repo-shared source of truth.

## Layout

- `specs/` — approved design docs.
- `plans/` — active implementation plans and handoff notes.
- `memory/` — durable repo facts, technical preferences, and open questions.
- `decisions/` — durable decisions and constraints worth reusing.
- `investigations/` — debugging notes, reproductions, and root-cause findings.

## Naming

- Plans: `YYYY-MM-DD-topic-plan.md`
- Decisions: `YYYY-MM-DD-topic-decision.md`
- Investigations: `YYYY-MM-DD-topic-investigation.md`

If a topic already has an active file, update it instead of creating a new one.
