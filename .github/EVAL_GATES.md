# Eval gates

`eval-gates` is the required deterministic workflow. It always validates the
frozen eval registry and Project Index, then runs the regression datasets. The
scope manifest selects the extra backend and frontend jobs from changed paths.
No automatic job invokes a real provider or a long campaign.

Changes under `evals/protected-paths.txt` activate the `eval-governance`
environment. Configure that environment with required reviewers and set its
`EVALUATOR_CHANGE_APPROVED=true` variable only for an independently reviewed
evaluator-change task. Without both controls, the job fails closed.

`eval-protected` is manual. Its `eval-provider` environment contains the short
contract provider key. The job reserves a conservative worst-case estimate
before every provider request and stops before either the 20-request or USD
0.20 cap. Its artifact contains JUnit plus a redacted usage/identity manifest.
Its `eval-holdout` environment contains the private
companion repository name and read-only token. The companion may export only
the aggregate schema accepted by `scripts/validate_holdout_aggregate.py`; case
inputs, expected values, prompts and transcripts stay outside this repository
and its artifacts.

`post-deploy-smoke` is manual and uses the protected `post-deploy-smoke`
environment. It performs read-only requests and verifies the deployed Git SHA.
It never creates a game or calls an LLM.
