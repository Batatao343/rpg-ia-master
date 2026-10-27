# SPEC-332 — revisão sol (review, Entrega 2)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `7137cc44`

## Escopo

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

## Achados

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

## Correções aplicadas

Nenhuma (revisão só leitura; o executor corrige na `spec-332`).

## Pendências

- Corrigir P1-1..P1-3 e pedir re-revisão Sol. Os P2 podem ir no mesmo commit ou virar follow-up na 336 (conteúdo) e na 334 (front).
- Continuam de antes: o alvo da arena é decisão do dono, e o front de `prenuncio`/`costuma` sai na SPEC-334 antes de `on`.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_enemy_decks.py tests/test_boss_phases.py tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_spec283_enemy_support_cards.py tests/test_card_effects_grammar.py tests/test_card_lint.py tests/test_card_effects_review_spec330.py → 162 passed
script ad hoc (scratchpad): idempotência sem _deck332, 124 criaturas x 6 seeds → 0 divergências; determinismo build_enemy_deck → True
script ad hoc: uso > 15 em 50 seeds → 17 seeds (lote 2) x 4 seeds (sem curadoria)
script ad hoc: colisão de id/nome contra `git show main:data/cards/**` → 0 ids, 2 nomes
arena_familias.py 2 --levels 3 --per-family 2 --only lider_matilha,guardiao (2x) → JSON idêntico
smoke ad hoc: Valerius solo a 25 % no `on` → fase 2 + presságio cumprido, depois `escapa do conflito`; Decreto não usado
```
