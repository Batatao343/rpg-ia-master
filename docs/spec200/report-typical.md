# Baseline de latencia percebida (SPEC-200)

## Fingerprint de ambiente

- `git_sha`: `afe98941a541dc5643b1f2f1f4ef3ba7563fcca6`
- `mode`: `offline-virtual`
- `profile`: `typical`
- `execution_mode`: `sequential`
- `python`: `3.13`
- `pseudo_streaming`: `True`
- `journeys_version`: `1`

> `pseudo_streaming=true`: o servidor fatia uma mensagem JA pronta; **TTFT = TTFMC (pseudo_streaming)** — nao ha token real.

> Modo offline mede a ESTRUTURA do turno (decomposicao, ordem, contagens) com latencia injetada; nao e latencia de rede. p95 absoluto so e interpretavel no modo `real`.

## TODAS — n=330

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 330 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 330 | 6417 | 7964 | 14036 |
| ttlt | 330 | 6417 | 7964 | 14036 |
| state | 330 | 6417 | 7964 | 14036 |
| total | 330 | 6417 | 7964 | 14036 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 289 | 355 | 4.7% |
| context | 0 | 0 | 0.0% |
| narrator | 2658 | 5996 | 50.6% |
| archivist | 3589 | 4709 | 44.7% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 180 | 6417 | 7882 |
| medium | 120 | 6514 | 9902 |
| long | 30 | 3313 | 7739 |

- tentativas LLM/turno (media): 3.139 · fallbacks: 0 · rotas: {'combat_agent': 60, 'loot': 60, 'npc_actor': 60, 'storyteller': 150}

## J1_story_simple — n=90

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 90 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 90 | 6247 | 7661 | 12012 |
| ttlt | 90 | 6247 | 7661 | 12012 |
| state | 90 | 6247 | 7661 | 12012 |
| total | 90 | 6247 | 7661 | 12012 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 299 | 357 | 7.8% |
| context | 0 | 0 | 0.0% |
| narrator | 2534 | 2984 | 49.9% |
| archivist | 3272 | 4609 | 42.2% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 6046 | 7545 |
| medium | 30 | 6412 | 7731 |
| long | 30 | 3313 | 7739 |

- tentativas LLM/turno (media): 2.556 · fallbacks: 0 · rotas: {'storyteller': 90}

## J2_combat_start — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 5782 | 13064 | 14036 |
| ttlt | 60 | 5782 | 13064 | 14036 |
| state | 60 | 5782 | 13064 | 14036 |
| total | 60 | 5782 | 13064 | 14036 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 270 | 354 | 3.2% |
| context | 0 | 0 | 0.0% |
| narrator | 5485 | 8646 | 87.1% |
| archivist | 0 | 4421 | 9.7% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 3020 | 13150 |
| medium | 30 | 6293 | 13064 |

- tentativas LLM/turno (media): 4.667 · fallbacks: 0 · rotas: {'combat_agent': 60}

## J3_npc_dialogue — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 6761 | 8780 | 9902 |
| ttlt | 60 | 6761 | 8780 | 9902 |
| state | 60 | 6761 | 8780 | 9902 |
| total | 60 | 6761 | 8780 | 9902 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 294 | 353 | 4.3% |
| context | 0 | 0 | 0.0% |
| narrator | 2503 | 4865 | 38.5% |
| archivist | 3810 | 4707 | 57.1% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| medium | 60 | 6761 | 8780 |

- tentativas LLM/turno (media): 3.067 · fallbacks: 0 · rotas: {'npc_actor': 60}

## J4_loot_shop — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 7043 | 7964 | 8138 |
| ttlt | 60 | 7043 | 7964 | 8138 |
| state | 60 | 7043 | 7964 | 8138 |
| total | 60 | 7043 | 7964 | 8138 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 306 | 354 | 4.3% |
| context | 0 | 0 | 0.0% |
| narrator | 2665 | 3230 | 37.8% |
| archivist | 4172 | 4709 | 57.9% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 60 | 7043 | 7964 |

- tentativas LLM/turno (media): 3.5 · fallbacks: 0 · rotas: {'loot': 60}

## J5_travel_replan — n=30

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 30 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 30 | 6573 | 7707 | 7734 |
| ttlt | 30 | 6573 | 7707 | 7734 |
| state | 30 | 6573 | 7707 | 7734 |
| total | 30 | 6573 | 7707 | 7734 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 0 | 0 | 0.0% |
| context | 0 | 0 | 0.0% |
| narrator | 2507 | 2940 | 38.4% |
| archivist | 3994 | 4776 | 61.6% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 6573 | 7707 |

- tentativas LLM/turno (media): 2.0 · fallbacks: 0 · rotas: {'storyteller': 30}

## J6_first_turn_new_game — n=30

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 30 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 30 | 2978 | 7882 | 7932 |
| ttlt | 30 | 2978 | 7882 | 7932 |
| state | 30 | 2978 | 7882 | 7932 |
| total | 30 | 2978 | 7882 | 7932 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 302 | 350 | 6.6% |
| context | 0 | 0 | 0.0% |
| narrator | 2479 | 2957 | 55.7% |
| archivist | 0 | 4712 | 37.7% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 2978 | 7882 |

- tentativas LLM/turno (media): 2.4 · fallbacks: 0 · rotas: {'storyteller': 30}

