# SPEC-390 — revisão sol (review)

> **Veredito:** `APPROVED` (rodada 3; rodadas 1–2: `CHANGES_REQUIRED`)
> **Revisor:** Opus 5.5 / Sol · **Data:** 2026-11-04 · **Commits revisados:** `c26c7ea3` (rodada 1), `3ff37fb4`+`44ef8483` (rodada 2), `76743a61` (rodada 3)

## Escopo

`git diff main...spec-390` (1 commit `c26c7ea3`): `services/round_log.py` (`_voce`, `_taunt_lines`),
`services/turn_outcome.py` (`_quest_titles`, `finalize_outcome`, `public_outcome`), `tests/test_spec390_text.py`
e §9 da spec. O smoke real §6 ficou fora (é do coordenador).

O que está correto:
- **R2.** O `receipt_id` é calculado antes de `quest_titles` (`turn_outcome.py:257-263`), então o hash não muda. O teste
  troca o título e compara o `receipt_id`. `quests_completed` continua `list[str]`. `public_outcome` lê o mapa e cai no id
  quando ele falta, o que cobre o save antigo e tem teste. O campo é `dict[str,str]` serializável; `public_outcome` é
  whitelist, então `quest_titles` não vaza cru. O `outcomeToast` já usa `title`.
- **R3.** O ramo da vítima "Você" fica isolado e o texto de vítima inimiga não muda (`test_spec353_registry`/`smoke7`
  verdes). Pela API, a seed `13 armadura` produz "Você está provocado por …" (verificado pela varredura abaixo).
- **R1 (parcial).** A linha "provocado por <herói>, muda de alvo." vira "provocado por você"; com outro ator, o nome fica.
- **TDD.** O executor escreveu a implementação antes dos testes. Para conferir, rodei `tests/test_spec390_text.py` contra
  a `main` num worktree descartável: os 6 testes de comportamento **falham** (R1, R3, R2×2, API voto, API entrega). Os 2
  testes de guarda (outro ator, vítima inimiga) passam, como deveriam.
- Sem flag nova, sem LLM, sem `except`, sem segredo. `conflict_orchestrator.py`/`api.py`/`agents/npc.py` não foram
  tocados. `dup_helpers`: nenhum nome repetido. As funções novas são curtas e `round_log.py` (934 linhas) fica abaixo de 1.000.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/round_log.py:249-252` (origem `services/conflict_orchestrator.py:2743`) | O nome do herói ainda aparece na seed `13 voto`. A outra saída do Voto, "Goblin resiste à provocação de Smoke368.", passa por `_HUMAN_LINE_RES` (`round_log.py:51`) e não é convertida. Varredura com a API real e MockLLM, 6 sementes: 3 ocorrências na mensagem de `/game/action`. Isso quebra o R1 ("a linha do Voto/Provocação não traz o nome do herói") e o R4 ("nome do herói 0× nas superfícies da `13 voto`"). | Em `_voce`, converter também `^(.+?) resiste à provocação de {hero}\.$` → `"{X} resiste à sua provocação."` (ou "à provocação de você"; o mesmo ponto único do R1). O nome de outro ator fica. |
| P1-2 | P1 | `tests/test_spec390_text.py:84-85` | A guarda do R4 é estreita demais: só afirma `f"provocado por {HERO}" not in text`, e por isso não pegou o P1-1. Também falta o que o R4 exige pela API: (a) a seed `13 armadura` (o R3 pela API, com "Você está provocado por" e herói 0×); (b) id cru nas superfícies de `13 voto`/`13 armadura`. | Varrer as superfícies de texto (mensagem/registro de `/game/action` e entradas de `/game/history`) sem `player_stats.name`, que é dado legítimo, e afirmar `HERO not in` em cada uma. Parametrizar `voto` e `armadura`, com regex de id (`\w+_\w+`, hex de 24) como na varredura do smoke-local 389 item 11. Adicionar teste unitário para a linha "resiste". |
| P2-1 | P2 | `tests/test_spec390_text.py` | O BRIEF/TESTES.md pede que teste novo não use o nome `test_specNNN_*.py`. A spec (§4) pediu esse nome, então isto não bloqueia. | De preferência, mover para `tests/test_combat_text_smoke8.py` ou para dentro de `test_combat_text_smoke7.py`, com a spec na docstring. |

## Correções aplicadas

- P1-1: `44ef8483`. P1-2: `44ef8483`. P2-1: `3ff37fb4` (renomeado para `tests/test_combat_text_smoke8.py`).

## Pendências

Nenhuma aceita como follow-up (política zero pendência): P1-1 e P1-2 precisam entrar nesta branch.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_spec390_text.py tests/test_spec353_registry.py tests/test_combat_text_smoke7.py tests/test_spec355_provocacao_rodada.py tests/test_turn_outcome_endpoints.py tests/test_spec363_rare_scenarios.py → 122 passed
worktree descartável da main + tests/test_spec390_text.py (pytest -p no:xdist) → 6 failed / 2 passed (os testes provam a mudança)
varredura temporária (removida) 13 voto/armadura × 6 sementes via TestClient → voto: "Goblin resiste à provocação de Smoke368." 3×; armadura: "está provocado por" presente, sem herói no texto
bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
```

## Rodada 2

Revisado `git diff 6024192b..spec-390` (`3ff37fb4`, `44ef8483`).

