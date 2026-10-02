# SPEC-175 mechanical summary

Canonical ground truth SHA-256: `d9a8ce2b087d7eb59ace5677b6cede18868e28d121a78b9ac5f20adcda957e39`. The computed hash matches the commitment (`true`).

There are 16 observations per condition. `localization_hit_before_edit` is 15/16 (93.75%) for A and 16/16 (100%) for B. Irrelevant-file counts, excluding `tests/**` and `web/e2e/**`, are 11 total / 0.6875 mean for A and 10 total / 0.625 mean for B. Mean relevant-test recall is 0.40625 for A and 0.375 for B.

Medians are:

| condition | discovery calls | source bytes read | wall seconds |
| --- | ---: | ---: | ---: |
| A | 3 | 9054.5 | 2.8 |
| B | 4 | 17027 | 10.3 |

Per-task replica averages (`A` → `B`) for discovery calls / source bytes are: B01 4/8646 → 6/21961.5; B02 3.5/14147 → 4.5/29456; B03 3.5/10291 → 4/15211; B04 2.5/10712.5 → 5/18047; B05 1.5/8059 → 4/12990; B06 1.5/4861 → 3/9884; B07 6.5/20081 → 5.5/30577; B08 5/8707 → 5/13952.5.

Under the preregistered `cost_win` rule, B has 0/8 task wins. The global 20% reduction criterion is false: median discovery calls change from 3 to 4 and median source bytes from 9054.5 to 17027. Conditional on `resolved` not falling, the mandatory and selective criteria are not met. The removal clause's localization-justification wording is left as `pending_sol_review`; `resolved` itself is not scored here.
