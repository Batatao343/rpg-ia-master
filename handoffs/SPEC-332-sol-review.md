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

## Lote 2 (revisão de `7137cc44`)

> **Veredito (lote 2):** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `7137cc44`

### Escopo

Branch `spec-332`, `main...7137cc44` (19 arquivos): 10 `faccao_*.json`, `chefes.json`, `_decks.json`
(`faccoes`, `legadas_compartilhadas`, `fases`), `lider_matilha.json`, `services/enemy_decks.py`
(`_pools`, `_curate_shared`, F-1, `_sorted_phases`), `docs/spec332/arena_familias.py` (`--only`), testes
`test_enemy_decks.py` e `test_boss_phases.py`, e a spec. Ficou fora: o front (SPEC-334) e a suíte completa (fica com o coordenador).

Conferência pedida pelo coordenador:

1. **`off` idêntico.** OK. `apply_deck`/`apply_phases`/`padrao_publico` retornam cedo em `off`; o fallback de
   `_sorted_phases` só é lido quando `fase_idx > 0`, que só `apply_phases` (`on`) grava. O `bestiary.json` não muda
   e nenhuma criatura referencia `inf_fac_*`/`inf_chefe_*`/`inf_lider_matilha_*`. O golden da 330
   (`test_card_effects_grammar`) passa. Nenhuma chave nova na ficha nem no save em `off`.
2. **Cartas no motor real.** Todos os `kind` novos já existiam nas famílias da Entrega 1 e chegam a
   `conflict_turn` (`_ATTACK_EFFECTS`/`_SUPPORT_EFFECTS`; as condições estão em `NAMED_CONDITIONS` ou `card_effects`).
   A exceção é `cura` (P1-2).
3. **Fases telegrafadas x Presságio.** O mecanismo segue o da Entrega 1 (`fase_rnd`, assinatura só depois de uma
   rodada telegrafada). O conteúdo, porém, põe a fase 2 numa faixa de vida em que o chefe solo foge (P1-1).
4. **Hash determinístico.** OK. `build_enemy_deck` dá o mesmo resultado nas duas chamadas para todo o bestiário. Com
   o marcador `_deck332` removido (ficha reconstruída), `ensure_combat_sheet` é idempotente para as 124 criaturas
   em 6 seeds (0 divergências). O F-1 com ≥ 3 cartas funciona porque toda criatura tem família (0 sem família).
