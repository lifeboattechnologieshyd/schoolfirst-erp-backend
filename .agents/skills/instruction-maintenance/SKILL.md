---
name: instruction-maintenance
description: Maintain AI-facing instruction docs without overlap, drift, or dead references.
---

# Instruction Maintenance

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

Use this skill when editing any AI-facing instruction surface in the repository, including:

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.agents/skills/*`

## Ownership Model

- `AGENTS.md` owns workflow, autonomy, escalation, and validation order.
- `.github/copilot-instructions.md` owns repository-specific engineering conventions.
- `.agents/skills/*` own narrow, repeatable task recipes.

If the same directive appears in more than one layer, keep one canonical owner and delete the duplicate.

## Editing Rules

1. Remove references to files that do not exist.
2. Prefer short imperative bullets over long essays.
3. Keep task skills narrow; they should not restate the entire global workflow.
4. Use concrete repository paths and commands that match the current codebase.
5. Cross-link the instruction layers so an agent can route quickly.

## Validation Checklist

1. Search for stale file references, especially renamed or missing docs.
2. Search for duplicated mandates that now belong to a single owner.
3. Verify new skill names are task-oriented and discoverable.
4. Confirm that instruction text matches real folders such as `bruno/`, `tests/playwright/tests`, and `shared/mixins/drf_views` consumers.

## Done Criteria

The instruction set is in good shape when:

- every rule has a clear owner,
- there are no dead references,
- task skills are present for high-frequency work,
- the docs are shorter, clearer, and easier to route than before.
