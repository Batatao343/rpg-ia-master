# SPEC-175 v6  -  mechanical summary

Scope: v6 only. V1 - v5 are excluded. Semantic `resolved` scoring and the mandatory/selective/remove decision remain pending independent Sol review.

## Integrity and validation

- Attestation self-hash: PASS (`sha256:e4de94d418baa87deb76f061c35560795d2873ef12899e7cf731a400fe74b36e`).
- Sealed artifact SHA-256 checks: PASS across 10 attested hash entries; commitment and ciphertext file hashes also match the attestation.
- Ground truth: canonical hash `sha256:1f5ec3ce3b235271d7a2cb0e02d3fd9fdf57326554dbde9e4f2714dee63f9af3` matches both commitment and attestation; revealed plaintext file hash `sha256:1194c5cd6fc23c7bcd1c9a67e802dfc636094370e9711c9c002d23137fc3a3d6` matches commitment.
- Nested seal: commit `aa50ca35af7e0f7c3785e7405b04c23ee68ab326` at `2026-10-01T14:35:52-03:00`; tracked working tree clean; all 12 files in the seal commit, including the attestation, match their committed blobs; commit timestamp precedes all session creation and first traces: PASS.
- Source tree and graph hashes match `project_index/manifest.json`: source PASS, graph PASS.
- Session prompts: all expected hashes match: PASS. Four complete sessions  -  8 results = 32 observations. Each session also matches the sealed source, graph, attestation, and budget hashes/values; agent-tool attestations were recorded after all four completed.
- Design checks: A index operations absent = True; every B task begins with `index:query` = True; trace calls/bytes reconcile = True; all task budgets pass = True.

## Session audit

| Session | Condition | Replicate | Model / effort | Order | Prompt hash | Complete | Trace reconciles | Budgets | File SHA-256 |
|---|---:|---:|---|---|---|---:|---:|---:|---|
| a1-v6 | A | 1 | gpt-5.6-sol / high | B01 - B02 - B03 - B04 - B05 - B06 - B07 - B08 | PASS | PASS | PASS | PASS | `sha256:10734f0ce3cc03faf865f893ec2e9acfc336fad5b66b5a4f6fa3cf4d61de2a52` |
| a2-v6 | A | 2 | gpt-5.6-sol / high | B08 - B07 - B06 - B05 - B04 - B03 - B02 - B01 | PASS | PASS | PASS | PASS | `sha256:0de6eea0a5d3913bbed51eb5c5926be1d018648998d144bd289017f431f8c94a` |
| b1-v6 | B | 1 | gpt-5.6-sol / high | B08 - B07 - B06 - B05 - B04 - B03 - B02 - B01 | PASS | PASS | PASS | PASS | `sha256:4048dca761fda9b636b1a77dd4ff24b5821d790e4896122243489ad0b4b462af` |
| b2-v6 | B | 2 | gpt-5.6-sol / high | B01 - B02 - B03 - B04 - B05 - B06 - B07 - B08 | PASS | PASS | PASS | PASS | `sha256:40f9e48d977597a2ed95f961324b2c418a404504892511ee4566a66095e37ae8` |

## Frozen metrics

Localization hit = a ground-truth core file among the first three reported implementation files. Irrelevant implementation files exclude `tests/**` and `web/e2e/**`. Test recall strips any `::test_name` suffix and averages per observation. Medians are the arithmetic mean of the two middle observations. Per-task usage is averaged across the two replicates.

| Condition | N | Localization hits | Irrelevant files total / mean | Relevant test recall mean | Median calls | Median source bytes | Median wall seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 16 | 16 | 18 / 1.1250 | 0.6042 | 5.00 | 24676.00 | 38.907 |
| B | 16 | 16 | 12 / 0.7500 | 0.6458 | 8.00 | 30999.50 | 58.254 |

## Per-task two-replicate averages

`cost_win` is true when B reduces calls or bytes and the other dimension worsens by at most 10%.

| Task | A calls | B calls | A bytes | B bytes | Cost win |
|---|---:|---:|---:|---:|---:|
| B01 | 5.50 | 10.00 | 45170.5 | 38177.5 | no |
| B02 | 3.50 | 8.00 | 44938.0 | 45503.0 | no |
| B03 | 6.00 | 10.50 | 32319.0 | 25457.0 | no |
| B04 | 6.50 | 7.50 | 23252.5 | 20445.5 | no |
| B05 | 3.50 | 6.50 | 11753.5 | 30999.5 | no |
| B06 | 2.00 | 7.00 | 21717.0 | 9015.0 | no |
| B07 | 4.50 | 7.00 | 31266.5 | 44914.0 | no |
| B08 | 6.00 | 10.00 | 10820.0 | 21700.5 | no |

Cost wins: 0/8 (none).
Global criterion: median bytes reduction -25.6261%; median calls change +60.0000%; criterion FAIL (at least 20% reduction in one median and no more than 10% worsening in the other).

## Reproduction logic

The aggregation uses the project Python 3.13 environment and standard-library `json`, `hashlib`, arithmetic, and `subprocess`; it does not invoke the product, evaluator, tests, or LLM. To reproduce from the repository root, use the same deterministic logic:

```python
sha256(data) = hashlib.sha256(data).hexdigest()
canonical_ground_truth = json.dumps(json.loads(ground_truth_bytes), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
median_even(xs) = (sorted(xs)[len(xs)//2 - 1] + sorted(xs)[len(xs)//2]) / 2
localization_hit = bool(set(result.files[:3]) & set(task.core_files))
irrelevant = files outside task.core_files, excluding tests/** and web/e2e/**
test_recall = len(gold_tests & reported_tests_after_stripping_::suffix) / len(gold_tests)
task_cost_win = (B_calls < A_calls and B_bytes <= 1.10*A_bytes) or (B_bytes < A_bytes and B_calls <= 1.10*A_calls)
global_pass = (one median reduction >= 20%) and (other median worsening <= 10%)
```

Trace reconciliation sums each trace entry - s `source_bytes`, compares trace length with stored `discovery_calls`, and compares both totals with the task result. Budgets compare each task - s calls, source bytes, and result wall seconds against 12, 50,000, and 300. The nested seal was checked with `git rev-parse`, `git show -s --format=%cI`, `git status --porcelain --untracked-files=all`, and `git ls-tree`; all sealed files -  current Git blob IDs were compared with `HEAD:path`.
