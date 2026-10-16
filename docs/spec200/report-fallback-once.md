# Baseline de latencia percebida (SPEC-200)

## Fingerprint de ambiente

- `git_sha`: `afe98941a541dc5643b1f2f1f4ef3ba7563fcca6`
- `mode`: `offline-virtual`
- `profile`: `fallback-once`
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
| ttfmc (= TTFT) | 330 | 9681 | 11432 | 17585 |
| ttlt | 330 | 9681 | 11432 | 17585 |
| state | 330 | 9681 | 11432 | 17585 |
| total | 330 | 9681 | 11432 | 17585 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 435 | 517 | 4.9% |
| context | 0 | 0 | 0.0% |
| narrator | 3878 | 7416 | 49.6% |
| archivist | 5521 | 6752 | 45.5% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 180 | 9589 | 11222 |
| medium | 120 | 9825 | 12612 |
| long | 30 | 4697 | 11239 |

- tentativas LLM/turno (media): 5.712 · fallbacks: 849 · rotas: {'combat_agent': 60, 'loot': 60, 'npc_actor': 60, 'storyteller': 150}

## J1_story_simple — n=90

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 90 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 90 | 9178 | 11239 | 14196 |
| ttlt | 90 | 9178 | 11239 | 14196 |
| state | 90 | 9178 | 11239 | 14196 |
| total | 90 | 9178 | 11239 | 14196 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 460 | 522 | 8.0% |
| context | 0 | 0 | 0.0% |
| narrator | 3763 | 4237 | 49.8% |
| archivist | 5227 | 6667 | 42.2% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 8845 | 11369 |
| medium | 30 | 9713 | 11038 |
| long | 30 | 4697 | 11239 |

- tentativas LLM/turno (media): 5.1 · fallbacks: 229 · rotas: {'storyteller': 90}

## J2_combat_start — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 7205 | 16605 | 17585 |
| ttlt | 60 | 7205 | 16605 | 17585 |
| state | 60 | 7205 | 16605 | 17585 |
| total | 60 | 7205 | 16605 | 17585 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 412 | 506 | 3.6% |
| context | 0 | 0 | 0.0% |
| narrator | 6759 | 9986 | 85.5% |
| archivist | 0 | 5991 | 10.9% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 4305 | 16605 |
| medium | 30 | 7823 | 16766 |

- tentativas LLM/turno (media): 6.8 · fallbacks: 128 · rotas: {'combat_agent': 60}

## J3_npc_dialogue — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 10166 | 11465 | 12612 |
| ttlt | 60 | 10166 | 11465 | 12612 |
| state | 60 | 10166 | 11465 | 12612 |
| total | 60 | 10166 | 11465 | 12612 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 443 | 516 | 4.4% |
| context | 0 | 0 | 0.0% |
| narrator | 3703 | 5706 | 37.5% |
| archivist | 5983 | 6892 | 58.1% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| medium | 60 | 10166 | 11465 |

- tentativas LLM/turno (media): 6.067 · fallbacks: 180 · rotas: {'npc_actor': 60}

## J4_loot_shop — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 10045 | 11312 | 11635 |
| ttlt | 60 | 10045 | 11312 | 11635 |
| state | 60 | 10045 | 11312 | 11635 |
| total | 60 | 10045 | 11312 | 11635 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 441 | 515 | 4.5% |
| context | 0 | 0 | 0.0% |
| narrator | 3908 | 4430 | 38.2% |
| archivist | 5726 | 6580 | 57.3% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 60 | 10045 | 11312 |

- tentativas LLM/turno (media): 6.5 · fallbacks: 180 · rotas: {'loot': 60}

## J5_travel_replan — n=30

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 30 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 30 | 9788 | 10894 | 10898 |
| ttlt | 30 | 9788 | 10894 | 10898 |
| state | 30 | 9788 | 10894 | 10898 |
| total | 30 | 9788 | 10894 | 10898 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 0 | 0 | 0.0% |
| context | 0 | 0 | 0.0% |
| narrator | 3802 | 4450 | 39.0% |
| archivist | 5968 | 6857 | 61.0% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 9788 | 10894 |

- tentativas LLM/turno (media): 4.0 · fallbacks: 60 · rotas: {'storyteller': 30}

## J6_first_turn_new_game — n=30

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 30 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 30 | 4482 | 11222 | 11449 |
| ttlt | 30 | 4482 | 11222 | 11449 |
| state | 30 | 4482 | 11222 | 11449 |
| total | 30 | 4482 | 11222 | 11449 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 450 | 499 | 6.8% |
| context | 0 | 0 | 0.0% |
| narrator | 3777 | 4290 | 56.7% |
| archivist | 0 | 6842 | 36.5% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 4482 | 11222 |

- tentativas LLM/turno (media): 4.8 · fallbacks: 72 · rotas: {'storyteller': 30}

