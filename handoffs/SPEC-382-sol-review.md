# SPEC-382 — revisão sol (review, Etapa 3)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / papel Sol (`spec-reviewer`) · **Data:** 2026-11-04 · **Commit revisado:** `ae0d6c6a`

## Escopo

Branch `spec-382`, intervalo `485e506d..ae0d6c6a` (79534206, 045f1352, 6e9479ac, c7ef65b3, 736926c2,
77bdc4e9, ae0d6c6a). Arquivos: `services/conflict_orchestrator.py`, `tests/size_budget.json`, registro
de execução da Etapa 3 na spec. O golden `485e506d` (oráculo, de outro agente) **não foi tocado** pelo
executor: nenhum `tests/spec382_*`/`test_spec382_*` aparece no diff. Etapas 1/2/4 ficaram fora (já
revisadas).

Comparei o `_run_round` antigo (`git show 485e506d:services/conflict_orchestrator.py`, l.2563-3046) com
os helpers novos (l.2563-3283), bloco a bloco:

- **Ordem dos efeitos:** idêntica. Recusa → início da cena → Presságio (`ei.mode`, `forecast_round`)
  → `_RoundIntents` → declaração do jogador/reset/contexto `fx`/`inicio_rodada` → mecânica de classe
  → iniciativa/seq → laço → fim de cena/Última Ação/terminais/Entropia/Abismo → `fim_rodada`/fases/
  promessas/desfecho. Nenhuma instrução trocou de lado de outra.
- **Aliasing:** `out`, `frozen`, `intent_cursor`, `taunt_spend`, `acted`, `denied` são os mesmos
  objetos em todos os pontos de uso; `ctx.pressagios = intents.frozen` e
  `ctx.intent_cursor = intents.intent_cursor` mantêm a identidade que o Interromper (SPEC-330) usa.
  `actors_by_id.get(actor_id)` é refeito em `_round_extra_action`/`_round_resolve_actor`, mas nada
  entre a leitura do laço e a do helper rebinda chave do dict (`_snapshot_conditions`,
  `_tick_conditions_v4`, `_check_terminal` só mutam o ator); sem `actors_by_id[...] =` no módulo.
- **`acted` ligado:** `intents.acted = acted` antes do `for`, como o `acted` local que a closure
  `_tf_acted` lia; `tf_acted()` só é chamado no laço e em `_round_end` (depois do laço). Sem diferença.
- **Retornos antecipados:** o único (`return out` da recusa) virou `if _round_refusal(...): return out`;
  os `continue` do laço viraram `return`/`continue` equivalentes em `_round_extra_action` e no laço.
- **`frustrate_pending`:** reproduz exatamente os 3 blocos `intent_mode == "on" and frozen is not None
  → next_intent → if not None → frustrate(motivo)` (incapaz ×2, atordoado). O ramo da ação extra, que
  tem condição diferente (`actor_id not in denied` + `interrompido_por`), ficou inline — correto.
- **Imports locais (R8):** continuam locais; os helpers reimportam módulos já carregados antes no
  fluxo (`card_deck_round`, `scene_cards`, `enemy_intent`, `cards`) — sem efeito colateral novo.
- **Exceções:** `_run_round` não tinha `try/except`; nenhum novo foi criado.
- **Lambda em `declare_extra`:** `enemy_decks.declare_extra` só chama `declare(actor_id, actor)`; o
  espião do golden registra `type(v).__name__` (`tests/spec382_phase_spy.py:92`), que era `function`
  para a closure antiga e continua `function` com a lambda (seria `method` com o método ligado).
  Desvio justificado e declarado.
- **Tamanhos (ast):** `_run_round` 484 → 82 (R1 ≤ 150). Maior helper `_round_actor_loop` 60; maior
  método `_RoundIntents.taunt_same_round` 54 (era a closure de mesmo tamanho). Nada > 60.

### Desvio (1): arquivo 3.046 → 3.283 linhas e `size_budget.json` editado à mão

