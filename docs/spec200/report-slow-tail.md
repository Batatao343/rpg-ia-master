# Baseline de latencia percebida (SPEC-200)

## Fingerprint de ambiente

- `git_sha`: `afe98941a541dc5643b1f2f1f4ef3ba7563fcca6`
- `mode`: `offline-virtual`
- `profile`: `slow-tail`
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
| ttfmc (= TTFT) | 330 | 6728 | 18946 | 29069 |
| ttlt | 330 | 6728 | 18946 | 29069 |
| state | 330 | 6728 | 18946 | 29069 |
| total | 330 | 6728 | 18946 | 29069 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 292 | 1086 | 4.2% |
| context | 0 | 0 | 0.0% |
| narrator | 2704 | 10621 | 48.5% |
| archivist | 3643 | 15758 | 47.2% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 180 | 6776 | 19216 |
| medium | 120 | 6761 | 18756 |
| long | 30 | 6351 | 12012 |

- tentativas LLM/turno (media): 3.139 · fallbacks: 0 · rotas: {'combat_agent': 60, 'loot': 60, 'npc_actor': 60, 'storyteller': 150}

## J1_story_simple — n=90

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 90 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 90 | 6403 | 18883 | 29069 |
| ttlt | 90 | 6403 | 18883 | 29069 |
| state | 90 | 6403 | 18883 | 29069 |
| total | 90 | 6403 | 18883 | 29069 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 303 | 1213 | 6.5% |
| context | 0 | 0 | 0.0% |
| narrator | 2599 | 10636 | 47.0% |
| archivist | 3272 | 15681 | 46.6% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 6249 | 19704 |
| medium | 30 | 6514 | 18883 |
| long | 30 | 6351 | 12012 |

- tentativas LLM/turno (media): 2.556 · fallbacks: 0 · rotas: {'storyteller': 90}

## J2_combat_start — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 6246 | 14735 | 27300 |
| ttlt | 60 | 6246 | 14735 | 27300 |
| state | 60 | 6246 | 14735 | 27300 |
| total | 60 | 6246 | 14735 | 27300 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 270 | 358 | 2.9% |
| context | 0 | 0 | 0.0% |
| narrator | 5917 | 12268 | 83.1% |
| archivist | 0 | 4532 | 14.0% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 3184 | 13150 |
| medium | 30 | 6551 | 26602 |

- tentativas LLM/turno (media): 4.667 · fallbacks: 0 · rotas: {'combat_agent': 60}

## J3_npc_dialogue — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 6963 | 18266 | 24219 |
| ttlt | 60 | 6963 | 18266 | 24219 |
| state | 60 | 6963 | 18266 | 24219 |
| total | 60 | 6963 | 18266 | 24219 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 300 | 1145 | 4.4% |
| context | 0 | 0 | 0.0% |
| narrator | 2528 | 4958 | 35.8% |
| archivist | 3904 | 15016 | 59.8% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| medium | 60 | 6963 | 18266 |

- tentativas LLM/turno (media): 3.067 · fallbacks: 0 · rotas: {'npc_actor': 60}

## J4_loot_shop — n=60

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 60 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 60 | 7524 | 20504 | 22078 |
| ttlt | 60 | 7524 | 20504 | 22078 |
| state | 60 | 7524 | 20504 | 22078 |
| total | 60 | 7524 | 20504 | 22078 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 308 | 1056 | 3.8% |
| context | 0 | 0 | 0.0% |
| narrator | 2740 | 10452 | 35.0% |
| archivist | 4230 | 17182 | 61.2% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 60 | 7524 | 20504 |

- tentativas LLM/turno (media): 3.5 · fallbacks: 0 · rotas: {'loot': 60}

## J5_travel_replan — n=30

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 30 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 30 | 6739 | 14727 | 18946 |
| ttlt | 30 | 6739 | 14727 | 18946 |
| state | 30 | 6739 | 14727 | 18946 |
| total | 30 | 6739 | 14727 | 18946 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 0 | 0 | 0.0% |
| context | 0 | 0 | 0.0% |
| narrator | 2606 | 10697 | 46.0% |
| archivist | 4022 | 4794 | 54.0% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 6739 | 14727 |

- tentativas LLM/turno (media): 2.0 · fallbacks: 0 · rotas: {'storyteller': 30}

## J6_first_turn_new_game — n=30

| metrica (ms) | n | p50 | p95 | max |
|---|---|---|---|---|
| ack | 30 | 0 | 0 | 0 |
| ttfmc (= TTFT) | 30 | 3165 | 7932 | 10270 |
| ttlt | 30 | 3165 | 7932 | 10270 |
| state | 30 | 3165 | 7932 | 10270 |
| total | 30 | 3165 | 7932 | 10270 |

| fase | p50 | p95 | participacao |
|---|---|---|---|
| router | 304 | 1102 | 7.5% |
| context | 0 | 0 | 0.0% |
| narrator | 2524 | 2967 | 57.0% |
| archivist | 0 | 4712 | 35.5% |
| persistence | 0 | 0 | 0.0% |
| other | 0 | 0 | 0.0% |

| entrada | n | ttfmc p50 | ttfmc p95 |
|---|---|---|---|
| short | 30 | 3165 | 7932 |

- tentativas LLM/turno (media): 2.4 · fallbacks: 0 · rotas: {'storyteller': 30}

