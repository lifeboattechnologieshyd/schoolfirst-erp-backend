# AGENTS.md - Execution Guide

This file owns agent workflow for this repository.

- Use this file for execution policy, validation order, escalation, and instruction maintenance.
- Use [.github/copilot-instructions.md](.github/copilot-instructions.md) for repository architecture and coding conventions.
- Use the matching skill in [.agents/skills](.agents/skills) for task-specific checklists.

If a rule appears in more than one of those places, that is instruction debt. Remove the duplicate and keep one clear owner.

## Instruction Hierarchy

1. The user request and explicit task constraints.
2. This file for workflow, autonomy, validation, and escalation.
3. [.github/copilot-instructions.md](.github/copilot-instructions.md) for repo-specific implementation rules.
4. Relevant skill files in [.agents/skills](.agents/skills) for task-shaped recipes.
5. Module-specific instruction files in [.github/instructions/](.github/instructions/) — these load automatically via `applyTo` when you open or edit files in the matching directory.
6. Nearby code, tests, and existing patterns in the touched area.

## Start Every Task This Way

1. Read the full user request before touching files.
2. Identify the most concrete anchor available: failing test, endpoint, file, symbol, traceback, serializer, or model.
3. For any task with 3 or more meaningful steps, create a todo list before editing.
4. Read only enough nearby code to form one falsifiable local hypothesis and one cheap check that could disconfirm it.
5. If the first file only wires or registers behavior, step once to the code that actually decides the behavior.

Do not spend time mapping the repo broadly once there is a workable local hypothesis.

## Core Execution Loop

1. Plan briefly with checkable steps.
2. Make the smallest grounded edit that tests the current hypothesis.
3. Validate immediately after the first substantive edit.
4. If validation fails, either repair the same slice or move one hop closer to the controlling code.
5. Repeat until the task is complete or clearly blocked.

After the first edit, validation order is:

1. The exact failing behavior, command, or test if available.
2. A narrow test for the touched slice.
3. A narrow lint, typecheck, or compile check.
4. Diff inspection only when no executable validation exists.

Do not keep editing adjacent surfaces before running that first focused validation.

## Progress And Autonomy

- Keep working until the task is resolved end to end or a real blocker exists.
- Give short progress updates while exploring, editing, and validating.
- Prefer targeted search and local reads over broad exploration.
- Do not ask the user to perform steps you can execute directly.
- When required non-sensitive input or business clarity is missing, use VS Code's `vscode_askQuestions` tool instead of guessing or asking in free-form prose.
- If the task expands, update the plan instead of drifting silently.

## Shared Context Persistence

- For substantial work, persist repo-shared context under [docs/superpowers/](docs/superpowers/) so later agents and sessions can reuse it.
- Treat [docs/superpowers/](docs/superpowers/) as the canonical repo-shared context. Use `/memories` only as an optional cache or for context that should not become a repository document.
- Persist only durable, non-sensitive technical context. Never store secrets, credentials, personal data, or anything that should not be committed.
- Update an existing context doc before creating a new one when the topic already has a live home.
- Write or update shared context only for substantial work such as multi-step execution, debugging, architecture/design changes, refactors, or handoffs that would otherwise lose context.
- Store approved designs in [docs/superpowers/specs/](docs/superpowers/specs/), active plans and handoffs in [docs/superpowers/plans/](docs/superpowers/plans/), durable repo facts and technical preferences in [docs/superpowers/memory/](docs/superpowers/memory/), durable decisions in [docs/superpowers/decisions/](docs/superpowers/decisions/), and bug investigations in [docs/superpowers/investigations/](docs/superpowers/investigations/).
- When a task materially changes direction or finishes, update the relevant shared context doc if future agents would otherwise miss the new state.

## When The User Corrects The Agent

1. Stop the current path immediately.
2. Name the mistake precisely.
3. Classify it as one of: planning failure, assumption error, knowledge gap, or execution slip.
4. Re-derive the approach from scratch instead of patching the bad path.
5. Add the lesson to the Learned Rules section.
6. Confirm the new approach with the user if the correction changes scope or intent.

## Escalate Instead Of Guessing When

- A migration or data change may be destructive or irreversible.
- Business behavior is genuinely ambiguous between two plausible interpretations.
- The same issue persists after 3 distinct attempts.
- The fix expands materially beyond the original slice without clear evidence.
- Credentials, private environment state, or user input are required.

When escalating, include:

- what you validated,
- the current best root-cause hypothesis,
- the concrete decision or missing input needed to continue.

When the missing input is non-sensitive and the user can answer it directly, gather it with `vscode_askQuestions`.

## Task-Specific Routing

### Backend API changes

Use [.agents/skills/backend-api-change/SKILL.md](.agents/skills/backend-api-change/SKILL.md) when you add or change views, serializers, URLs, request payloads, response shapes, auth semantics, or API-facing models.

### Backend debugging

Use [.agents/skills/backend-debugging/SKILL.md](.agents/skills/backend-debugging/SKILL.md) when starting from a failing test, traceback, log, status code, or broken endpoint behavior.

### Instruction maintenance

Use [.agents/skills/instruction-maintenance/SKILL.md](.agents/skills/instruction-maintenance/SKILL.md) when editing AGENTS, repository instruction files, or task skills.

## Verification Before Marking Done

- Prove the touched path with at least one executable check when the environment allows it.
- Prefer targeted validation to full-suite runs unless the task requires broader coverage.
- After any session that edits Python code or fixes diagnostics, run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root and fix any Ruff or `ty` failures before handoff.
- For instruction-only changes, validate by searching for dead references, contradictory directives, and missing cross-links.
- State residual risk clearly when a useful check could not be run.

## Instruction Maintenance Rules

- Keep durable workflow rules in this file.
- Keep repository-specific coding rules in [.github/copilot-instructions.md](.github/copilot-instructions.md).
- Keep narrow, task-scoped recipes in [.agents/skills](.agents/skills).
- Do not reference files that do not exist.
- Prefer imperative bullets and checklists over long prose.
- Keep instructions current with the actual codebase, commands, and test layout.

## Learned Rules

Format each entry as `[mistake] -> [prevention rule]`.

- [planning failure: added backend Python tests in `apps/**/tests`] -> [For this repo, keep backend automated coverage in `tests/playwright/tests` only and remove mismatched Django or Python tests instead of mixing harnesses.]
