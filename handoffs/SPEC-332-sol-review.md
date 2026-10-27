# SPEC-332 — revisão sol (review)

> **Veredito:** `APPROVED` (re-revisão do delta `302d9dcd`; 1ª rodada: `APPROVED_WITH_FOLLOWUPS` em `894d4a83`)
> **Revisor:** Sol (Claude Opus, spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `894d4a83` → `302d9dcd`

## Escopo

Branch `spec-332`, `main...HEAD` (1 commit, 25 arquivos): `services/enemy_decks.py` (novo),
`services/conflict_orchestrator.py` (`ensure_combat_sheet`, `enemy_declaration`,
`_enemy_deck_declaration`, `_enemy_offensive_card`, `_run_round`), `services/enemy_intent.py`
(`public_round`), `agents/combat.py` (forecast do Presságio), `services/bestiary_knowledge.py`,
`services/content_validator.py`, 11 baralhos + `_decks.json`, testes novos e os dois testes de
equivalência/lint alterados. Revisado contra R1, R3–R7 e "Entrega 1 e desvios". Fora: R2
(facções), `fases` autoradas, UI (SPEC-334), arena (só li o doc de resultados).

### Conferência pedida pelo coordenador

- **(a) `off` idêntico — OK.** `apply_deck` retorna antes de tocar a ficha (`enemy_decks.py:210-212`);
  `enemy_declaration` só entra no plano com `active()`; `_enemy_offensive_card` com `kinds=None,
  rotate=0, skip=None` devolve o primeiro candidato como antes (a lista `found` não é usada);
  `apply_phases` devolve `False` em `off`, então `frozen` usa o congelado como antes; no nó,
  `scene_state=None` (igual ao default anterior) e `public_round` sem `prenuncio`; `public_panel`
  não ganha `costuma`. Golden das 308 legadas verde; save não ganha campo em `off`
  (`test_off_leaves_cards_untouched`, `test_phases_inert_when_flag_off`). `shadow` não muda
  decisão (só `_deck_shadow`/`_deck332` na ficha e `out["decks_shadow"]`).
- **(b) Testes de equivalência/lint — legítimo, sem afrouxamento.** `legacy_cards()` exclui
  `cartas-332`, mas `test_equivalencia_das_308...` ainda exige `len(legacy) == len(golden) == 308`
  e diff vazio; `test_card_lint` mantém 323 nas não-`inf_`. Em `content_validator.py:755` a
  inclusão de `cartas-332` na tupla **endurece** (as cartas novas passam pelas checagens plenas:
  orçamento, id duplicado, patamar, frequência, tipo, kind). Nada em `evals/` protegido mudou.
  Sugestão de robustez em P2-5.
- **(c) Assinatura × Presságio congelado — OK no caso base; frágil com fases** (P2-1, P2-2).
  Rodada coerente: o nó prevê com `_rodada_decisao = tactical_round+1` e a execução usa
  `tactical_round` após `advance_tactical_state` (mesmo número). `prenuncio` sai no Presságio da
  rodada r+1 avisando a assinatura de r+2, que entra no congelado de r+2 e é executada.
  Invalidação por fase não é reroll explorável: fase só avança (monotônica, 1× por limiar).
- **(d) Determinismo — OK.** SHA-256 de `id|seed|rótulo` (sem `hash()`/PYTHONHASHSEED, sem rng);
  `rotate_index` e `_sig_falls_on` puros; forecast em sandbox não muta. `deck_seed` não é
  escrito em lugar nenhum (seed sempre 0; ver P2-4).
- **(e) Reforços — OK.** Nenhum kind de invocação nas 88 cartas (dano 25, aplicar_condicao 23,
  marca 7, protecao 7, dot 5, reposicionar 5, buff_* 8, empurrao 3, taunt 3, esconder 2);
  `fases` só acrescentam cartas existentes; slot `mover` devolve ao perfil.
- **(f) Lint/orçamento/voz — OK.** `test_new_enemy_cards_pass_vocabulary_budget_and_voice` e
  `validate_content.py` (cards 0 erros). Desvio R7 (sem faixa própria de inimigo) registrado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/conflict_orchestrator.py:2191-2207`, `agents/combat.py:2268-2283` | A fase é aplicada no INÍCIO da rodada seguinte, mas o Presságio dessa rodada foi previsto no fim da anterior com a fase velha (a Vitalidade já estava abaixo do limiar). Resultado: toda troca de fase mostra ao jogador um Presságio que nunca se cumpre, e o "presságio novo" do R5 é executado sem nunca ter sido exibido. | Aplicar `apply_phases` no fim de `_run_round` (após o dano) ou no nó antes do `forecast_round`; aí o congelado já nasce na fase nova e a invalidação deixa de ser necessária. Obrigatório antes de autorar `fases` nos chefes. |
| P2-2 | P2 | `services/enemy_decks.py:265-274`, `:247-262` | A assinatura de uma fase nova pode cair na rodada em que a fase entra, sem `prenuncio` (calculado com a assinatura da fase anterior). Também: com `RPG_ENEMY_DECKS=on` e `RPG_ENEMY_INTENT=off` não há telegrafia nenhuma (o `prenuncio` só existe dentro de `pressagios_publicos`). R4 exige "telegrafada 1 rodada antes". | Exigir rodada de entrada + 1 para a assinatura da fase (ou resolver junto com P2-1); documentar/forçar que `on` dos baralhos requer Presságio `on` (ou emitir o telegrafo em `out.logs` quando o Presságio está `off`). |
| P2-3 | P2 | `services/enemy_decks.py:211-219` | `shadow` marca `_deck332=True`; ao virar a flag para `on` no meio da campanha, inimigos já normalizados em `shadow` nunca recebem o baralho. Inversamente, sem `_deck332` (ficha reconstruída) a montagem não é idempotente (próprias passam a incluir as da família e soma mais 3-5: 7 → 9 cartas no probe). Não há teste de round-trip save/load de `_deck332`/`fase_idx`. | Marcadores separados (`_deck332_shadow` × `_deck332`) e teste de round-trip (save → load → `ensure_combat_sheet` não altera `cartas` nem `fase_idx`). |
| P2-4 | P2 | `services/enemy_decks.py:213`, `:252` | `deck_seed` nunca é gravado: o seed é sempre 0, então `lobo_1` monta o mesmo baralho em toda campanha (o R3 fala em "id + seed"). O teste "≤ 15 criaturas" usa o id do bestiário, mas em runtime o id é `<base>_<n>` (`agents/combat.py:676`), logo a distribuição medida não é a do jogo. | Gravar `deck_seed` a partir do `game_id`/seed do encontro no spawn; no teste, medir também com ids `<base>_1`. |
| P2-5 | P2 | `tests/spec330_equivalence.py:127-133` | Filtro por `origem` exige editar o helper a cada spec nova de cartas (já são 2). Não afrouxa (o `== 308` segura), mas é frágil. | Filtrar pelas chaves do golden (`cid in golden`) e manter, em teste separado, que toda carta fora do golden está no formato novo ou tem origem pós-golden conhecida. |
| P2-6 | P2 | `services/enemy_decks.py:384-386` | R6 diz "após 1 conflito com a família"; `known_pattern` usa `revealed_cards` do ator, que acende já no 1º conflito, assim que o inimigo usa uma carta, e é por arquétipo (não por família). No perfil hosted o conhecimento persistido não é carregado. Desvio parcialmente registrado na spec. | Registrar a semântica real na spec ou ligar a um contador de conflitos por família no `bestiary_knowledge` (SPEC-334). |
| P2-7 | P2 | `services/enemy_intent.py:299-305`, `services/bestiary_knowledge.py:47-51` | `prenuncio` e `costuma` não são renderizados no `web/` (nenhuma referência em `web/src`). Smoke real 1 e 2 da spec não são observáveis pelo jogador ainda. | Front na SPEC-334 antes de `on`; anotar no ESTADO. |
| P2-8 | P2 | `services/conflict_orchestrator.py:514-529` | Com plano ativo, um perfil cujo `sempre` é `control` tem o controle tático trocado pelo slot do padrão (só `support/flank/protect/stabilize` são preservados). Hoje nenhum perfil do bestiário tem `sempre`→`control` explícito, mas a regra é implícita. | Incluir `control` no conjunto preservado ou documentar a precedência no docstring de `plan`. |

Sem P0/P1: tudo atrás de `RPG_ENEMY_DECKS` (default `off`, byte-idêntico), nenhuma fase autorada,
nenhum valor de LLM novo, nenhum structured output novo, nenhum segredo em log.

## Correções aplicadas

Re-revisão do delta `7f3a6a72..302d9dcd` (Sol, 27/10): **APPROVED**.

- **P2-1 — corrigido.** `apply_phases` roda também no fim de `_run_round` (`conflict_orchestrator.py:2461`), depois do dano e antes do forecast do nó, e grava `fase_rnd`. Não há aplicação dupla: a fase é monotônica (`reached <= current` → `continue`), e a chamada do início da rodada só dispara se algo (tick de cena/Abismo) cruzar um limiar entre as duas chamadas. O spy de `test_phase_applied_at_end_of_round_before_next_forecast` confirma 2 chamadas por rodada e uma só narração.
- **P2-2 — corrigido.** A assinatura de fase leva `_fase`, e `_sig_falls_on` exige `rnd >= fase_rnd + 1`. O `prenuncio` vai a `out.logs` quando o Presságio não está `on` (gate `edk.active()`, `ei` importado antes no mesmo escopo, `_alive(None)` seguro).
- **P2-3 — corrigido.** Os marcadores agora são separados (`_deck332_shadow` × `_deck332`), e há teste de round-trip JSON com e sem o marcador. Resta uma ressalva, que registro como **F-1** abaixo.
- **P2-4 — corrigido.** `deck_seed = crc32(game_id|turn_count|target_hint)` é gravado em `_instances` só quando o modo não é `off`, e o limite de 15 é testado com ids `<base>_1`.
- **P2-5 — corrigido.** `legacy_cards()` filtra pelas chaves do golden, e `test_equivalencia_das_308...` segue exigindo `len(legacy) == len(golden) == 308` com diff vazio (o caso da carta legada removida continua coberto).
- **P2-8 — corrigido.** `control` entrou no conjunto preservado.
- **`off` byte-idêntico — confirmado.** `apply_deck` sai no topo; `apply_phases` devolve False sem tocar a ficha; o log de `prenuncio` é gated por `active()`; o spawn não grava `deck_seed` (`_deck_seed=None`); `enemy_declaration` não mudou no caminho `off`. Golden 308 verde, e os testes de spawn/encontro também verdes.

Follow-ups novos (P2, não bloqueiam):
- **F-1** (`enemy_decks.py:217-223`): a heurística "ficha já tem carta `inf_*`/facção → já montada" faz o baralho ser pulado em silêncio se a curadoria do bestiário (próximo lote, desvio do critério 1) puser cartas `inf_*` nas `cartas` próprias de uma criatura. Correção: decidir por `_deck332`, e usar a heurística só se o marcador faltar **e** a ficha tiver mais cartas da família do que o bestiário dá; ou exigir no `validate_content` que o bestiário não referencie `inf_*`.
- **F-2** (`tests/spec330_equivalence.py:124-131`): `build_golden()` agora depende do próprio golden, então não dá para regenerá-lo do zero (aceitável: o golden é congelado pré-330). Também deixou de existir a guarda "carta nova em formato legado sem `efeitos`". Sugestão: um teste curto em que toda carta fora do golden tem `efeitos` ou origem pós-golden conhecida.
- P2-6 e P2-7 seguem como follow-ups registrados na spec (SPEC-334).

## Pendências

- P2-1/P2-2: antes de autorar `fases` nos 11 chefes (próximo lote da 332).
- P2-3/P2-4: antes de `RPG_ENEMY_DECKS=on` no staging.
- P2-7: SPEC-334 (painel/presságio no front).
- P2-5, P2-6, P2-8: higiene; podem ir no próximo lote da 332.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_spec283_enemy_support_cards.py tests/test_scene_cards_node.py tests/test_enemy_decks.py tests/test_boss_phases.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_error_envelope.py tests/test_card_effects_grammar.py tests/test_card_lint.py → 148 passed in 17.62s
bash scripts/dev/py.sh scripts/validate_content.py → 0 erros, 0 avisos
probe (scratch, removido): famílias no bestiário 21/15/15/15/14/12/11/10/6/5, abissal 0; kinds das 88 cartas sem invocação; rebuild sem _deck332 7→9 cartas
re-revisão 302d9dcd: mesmo conjunto de 11 arquivos -n 2 → 155 passed in 14.53s
re-revisão 302d9dcd: tests/test_encounter_identity_repro.py tests/test_encounter_manifest.py tests/test_spec272_conflito_ligado.py -n 2 → 38 passed in 3.60s
```
