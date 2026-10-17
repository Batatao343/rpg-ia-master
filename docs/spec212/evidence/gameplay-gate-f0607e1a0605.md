# Gate de gameplay do beta desktop — f0607e1a0605

- ok: **True** · dirty_files: 0 · strict: True
- viewports: 1440x900, 1280x800
- failing: —

| check | status | bloqueante |
|---|---|---|
| journeys_f01_f40 | pass | True |
| vertical_v01_v09 | pass | True |
| console_clean | pass | True |
| no_duplicate_turns | pass | True |
| no_secret_leak | pass | True |
| latency_present | pass | True |
| a11y_serious_critical | pass | True |
| xp_speaker_roster_gesture | pass | True |
| known_issues_no_blockers | pass | True |

## Baseline de latencia (cliente, nearest-rank, sem meta)

- desktop-1440: n=7 TTFMC p50/p95 417/511 ms · TTLT p50/p95 419/517 ms (indicativo: n<20)
- desktop-1280: n=9 TTFMC p50/p95 189/310 ms · TTLT p50/p95 191/313 ms (indicativo: n<20)
