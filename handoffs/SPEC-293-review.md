# SPEC-293 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (revisão independente) · **Data:** 2026-10-19 · **Commit revisado:** `54c5dd5` (+ correção `13aa80d`)

## Escopo

Branch `spec-293` sobre `main` `858caa0`: `services/faction_display.py` (novo), `api.py`
(`format_response`, `/game/history`, `/game/chronicle/search|export`),
`services/player_knowledge.py` (projeção + oráculo (e)), `services/dossiers.py`,
`agents/combat.py` (`_concealed_species`), testes `tests/test_spec293_rotulo_faccao.py`.
Conferi R1–R7 contra o código, o caminho SSE (`_stream_turn_events`: `chunk` só emite
`phase`/`route`; `visual`/`narrative`/`state` saem do `resp` já projetado), recibos de
operação/replay (gravam `response.model_dump` já projetado), alvo no cliente
(`web/src/combat/targeting.ts` manda `target_id`; `valid_targets` são ids slug) e o contrato
do `GameResponse` (sem alias/exclude/validators; `model_validate` pós-dump preserva tipos e
`VisualResponse`). Fora: frontend, CLI, audit/account export (canônicos por design).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/faction_display.py:_pattern` (orig.) | A projeção só casava a grafia exata (caixa à parte). Prosa do LLM com quebra de linha/espaço duplo, sem acento ("Destilacao"), hífen↔espaço ("Druida Renegado") ou **plural** ("Dois Iniciados da Chama Azul", natural com instâncias numeradas) passava em todas as superfícies; o oráculo (e) normaliza e pegava 3 desses casos, mas o plural escapava dos dois. | **Corrigido em `13aa80d`**: regex por nome tolera caixa, acento, `[\s-]+` entre palavras e plural `s/es` nas palavras de conteúdo; o rótulo herda o plural ("Iniciados", "Degoladores", "Combatentes desconhecidos"). 8 casos novos parametrizados. |
| P2-1 | P2 | `services/faction_display.py:209` | Oráculo (e) usa substring normalizada sem fronteira: "Iniciado da Chama Azulado" acusa vazamento que a projeção (corretamente) não troca. Mais estrito que a projeção — falso positivo só em texto artificial. | Follow-up opcional: fronteira de palavra no oráculo **sem** perder o plural (mexe na régua de eval → relock). |
| P2-2 | P2 | `api.py:2685`, `services/combat_targeting.py:56` | Inimigo sem `id` (save legado) usa o nome como id: `enemies[].id`/`participant_id` ficam canônicos (chave protegida → vaza) e `valid_targets`/`engaged_with` (chaves não protegidas) viram rótulo → mira do cliente não casa. Todos os spawns atuais setam `id` (`_instances`), então é só legado. | Follow-up: backfill de `id` no load/spawn, ou id estável derivado do slug. |
| P2-3 | P2 | `api.py:3357` (`/data/combat-simulator`) | O laboratório lista o bestiário inteiro com nomes canônicos para qualquer usuário (não é estado de observador). Pré-existente, fora do R3. | Decisão do dono: aceitar (lab) ou projetar com intel vazio. |
| P2-4 | P2 | spec §R3 | A spec diz que equip/levelup/cards passam por `format_response`; não passam (montam dict próprio). Os payloads não têm nome de inimigo, então não há vazamento — só texto impreciso. | Ajustar o texto da spec no pouso. |
| P2-5 | P2 | `services/faction_display.py:53` | `concealed_name_map` percorre o bestiário (124) a cada resposta: ~3,5 ms extras por `format_response` medidos (0,4 → 3,9 ms). Desprezível frente ao turno; codex/dossiês recalculam 2×. | Opcional: cache por `(id(factions), intel known-set)`. |

Sem P0. Não achei superfície player-facing que escape além de P2-2/P2-3: `/game/new`,
`/game/death`, `/game/state`, POST/SSE, replay legado e de banco, `combat_result`,
`turn_outcome`, `speaker`, `visual.cue`, crônica no payload, histórico, busca/export da
crônica, codex e dossiês estão cobertos. `/game/saves` (SaveSummary) não tem nome de
inimigo; ofertas de arte expõem só `offer_id/type`; `/game/map` não lê bestiário.
Substituição não corrompe ids (`id`, `*_id`, `*_ids` intactos; ids são slugs com `_`, que é
`\w` e barra a fronteira), nomes de NPC/local (só o nome completo da criatura casa) nem o
fluxo de alvo (resolução por `target_id`). Evals: rodar todos os datasets dá a mesma
`hard_failure` do fixture `governance.exact.bad` na base e com a correção; métricas de
vazamento (`player_knowledge_leak_count`, `dossier_leak_count`, `secret_leak_count`) = 0.

## Correções aplicadas

- `13aa80d` — P1-1 (projeção tolerante a espaço/acento/hífen/plural + testes).

## Pendências

- P2-1 (oráculo com fronteira, exige relock de eval) e P2-2 (id de inimigo legado):
  coordenador decide spec de destino.
- P2-3: decisão do dono.
- P2-4: corrigir o texto de R3 no pouso.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec293_rotulo_faccao.py + dossier_leak/dossiers/dossiers_api/player_knowledge/eval_player_knowledge/eval_dossier_leak/chronicle_search/presentation_history/encounter_manifest/eval_encounter_manifest/spec289/streaming/speaker_contract/turn_outcome_endpoints → todos verdes (antes e depois da correção)
bash scripts/dev/py.sh -m pytest -q ... test_hardening_persistencia_sse.py test_surfaces_221.py test_visual_assets.py → verdes
bash scripts/dev/py.sh -m evals run (base com stash e com a correção) → mesma hard_failure de fixture governance.exact.bad; leak metrics 0
bash scripts/dev/py.sh -m ruff check / format --check (arquivos tocados) → ok
scratchpad perf.py → format_response 0,4 ms raw vs 3,9 ms projetado
```