**Fechados:**
- **P1-1.** `_voce` passa a converter "X resiste à provocação de <herói>." em "X resiste à sua provocação."; com outro ator,
  o nome fica (há teste unitário). `_HUMAN_LINE_RES` aceita as duas formas. A regex ficou um pouco mais larga
  (`(?: de )?` opcional também casa "resiste à provocação" seguido de qualquer coisa), mas só a linha do motor chega com
  esse texto, então não há risco prático.
- **P1-2.** O teste da API está parametrizado em `voto`/`armadura`, com varredura de nome do herói e de id cru.
  **Prova de que pega a regressão:** rodei `tests/test_combat_text_smoke8.py` contra o código da rodada 1 (`6024192b`) num
  worktree descartável: `test_voce_resiste_a_provocacao_do_heroi` e `test_voto_api_never_shows_hero_name_or_raw_id[voto]`
  **falham**.
- **P2-1.** O arquivo foi renomeado e a spec (§4/§9) foi atualizada.

**Julgamento da exclusão de `narrative_summary`: aceita.** Fiz um inventário completo das chaves de `/game/action` e de
`/game/history` (6 sementes × 2 seeds). O nome do herói só aparece em `narrative_summary` ("A jornada de Smoke368 começa
em Nova Arcádia.", a prosa de abertura determinística, em 3ª pessoa por design) e em `participant_name`, que é dado e não
texto de registro. Nenhuma superfície de combate traz o nome.

**Julgamento da regex de id (`[a-z]{2,}(?:_[a-z0-9]+)+`; no código não tem o `\b` citado no hand-back):**
- *Falso positivo:* praticamente nenhum em prosa PT. Sem `\b` a regex fica até mais sensível (casa o sufixo de
  `Enemy_goblin`), o que é aceitável para uma guarda.
- *Falso negativo:* ids de uma palavra só (`q368`) e hex de 24 (`[0-9a-f]{24}`, formato dos `id` do histórico). Hoje
  nenhum dos dois aparece em chave de texto (varredura abaixo), e o `q368` do recibo já é coberto pela igualdade de título
  no teste da `14 entrega`.

**Achado novo:**

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-2 | P2 | `tests/test_combat_text_smoke8.py:96` (`_TEXT_KEYS`) | A lista de chaves varridas tem 3 nomes que não existem nas respostas (`registro_rodada`, `last_mech_log`, `last_turn_log`) e deixa de fora superfícies reais: **`mech_log`**, que o R1 cita nominalmente, e `content`, `texto`, `description`, `resultado`, `title`, `label`, `sinal`, `prenuncio`. Hoje a guarda pega a regressão só porque a linha também vai para `message`. Se ela sair só no `mech_log` ou no conteúdo do Livro, passa sem ser vista. | Trocar `_TEXT_KEYS` pelas chaves reais: `{"message","mech_log","content","text","texto","efeito","description","resultado","title","label","sinal","prenuncio"}`. Opcional: somar `\b[0-9a-f]{24}\b` à `_RAW_ID`. Varri essa lista ampliada (+ `reason`, `climax`, `objective`, `arc_title`, `suggestions`, `status` etc.) nas duas seeds × 6 sementes: **0 nome do herói e 0 id**, só `reason="classify_story"` (metadado do responder, que não deve entrar). A troca passa sem mexer em produto. |

Com a política de zero pendência, o P2-2 entra nesta branch: é a troca de uma constante de teste. O código de produto
(`round_log.py`, `turn_outcome.py`) está aprovado. Depois do P2-2, o veredito passa a `APPROVED` sem nova rodada de
revisão completa; basta rodar o arquivo de teste.

### Comandos da rodada 2

```text
worktree descartável em 6024192b + tests/test_combat_text_smoke8.py (pytest -p no:xdist) → 2 failed (resiste unit + API voto): a guarda prova o P1-1
varredura temporária (removida) de todas as chaves, voto/armadura × 6 sementes → herói só em narrative_summary/participant_name; ids só em chaves *_id/id
varredura temporária (removida) com as chaves de texto ampliadas → 0 herói, 0 id (fora reason=classify_story)
bash scripts/dev/pt.sh tests/test_combat_text_smoke8.py tests/test_error_envelope.py tests/test_no_silent_except.py tests/test_log_event_registry.py tests/test_size_budget.py tests/test_spec353_registry.py tests/test_combat_text_smoke7.py tests/test_spec355_provocacao_rodada.py tests/test_spec363_rare_scenarios.py tests/test_spec387_seed.py tests/test_turn_outcome_endpoints.py → 183 passed
```

## Rodada 3

Revisado `git show 76743a61`, que só mexe em `tests/test_combat_text_smoke8.py`:
- **P2-2 fechado.** `_TEXT_KEYS` agora tem as superfícies reais (`message`, `text`, `efeito`, `mech_log`, `content`, `texto`,
  `description`, `resultado`, `title`, `label`, `sinal`, `prenuncio`), a mesma lista que a rodada 2 varreu limpa.
  `reason` continua fora. `_RAW_ID` soma `\b[0-9a-f]{24}\b`. Produto não foi tocado.
- Nenhum achado aberto: P1-1, P1-2, P2-1 e P2-2 fechados. O smoke real §6 continua com o coordenador.

**Veredito final: `APPROVED`.**

```text
bash scripts/dev/pt.sh tests/test_combat_text_smoke8.py → 10 passed
```
