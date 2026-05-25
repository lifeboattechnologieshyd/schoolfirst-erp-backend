# Cross-App Typed Seams Design

Date: 2026-05-17
Status: Proposed
Scope: assistant, calendar, core, docusafe

## Summary

This design deepens shallow modules across the backend by moving raw dict and JSON payload handling to explicit typed seams. The goal is to improve locality for schema changes, increase leverage for callers, and make tests exercise stable module interfaces instead of implicit field names.

The implementation will be phased by module, not as one undifferentiated refactor. Each phase will preserve existing endpoint URLs and response envelopes unless a contract change is required to remove ambiguity or duplicated parsing.

## Problem Statement

Several modules currently expose interfaces that are nearly as complex as their implementations:

- Calendar recurrence and mutation behavior flows through mutable `validated_data` dicts.
- Docusafe access and temporary sharing use separate modules but still leak raw request fields and raw dict outputs across the seam.
- Assistant Thread settings are partially typed, while `module_settings` and LLM results still rely on ad hoc dict contracts.
- Core auth and lookup flows return positional tuples and implicit dict payloads.

These shapes reduce locality because a field rename or new invariant requires coordinated edits across serializers, views, and service modules.

## Goals

- Deepen module interfaces around typed request and result values.
- Keep business logic in service modules, not views or serializers.
- Preserve the standard API response envelope.
- Minimize request and response contract churn where typed seams can be introduced internally.
- Update Bruno and Playwright coverage where external contracts change.

## Non-Goals

- Replacing Django models with a new persistence pattern.
- Introducing a repo-wide static type checker in this change set.
- Rewriting every JSONField into normalized relational tables.
- Unifying unrelated business rules across apps when only the payload shape is shared.

## Approaches Considered

### Approach 1: Broad annotation pass

Add more type hints to existing functions and keep current dict-based interfaces.

Pros:

- Smallest diff.
- Low migration risk.

Cons:

- Does not deepen the modules.
- Leaves callers dependent on raw keys and ordering.
- Keeps tests focused on implementation details rather than the interface.

### Approach 2: Phased typed seams by module

Introduce typed request and result modules at the serializer-to-service seam for each app, then migrate callers incrementally.

Pros:

- Highest locality per phase.
- Lets validation follow the owning contract.
- Limits risk by validating each app slice independently.

Cons:

- Requires touching several modules over multiple passes.
- Some bridge code will temporarily coexist with old dict-based paths.

### Approach 3: Shared cross-app type layer first

Define a common shared types package before touching app logic.

Pros:

- Encourages reuse for recurring concepts like access scopes and auth results.

Cons:

- High risk of creating hypothetical seams.
- Can centralize shapes before behavior is stable.
- Likely to slow delivery with premature abstractions.

## Recommendation

Use Approach 2.

The seam is already real inside each app: serializers parse inputs, services decide behavior, and views adapt responses. Deepening those module interfaces app by app increases leverage immediately without creating speculative cross-app adapters. Shared types should only be extracted after at least two modules prove the seam is real.

## Design

### 1. Core auth and lookup module

Core auth will stop returning positional tuples and implicit dict payloads from service modules. The service interface will return explicit result values for signup completion, password reset verification, login token issuance, and User lookup.

The view layer will keep the existing response envelope, but it will no longer reconstruct payload shape from loose return values. This concentrates auth result structure in one module and makes future additions like token metadata or alternative auth flows local changes.

### 2. Assistant Thread context and Message result module

Assistant Thread settings already have one typed seam in `ThreadSettingsSerializer`. This will be extended so `module_settings`, content block payload handling, and non-streaming LLM results move behind explicit typed modules.

The LangGraph state stays as-is because it is already a real typed seam. The deeper module will sit between graph execution and persistence, so `ChatView`, `Thread`, and `LLMService` no longer coordinate ad hoc dict shapes for module-specific context or response payloads.

### 3. Calendar recurrence and mutation module

Calendar recurrence currently relies on raw RRULE dicts and mutable `validated_data` shared across mutation scopes. This will be replaced by typed mutation input modules and a typed recurrence module.

