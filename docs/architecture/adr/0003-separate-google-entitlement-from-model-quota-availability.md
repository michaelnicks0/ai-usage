---
id: ADR-0003
status: accepted
date: 2026-06-20
decider: Mike Nicks
scope: repo
supersedes: []
superseded_by: []
related:
  - ../workspace.dsl
  - ../../architecture.md
  - ../../data-architecture.md
  - ../../../src/ai_usage/providers/google.py
  - ../../../src/ai_usage/render.py
verification:
  - "Focused tests: .venv/bin/python -m pytest tests/test_providers/test_google.py tests/test_render.py -q (28 passed)"
  - "Full test/cov suite: .venv/bin/python -m pytest tests/ -v --cov=ai_usage --cov-report=term (108 passed, 78% coverage)"
  - "C4 validation/generation gate: Structurizr validate plus 5-view generated artifact completeness check"
  - "Live smoke: ./ai-usage -j -p google showed plan_type=free from loadCodeAssist.paidTier while gemini-3.1-pro-high quota remained present"
---

# ADR-0003: Separate Google Entitlement from Model Quota Availability

## Context

`ai-usage` previously displayed Google AI Studio / Antigravity as `Ultra 20x` when the Cloud Code `fetchAvailableModels` response included `gemini-3.1-pro-high`.

That was misleading. `fetchAvailableModels` reports provisioned model/quota availability, not active Google One / Google AI billing subscription status. A user can see premium-looking model quota rows after a plan changes, during backend grace/transition windows, or because availability and subscription state are represented by different Cloud Code fields.

Cloud Code exposes a separate entitlement probe through `v1internal:loadCodeAssist`. The response includes tier fields such as `paidTier.id`, `currentTier.id`, and `cloudaicompanionProject`. Public Gemini/Antigravity tooling treats `paidTier.id` values such as `g1-ultra-tier` and `g1-pro-tier` as the subscription entitlement signal.

## Decision

`ai-usage` will separate Google subscription entitlement from model quota availability.

- Use `POST daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist` to determine the displayed Google tier.
- Prefer `paidTier.id` for Google One / Google AI paid entitlements.
- Fall back to `currentTier.id` only when no paid tier is present.
- Normalize Google tier metadata into `ProviderData.extra` fields:
  - `plan_type`
  - `plan_label`
  - `plan_source`
  - `subscription_status`
  - `raw_tier_id`
- Continue using `POST daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels` only for per-model quota rows.
- Never infer an active Ultra/Pro subscription from the presence of a model key such as `gemini-3.1-pro-high`.

## Decision drivers

- Avoid false-positive paid-plan labels after a Google AI plan ends.
- Preserve useful per-model quota rows even when subscription entitlement is free or unknown.
- Keep rendered output concise while exposing source metadata in JSON for debugging.
- Avoid storing or documenting OAuth tokens, cookies, or other credential material.

## Options considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Keep model-key heuristic | Minimal code change. | Falsely reports Ultra from availability data; caused the observed bug. | Rejected |
| Hide Google quota rows unless paid tier is active | Avoids confusing premium-looking quota rows. | Throws away useful quota availability data and makes backend state harder to debug. | Rejected |
| Use `loadCodeAssist` for tier and `fetchAvailableModels` for quotas | Separates entitlement from availability; preserves both data sets. | Depends on another private Cloud Code endpoint and must tolerate partial failure. | Chosen |

## Consequences

- Positive: Google rows no longer show `Ultra 20x` solely because `gemini-3.1-pro-high` appears in the quota response.
- Positive: JSON output now records whether the tier came from `loadCodeAssist.paidTier`, `loadCodeAssist.currentTier`, or an unavailable entitlement probe.
- Positive: Quota rows remain visible for debugging model availability and reset windows.
- Neutral: The provider still depends on Google private Cloud Code endpoints, as before.
- Negative: If `loadCodeAssist` fails while `fetchAvailableModels` succeeds, table rows show an unknown tier until entitlement detection succeeds again.

## Verification / validation

- Verification: `.venv/bin/python -m pytest tests/test_providers/test_google.py tests/test_render.py -q` completed with 28 passed.
- Verification: `.venv/bin/python -m pytest tests/ -v --cov=ai_usage --cov-report=term` completed with 108 passed and 78% total coverage.
- Verification: Structurizr validation and generated artifact completeness check completed for the 5 C4 views.
- Verification: `./ai-usage -j -p google` completed successfully and showed `plan_type: "free"`, `plan_source: "loadCodeAssist.paidTier"`, `raw_tier_id: "free-tier"`, and still retained `gemini-3.1-pro-high` quota rows.
- Validation: provider tests cover active Ultra from `paidTier.id`, free/starter entitlement with `gemini-3.1-pro-high` quota availability, token-refresh retry, and exhausted quota rows.
- Validation: renderer tests cover the table not rendering `Ultra 20x` from model availability and JSON exposing `plan_source`/`quota_source`.

## Revisit triggers

- Supersede this ADR if Google publishes a stable public endpoint for Google One / Google AI subscription status.
- Supersede this ADR if Cloud Code changes or removes `paidTier.id`/`currentTier.id` from `loadCodeAssist`.
- Supersede this ADR if Google quota rows move from Antigravity/Cloud Code into a first-party Google AI Studio usage API.

## References

- `README.md`
- `docs/architecture.md`
- `docs/data-architecture.md`
- `src/ai_usage/providers/google.py`
- `src/ai_usage/render.py`
- `tests/test_providers/test_google.py`
- `tests/test_render.py`