A regra geral do AGENTS.md ("arquivo > 1.000 linhas não cresce; código novo vai em módulo próprio")
colide com o R2 da spec aprovada ("helpers no mesmo módulo; nenhum `.py` novo de produto"). A spec é
o contrato mais específico, e o R2 existe por um motivo de equivalência (R7: testes patcham nomes do
módulo; helpers chamam os globais pelo módulo). A Etapa 4 resolveu do mesmo jeito: `agents/combat.py`
3731 → 3957 e `agents/storyteller.py` 2725 → 3020, baseline atualizada em commit próprio com o motivo
(registro da spec, l.586), revisão Sol anterior APPROVED_WITH_FOLLOWUPS. A Etapa 3 segue o precedente:
commit próprio (`ae0d6c6a`), só a linha do arquivo e a remoção de `_run_round: 484` (agora 82 < 100,
entrada obsoleta). Aceito; o crescimento vira follow-up (P2-1), não bloqueio.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/conflict_orchestrator.py` (3.283 l.); `tests/size_budget.json:28` | God-file cresceu +237 linhas por força do R2 (mesmo padrão das Etapas 2/4). Aceito nesta spec, mas o orquestrador fica 3× acima do teto. | Follow-up (spec própria, junto com o de `combat.py`/`storyteller.py`): mover `_RoundIntents` + `_round_*` para `services/conflict_round.py`, com shims dos nomes patchados (R7). Não fazer nesta spec. |
| P3-1 | P3 | `services/conflict_orchestrator.py:2978`, `:3018`, `:3116`, `:3169` | Aliases redundantes (`_cond_before = cond_before`; `_scene_ctx, _scene_rnd = scene_ctx, scene_rnd`) só para manter o texto colado. Inócuo. | Opcional: renomear os parâmetros para o nome usado no corpo e apagar o alias. |
| P3-2 | P3 | `services/conflict_orchestrator.py:2579-2581`, `:2669-2671` | Artefato do `ruff format` ao mover comentário de fim de linha (`dict[\n str, list[dict]\n] = {}  # …`; `)  # SPEC-387`). Cosmético. | Comentário em linha própria acima da instrução. |
| P3-3 | P3 | `services/conflict_orchestrator.py:2964-2975`, `:3000-3013`, `:3098-3112` | `_round_extra_action`/`_round_resolve_actor`/`_round_end` recebem 10–13 parâmetros posicionais; uma troca futura de ordem passa no tipo (`dict`/`dict`). O golden pega hoje (mutação 3 abaixo), mas a assinatura é frágil. | Follow-up opcional: tornar os parâmetros keyword-only (`*,`) ou ampliar o contexto de rodada. |
| P3-4 | P3 | `specs/SPEC-382-refactor-nos-grandes-agentes.md:3` | Cabeçalho ainda diz "Etapa 3 pendente por W1 da `spec-373`"; o registro de execução no fim está correto. | Coordenador atualiza o status no pouso (Etapa 5 da Etapa 3: W2 + smoke). |

Sem P0/P1. Nenhuma mudança de comportamento encontrada; nenhum `except` novo; nenhum valor de LLM,
writer persistente, segredo em log ou arquivo de `evals/` no diff; `dup_helpers` limpo.

## Correções aplicadas

Nenhuma (revisão sem P0/P1).

## Pendências

- P2-1 → spec de follow-up de extração de módulos (`conflict_orchestrator`, `combat`, `storyteller`), dono: coordenador.
- P3-1..P3-3 → opcionais, podem entrar no mesmo follow-up.
- P3-4 → coordenador, no pouso.
- Etapa 5 para a Etapa 3 (W2 A/B completo + smoke) continua com o coordenador; não rodei a suíte completa.

## Comandos rodados

```text
git diff 485e506d..HEAD --stat → 3 arquivos (orquestrador, spec, size_budget.json); golden intocado
bash scripts/dev/pt.sh tests/test_spec382_node_golden.py tests/test_card_effects_grammar.py tests/test_spec339_duracao_condicoes.py tests/test_spec346_mech_log.py tests/test_enemy_intent_node.py tests/test_spec355_*.py tests/test_spec295_chefe_no_topo.py tests/test_spec353_golden_guard.py tests/test_spec363_golden_guard.py tests/test_spec364_golden_guard.py tests/test_size_budget.py -n 2 → rc=0 (~420 passed, poucos skips)
ast: _run_round 82; maior helper _round_actor_loop 60; maior método taunt_same_round 54
mutação tf_acted → None (simula `acted` não ligado) → golden FALHA (round_boss_extra_intent)  [morta]
mutação frustrate_pending com motivo fixo "incapaz" (atordoado perdido) → golden FALHA (round_intent_on)  [morta]
mutação _round_extra_action com denied vazio → golden FALHA (round_interromper_stun)  [morta]
  (mutações por plugin pytest em scratchpad via monkeypatch; worktree não editado)
dup_helpers.py --diff 485e506d...HEAD → nenhuma função nova com nome repetido
ruff check services/conflict_orchestrator.py → All checks passed
ram.sh → sem pytest/python órfão
```