5. **`_pools`.** Nenhum pool se perde: os 11 arquivos de família da `main` estão todos em `FAMILIAS`. Ver P2-5.
6. **Nomes.** Não há colisão de id com a `main` (456 cartas), mas há 2 colisões de nome (P1-3).
7. **Arena.** É reproduzível: duas execuções em processos separados (`2 --levels 3 --per-family 2 --only
   lider_matilha,guardiao`) deram JSON idêntico, sem contar `elapsed_s`.

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `data/cards/inimigos/_decks.json:222` (fases 30 % dos 12 chefes) + `services/conflict_orchestrator.py:449,463,521` | A fase 2 entra a 30 %, mas `badly_wounded` vale para `_vitality_ratio <= 0.35`. Em 10 chefes a 1ª prioridade é `plano_falhou` (ferido e sozinho → `flee`); em `mon_mae_micelio` e `mon_eclipse_caminhante` é `muito_ferido`. O plano/assinatura só vale com o gatilho `sempre` (`:521`), então o chefe solo **nunca** usa a carta `inf_chefe_*` da fase 2. `prenuncio` não olha o gatilho e anuncia a assinatura mesmo assim, e na rodada seguinte o chefe foge. Isso quebra a promessa do Presságio da 329. Smoke: Valerius a 25 % → "perde a cautela" → "escapa do conflito" na mesma rodada, sem usar o Decreto. | (a) subir a fase 2 para acima de 35 % (ex.: 60/40) **ou** (b) fazer chefe em fase ≥ 1 ignorar `plano_falhou`/`muito_ferido` (o perfil do chefe na fase manda) **e** (c) fazer `prenuncio` exigir que o gatilho previsto seja `sempre`. Teste de regressão: chefe solo a 25 % na fase 2 → presságio anunciado ⇒ assinatura executada na rodada seguinte. |
| P1-2 | P1 | `data/cards/inimigos/faccao_druidas_renegados.json:5` + `services/conflict_orchestrator.py:637-639,805` | `Seiva do Ciclo` (`cura`, `ativa`) é a única carta nova cujo `kind` a IA do inimigo nunca escolhe. `_enemy_support_card` só aceita `protecao/buff_defesa/buff_*/vantagem/reposicionar`, e `_enemy_offensive_card` descarta o que não é ataque nem `esconder`. Resultado: carta morta que ocupa vaga do baralho (0-3 da facção). | Trocar o efeito por um que a IA usa (`protecao`/`buff_defesa`) **ou** incluir `cura` em `_ENEMY_DEFENSIVE_SUPPORT`, com teste de que um druida ferido a usa. Para evitar a próxima, um teste estático de que toda carta `inf_*` tem `kind` alcançável pela IA do inimigo. |
| P1-3 | P1 | `faccao_grupos_piratas_rivais.json:64`, `faccao_renegados_ermo.json:101` x `emboscador.json:63,120` | Nomes repetidos: "Areia nos Olhos" (piratas = emboscador) e "Laço no Tornozelo" (renegados = emboscador). Um pirata/renegado emboscador pode ter as duas no baralho, com nomes iguais no log, no presságio e na mão. `test_faction_cards_do_not_collide_with_player_card_names` só compara com cartas de jogador. | Renomear as duas da facção e estender o teste para **todas** as cartas (`cards.all_cards()`, inclusive `bst_*`/`inf_*`). Os nomes `san1_*` da `spec-335` ficam fora porque não estão na `main`. |
| P2-1 | P2 | `services/enemy_decks.py:202-210`; spec §5 critério 1 | A curadoria repõe `bst_bote_certeiro` com ataques da família sem olhar o uso, e empurra cartas do `predador` acima de 15. Em 50 seeds, 17 têm alguma carta não-legada com mais de 15 (contra 4 sem curadoria), e já na seed 0 há `inf_predador_rastro_de_sangue` com 16. O teste só conta `bst_bote_certeiro` nas seeds 0-3, e o `[x]` do critério 1 está exagerado. | Repor com o ataque de menor uso esperado (ou espalhar por hash entre todos os ataques da família, sem viés) e fazer o teste contar todas as cartas; senão, voltar o critério para `[~]`. |
| P2-2 | P2 | `tests/test_boss_phases.py:250` | `assert out["logs"] and "Lorde" in out["logs"][0] or out["logs"]` é quase tautológico (passa com qualquer log). | `assert any("Lorde" in l for l in out["logs"])` e conferir `out["fases"] == [{"actor_id": ..., "fase": 1}]`. |
| P2-3 | P2 | `_decks.json:222-` | Quando o dano pula as duas fases de uma vez, só a narração da última é registrada (`apply_phases` formata só `fases[reached-1]`). A narração da fase 2 é idêntica nos 12 chefes. As da fase 1 fixam o nome ("O Lorde", "A Víbora") em vez de `{nome}`. | Usar `{nome}` na fase 1, dar uma frase própria a cada fase 2 (conteúdo) e, opcionalmente, narrar a fase 1 quando as duas entram juntas. |
| P2-4 | P2 | spec §5 critério 2 | O `[x]` diz "cada facção", mas 4 facções do bestiário (`tribos_devoradores_sol`, `bandos_nomades`, `colmeia_hospedeiros`, `mercadores_escravos_pradaria`) ficam sem pool. O desvio está registrado na Entrega 2. | Marcar `[~]` e apontar para a 336, ou entregar as 4. |
| P2-5 | P2 | `services/enemy_decks.py:122` | Um arquivo novo em `data/cards/inimigos/` que não esteja em `FAMILIAS` nem comece com `faccao_` é ignorado sem aviso. Hoje só `chefes.json`, que é intencional. | Teste que liste os arquivos não reconhecidos (allowlist `{"chefes"}`) para pegar um pool órfão. |
| P2-6 | P2 | `handoffs/SPEC-332-sol-review-lote2.md` | O nome pedido não passa em `scripts/check_handoff_names.py` (o sufixo `-lote2` não está no padrão). | Coordenador: renomear/fundir em `SPEC-332-sol-review.md` no pouso ou pôr o nome no `LEGACY` do lint. |

### Correções aplicadas

Nenhuma (revisão só leitura; o executor corrige na `spec-332`).

### Pendências

- Corrigir P1-1..P1-3 e pedir re-revisão Sol. Os P2 podem ir no mesmo commit ou virar follow-up na 336 (conteúdo) e na 334 (front).
- Continuam de antes: o alvo da arena é decisão do dono, e o front de `prenuncio`/`costuma` sai na SPEC-334 antes de `on`.

### Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_enemy_decks.py tests/test_boss_phases.py tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_spec283_enemy_support_cards.py tests/test_card_effects_grammar.py tests/test_card_lint.py tests/test_card_effects_review_spec330.py → 162 passed
script ad hoc (scratchpad): idempotência sem _deck332, 124 criaturas x 6 seeds → 0 divergências; determinismo build_enemy_deck → True
script ad hoc: uso > 15 em 50 seeds → 17 seeds (lote 2) x 4 seeds (sem curadoria)
script ad hoc: colisão de id/nome contra `git show main:data/cards/**` → 0 ids, 2 nomes
arena_familias.py 2 --levels 3 --per-family 2 --only lider_matilha,guardiao (2x) → JSON idêntico
smoke ad hoc: Valerius solo a 25 % no `on` → fase 2 + presságio cumprido, depois `escapa do conflito`; Decreto não usado
```


### Correções aplicadas (executor)

P1-1, P1-2, P1-3 e P2-1..P2-6 corrigidos na `spec-332` (ver spec, "Correções da revisão Sol (lote 2)"); aguardando re-revisão.

### Re-revisão do lote 2 (delta `128edd12..ed34e595`)

> **Veredito (lote 2, re-revisão):** `CHANGES_REQUIRED`. Os P1-1..P1-3 e os P2 originais foram resolvidos, mas a correção do P1-1 introduziu a regressão P1-4.
> **Revisor:** Opus (papel Sol) · **Data:** 2026-10-27 · **Commit revisado:** `ed34e595`

Conferência dos achados:

- **P1-1 OK.** As fases agora entram a 60/40, acima do limiar de 35 %. `test_phase_two_boss_uses_signature_before_fleeing` mostra Valerius a 39 % jogando o Decreto pela `enemy_declaration` real, e `prenuncio` não promete com vida <= 35 % nem com ferimento grave/crítico.
- **P1-2 OK.** `_ENEMY_HEAL_SUPPORT` cobre o caso de si mesmo a <= 70 % e o de aliado ferido (`_ally_wounded_target` existe em `conflict_orchestrator.py:471`). Há teste estático de que todo `inf_*` pode ser escolhido pela IA. O `off` não muda, porque nenhuma carta do bestiário tem `cura`, e a Seiva é a única carta `cura` de inimigo.
- **P1-3 OK.** As cartas viraram "Poeira do Cais" e "Corda no Passo", e o teste de nomes cobre o catálogo inteiro.
- **P2 OK:**
  - P2-1: a troca entra na cota da família, o pool do `predador` foi de 8 para 12 cartas, e o teste verifica `inf_* <= 15` em 12 seeds. A spec registra a variância residual.
  - P2-2: a asserção do teste agora é real.
  - P2-3: as narrações usam `{nome}`, cada chefe tem a sua, e quando o dano pula fases todas são narradas.
  - P2-4: o critério 2 voltou para `[~]`.
  - P2-5: arquivo órfão gera log, com teste.
  - P2-6: o handoff foi fundido e `check_handoff_names.py` passa.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-4 | P1 | `services/enemy_decks.py:345` (`plan`) x `:363-364` (`prenuncio`) | **Regressão do 329: assinatura jogada sem Presságio.** A nova trava `_badly_wounded` só existe no `prenuncio`; o `plan()` continua liberando a assinatura. Em criaturas cujo perfil não tem gatilho de vida baixa antes do `sempre`, e em chefes/membros de bando com `plano_falhou` mas sem estarem sozinhos ou cercados, o `sempre` decide abaixo de 35 % e a assinatura é jogada sem aviso na rodada anterior. Medi com script ad hoc (`on`, 30 % de vida): **21 criaturas** do bestiário têm uma rodada em que `plan(r).assinatura` existe e `prenuncio(r-1)` é `None`, por exemplo `enemy_soldado_legiao_ferro` com `inf_lider_matilha_uivo_de_reuniao` na rodada 3. Antes do delta, os dois lados eram simétricos. | Aplicar a mesma condição nos dois lados: em `plan()`, `carta = None` quando `_badly_wounded(actor)`, e o slot do padrão segue. A alternativa é derivar a trava do gatilho que de fato decide. Teste de regressão: para todo o bestiário em `on`, a 30 % e a 60 %, `plan(r)["assinatura"]` implica `prenuncio(r-1)`. |
| P2-7 | P2 | `services/enemy_decks.py:363` | Resta uma janela inerente: o Presságio é decidido no fim da rodada e o chefe pode cair abaixo de 35 % antes de agir na seguinte, aí foge e não cumpre o anunciado. Com 60/40 isso é raro. | Follow-up opcional: registrar telemetria `pressagio_nao_cumprido` ou, nas fases, deixar o chefe ignorar `plano_falhou` na rodada da assinatura. |

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_enemy_decks.py tests/test_boss_phases.py tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_spec283_enemy_support_cards.py tests/test_card_effects_grammar.py tests/test_card_lint.py → 149 passed
bash scripts/dev/py.sh scripts/check_handoff_names.py → exit 0
script ad hoc (on, 30 % vida, bestiário inteiro): plan com assinatura e prenuncio(r-1) None → 21 criaturas
```