The service module will own RRULE parsing, recurrence end-date derivation, attachment resolution decisions, and per-scope update behavior. Views and serializers will stop knowing which keys are removed, mutated, or synthesized during recurrence updates.

### 4. Docusafe access and sharing module

Docusafe currently has real module separation for owner lifecycle and public temporary-share access, but the typed seam is still weak. Grant access, revoke access, owner share lifecycle, and public share access will move toward explicit request and result modules.

The goal is not to collapse every Docusafe sharing module into one implementation. The goal is to make the interface of each module explicit enough that views do not coordinate raw request-data conventions or interpret raw dict results.

## Module Boundaries

### Serializer seam

Serializers remain responsible for external input validation. Where a payload is structurally rich, nested serializers should be used instead of bare `JSONField` inputs. After validation, serializers should hand service modules a typed module input rather than a raw dict where practical.

### Service seam

Service modules own business invariants, derived fields, orchestration, and persistence decisions. They should accept typed inputs and return typed results whenever a caller would otherwise need to know field names, ordering, or implicit error modes.

### View seam

Views keep responsibility for authentication, permission classes, serializer invocation, and standard response formatting. Views should not transform business payloads beyond adapting typed results to the existing response envelope.

## Data Flow

1. Request enters view.
2. Serializer validates the external payload.
3. Serializer or adjacent adapter converts validated input into a typed module input.
4. Service module performs business behavior and returns a typed result.
5. View converts the typed result into the standard `{success, message, data, error, meta}` envelope.

This data flow keeps the interface test surface on the serializer-to-service seam and the service-to-view result seam.

## Error Handling

- Validation errors remain serializer-driven and continue to use the standard error envelope.
- Service modules continue to raise domain-appropriate exceptions where behavior is invalid after input validation.
- New typed result modules should not encode error states as loosely typed dict flags.
- If a response contract changes, the view will remain the single place that maps typed results to external payload shape.

## Migration Strategy

### Phase 1: Core

- Add typed auth and lookup result modules.
- Replace tuple and raw dict returns in core auth and User lookup flows.

### Phase 2: Assistant

- Deepen `module_settings` handling.
- Add explicit result typing for non-streaming chat responses.
- Keep streaming event payloads stable in phase 2 unless validation holes require a contract update.

### Phase 3: Calendar

- Add typed recurrence and mutation input modules.
- Migrate event and task mutation modules off raw `validated_data` dict mutation.
- Keep list and detail endpoints stable unless a filter contract is clarified.

### Phase 4: Docusafe

- Add explicit request and result modules for grant/revoke and temporary-share access.
- Preserve existing module split between owner lifecycle and public access.
- Only extract shared access types if both sides require the same seam after the refactor.

## Testing Strategy

- Use focused executable validation after each phase.
- For API-facing contract changes, update Bruno and the matching Playwright tests in the same phase.
- Prefer slice-level Ruff validation for changed modules before broader checks.
- Use migrations only if a model field or persistence contract changes.

## Contract Policy

- Internal typed seams can change without Bruno updates if request and response contracts stay the same.
- Bruno and Playwright updates are required when request payloads, response data fields, or status codes change.
- The standard response envelope will remain unchanged.

## Risks

- Mixing internal refactor and API contract changes in the same phase can obscure regressions.
- Over-extracting shared types too early can create hypothetical seams with no real leverage.
- Calendar recurrence behavior is sensitive because mutation scopes currently depend on in-place dict mutation.
- Assistant streaming must keep current event ordering and payload shape unless explicitly revised.

## Validation Plan

- Phase 1: focused checks on core slices.
- Phase 2: focused checks on assistant serializers and services.
- Phase 3: focused checks on calendar recurrence and mutation slices.
- Phase 4: focused checks on docusafe access and sharing slices.
- Final pass: repo-level Ruff or targeted multi-slice checks plus any necessary Bruno and Playwright updates.

## Open Decisions

- Default rollout: phased by module.
- API stability preference: preserve existing contracts unless a contract change is needed to remove ambiguity.
- Shared cross-app access types should only be extracted if the seam remains real after calendar and docusafe phases are complete.
