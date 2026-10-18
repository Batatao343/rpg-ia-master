# Rate card / audit-local incident — 2026-10-17/18

CI `audit-local` (run 39089618980, commit `ebd3cdd`) failed in
`tests/test_audit_browser_local.py` with `503 image_pricing_unavailable` at the
image quote step. The same job passed on `7c79697` a few hours earlier; no
pricing code changed in between.

## Root cause: a fixture window, not an expired provider card

- `PricingVersion.require_fresh` pins `rate_card_observed_at` to the installed
  LLM card (`data/pricing/rate_card_2026-10-08.json`, observed
  2026-10-08T00:00Z) and requires `now - observed <= rate_card_max_age_seconds`.
- The audit fixture (`tests/fakes/local_image_finance.py`) and nine other
  Postgres-local tests seeded that window as a fixed `864000` s (10 days).
  They expired at **2026-10-18T00:00Z**. CI ran at 02:21Z.
- The installed cards are still fresh under their production windows:
  LLM until 2026-11-07, image and speech (`*_2026-10-12.json`, 30 d window
  from SPEC-236) until 2026-11-11. The "expires 19/10" note refers to the
  old 7-day window before SPEC-236.

**No new rate card was issued.** Nothing expired at the provider level, so a
new card would only add churn. The live prices were not re-verified as part
of this incident.

## Fix

- `tests/fakes/local_pricing.py::installed_card_max_age_seconds(now)` returns
  the installed card's current age plus a 10-day margin. All synthetic
  pricing versions in local tests and in the audit fixture use it. Production
  guards are unchanged: the installed card, its sha and observed_at, and the
  published windows still fail closed.
- `tests/test_local_pricing_fixture.py`, offline:
  - The helper stays fresh at +0 to +400 days.
  - The old fixed 864000 s window fails at the CI instant.
  - A real 30-day window still rejects a 40-day-old card.
- `test_stale_image_card_fails_before_ticket_and_releases_safe_hold` now
  advances past the image card's own window. It no longer depends on the
  pricing-version window expiring by accident.
- The fix also exposed a second failure in the audit browser test. SPEC-216
  replaced the "Modo de exibição" group with the "Superfícies" nav below
  900 px. The test now uses that nav, as the Playwright journeys already do.

## Verification

- `scripts/audit_local_gate.py` on a freshly reset local stack: 35 passed.
- Edited Postgres-local tests: 79 passed, 1 failed.
  - The failure is `test_expired_job_fence_cannot_dispatch_and_reclaimed_ticket_never_retries`.
  - It fails because of SPEC-236 R9: an image job has `max_attempts=1`, so an
    expired lease goes `dead` instead of being re-leased.
  - It is unrelated to pricing. No CI workflow runs it. Left for a follow-up.

## Before 2026-11-07

Renew the cards ahead of their windows. Follow the runbook in
`docs/spec197/runbooks/budget.md`: add a new versioned file and update the
loader paths. Never edit a card in place. `rate_card_expiring` warns 3 days
ahead.

## Staging

No action is needed for this incident. Staging pricing versions come from
`scripts/staging/synthetic_data.py`, which uses a 1-year window.

`scripts/staging/smoke_ab.py` (historical SPEC-191 smoke) still seeds a
1-day window from the installed card's `observed_at`. It would fail if it
were re-run today. It was not changed or run.
