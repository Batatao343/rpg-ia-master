# Eval gates

`eval-gates` is the required deterministic workflow. It always validates the
frozen eval registry and Project Index, then runs the regression datasets. The
scope manifest selects the extra backend and frontend jobs from changed paths.
No automatic job invokes a real provider or a long campaign.

Changes under `evals/protected-paths.txt` activate the `eval-governance`
environment. Configure that environment with required reviewers and keep
`EVALUATOR_CHANGE_APPROVED=true` as a variable **of that environment** (not of
the repository). Environment variables only reach the job after a reviewer
approves the deployment, so the approval click is the single gate and nobody
toggles the variable per run. Without both controls, the job fails closed.

One-time setup (owner):

```bash
gh variable set EVALUATOR_CHANGE_APPROVED --env eval-governance --body true
gh variable delete EVALUATOR_CHANGE_APPROVED   # remove any repository-level copy
```

Per wave: batch every pending eval authoring into one commit (no product code in
it), push, then run `/eval-publish` (`scripts/dev/eval_publish.py`). It validates
the scope, finds the waiting `eval-gates` run and prints the approval link plus
the exact `gh api … pending_deployments … state=approved` command for the owner.
Agents never approve the environment and never wait in a loop.

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
