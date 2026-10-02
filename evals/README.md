# Valoria evals

This directory contains the public deterministic eval ruler. Product optimization
must not change the protected paths listed in `protected-paths.txt` in the same
task. Evaluator changes require a separate reviewed task and a new evaluator
version when semantics change.

Datasets under `datasets/dev` are for debugging. Real bugs become permanent
cases under `datasets/regression`. A true holdout must live in a separate private
repository and may return only aggregate metrics and opaque failure IDs; no
`datasets/holdout` directory is allowed here. Without that private companion,
scores are development scores rather than evidence of generalization.

Every metric defines its unit, numerator, denominator and exclusions in
`metrics-registry.yaml`. Subjective LLM judges remain informational until a
separate SPEC-171 meta-eval establishes an auditable promotion contract. They
cannot block in this version and never replace deterministic state, schema,
invariant or evidence checks.

Before execution, run:

```powershell
uv run python -m evals.core.governance check --root .
```

The check fails closed when a dataset, registry, generated schema or evaluator
version differs from `manifest.lock.json`. The lock includes exact hashes for
the complete ruler bundle (`evals/core`, `evals/evaluators` and the CLI entrypoint).
Baselines are comparable only when schemas, ruler source, metric registry, case
selection, datasets, seed and runtime configuration match; the product SHA is
expected to differ between baseline and candidate.

Run a locked deterministic suite without provider credentials:

```powershell
uv run python -m evals --root . run `
  --dataset datasets/regression/harness.jsonl `
  --run-id local-harness
```

The command writes addressable JSON and Markdown under `evals/runs/` and exits
non-zero for a failed case, case error, skip or blocking hard limit. Results
include product SHA, dataset hashes, evaluator bundle hashes, registry hash,
seed and runtime identity. Compare only compatible runs:

```powershell
uv run python -m evals --root . compare `
  --baseline evals/runs/baseline.json `
  --current evals/runs/candidate.json
```

Suites resolve through the explicit registry in `core/adapters.py`. The
`playtest_invariants` adapter calls `playtest.invariants.check_all`; it does not
copy the systemic rules. Adapters produce only `actual`. The fixture-authored
`expected` remains outside product execution.
