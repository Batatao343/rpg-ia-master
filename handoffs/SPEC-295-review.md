# SPEC-295 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (Sol/Astra, subagente independente `spec-reviewer`) · **Data:** 2026-10-19 · **Commit revisado:** `0ba8f29`

## Escopo

Branch `spec-295`, `36cda92..0ba8f29` (2 commits): `services/conflict_orchestrator.py`
(`extra_actions`, `run_round`), `agents/bestiary.py` (`DEFAULT_ACTIONS_PER_ROUND`,
`CHEFE_PROTECAO_POR_NIVEL_ENCONTRO`, `apply_encounter_survival`,
`materialize_enemy_concept`), `combat_mechanics.passive_modifiers`,
`scripts/migrate_bestiary_v4.py`, `data/bestiary.json`,
`tests/test_spec295_chefe_no_topo.py`, spec e `docs/spec295/README.md`.
Não revisado: o playtest R10 (números aceitos como estão na §8) e a suíte completa
(fica para o `/spec-land`).

**Conclusões por foco:**

- **K2 em `run_round`:** está correto. As ações extras entram depois de todo o
  `seq` e só para ids de `sides["enemy"]` que estavam aptos quando o `seq` foi
  montado. O stun observado na 1ª ação vai para `denied` e nega a 2ª. Tick de
  condição e `_expire_stat_conditions` rodam só na 1ª ação. A 2ª passa pelo mesmo
  `_can_act` (vivo, não `estado_terminal`, não `last_stand_pending`), então chefe
  morto ou terminal não age. `_resolve_actor_turn` reabre a janela de Reação e
  `resolve_turn` reseta o orçamento do turno. `_stalemate_guard`,
  `_resolve_last_stands` e `resolve_terminals` seguem uma vez por rodada, fora do
  loop. A ordem é determinística (ordem de `sides`) e tudo usa o `rng` da rodada.
  Não há LLM nem `random` global.
- **Proteção natural:** o desvio (knob fora de K1–K3) está justificado na §4/§8.
  A Vitalidade dos Níveis 1–2 está travada pela SPEC-287 e o valor 12 pela
  SPEC-290; o §27.3 das regras prevê "sobrevivência específica". O valor sai só de
  `encounter_level` (`compute_encounter_level` não recebe a party), então a R5 é
  respeitada. A Proteção só é gravada em Chefe/Nomeado e o herói ignora o campo.
  O valor é atribuído, não somado, e por isso é idempotente. Com a sobrevivência
  da SPEC-287/290 não há conflito: Vitalidade e Proteção são campos separados.
  R9: uma ficha sem os campos dá 1 ação e Proteção 0. O default só entra quando a
  ficha passa de novo por `apply_encounter_survival`, e combate salvo em
  andamento não passa.
- **Gerador:** regenerei o arquivo inteiro em memória (`NEW_CREATURES` +
  `migrate_creature` sobre `data/bestiary.json`), com 0 entradas diferentes.
  Portanto o arquivo é exatamente a saída do gerador, e a regeneração é
  idempotente. O campo existe só em Chefe/Nomeado (há teste).
- **C3 confirmado:** arena com 3 seeds, níveis 1/5/8, dois bots, comparando um
  `main` 36cda92 limpo (via `git archive`) com a branch. As 18 células
  Lacaio/Padrão/Elite têm o dicionário inteiro idêntico; só "chefe" muda.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | agents/bestiary.py:260 | `CHEFE_PROTECAO_POR_NIVEL_ENCONTRO = {1: 2, 3: 1}` não é monotônica (Nível 1 = 2, 2 = 0, 3 = 1, 4–10 = 0). Foi ajustada às 3 células que a arena deixava abaixo da barra, pelo `DANGER_BY_LEVEL` da arena (L1–2 → Nível 1, L5–6 → Nível 3). É uma curva de ajuste ao instrumento, não uma regra legível: um Chefe de Nível 3 tem mais Proteção que um de Nível 4. Também é um knob fora da R1 que o dono não aprovou explicitamente (a justificativa está registrada). | Aceitável para pousar, porque C1/C2 fecham e o desvio está documentado. Follow-up: o dono ratifica o desvio. Revisitar a curva junto do tuning de classe (SPEC-049) ou de uma mudança no mapeamento da arena, preferindo uma forma monotônica ou uma regra explicável. Se mudar, registrar na §8. |
| P2-2 | P2 | tests/test_spec295_chefe_no_topo.py (ausente) | Nenhum teste prova que um Chefe derrubado para `estado_terminal`/`last_stand_pending`/morto entre a 1ª e a 2ª ação não age de novo. Isso estava no foco da spec ("respeitando `_can_act`") e o código cobre (conflict_orchestrator.py:1992), mas sem teste uma regressão passa calada. | Adicionar `test_boss_terminal_after_first_action_skips_extra`: setar `last_stand_pending=True` no Chefe via um ataque do herói que agiu antes, ou por monkeypatch de `_resolve_actor_turn`, e assertar `resolved_turns.count("boss") == 1`. Atenção: Vitalidade 0 sozinha não é terminal no v4 (o excedente vira Ferimento). |
| P3-1 | P3 | services/conflict_orchestrator.py:1989-1993 | Um stun aplicado no meio da rodada (o herói age entre a 1ª e a 2ª ação do Chefe) não nega a 2ª ação; ele vale para a rodada seguinte. O comportamento é intencional e comentado, mas é contraintuitivo para o jogador ("atordoei e ele bateu de novo"). | Registrar na §4 da spec ou no texto da Carta de controle. Se o dono preferir, checar `cm.has_control(actor, "stun")` também na ação extra. |
| P3-2 | P3 | services/conflict_orchestrator.py:1919 | O contador `turno` das Cartas de inimigo só é zerado no início da rodada, então a 2ª ação compartilha o limite por turno da 1ª. Uma Carta "1/turno" não repete na 2ª ação. É coerente com a semântica "uma rodada", mas não está documentado. | Uma linha na §4 da spec. |
| P3-3 | P3 | agents/bestiary.py:279 | Com `vitalidade_por_nivel_encontro` inválido, `apply_encounter_survival` sai cedo e o Chefe fica sem `acoes_por_rodada` default e sem Proteção. | Mover o bloco SPEC-295 para antes do early-return, ou tratar a falha só no cálculo de Vitalidade. Ficha oficial não tem esse caso, só overlay ou LLM malformado. |
| P3-4 | P3 | docs/spec295/README.md (C2) | A folga do teto C2 é estreita: na minha amostra de 3 seeds, `cartas` L1 deu Chefe − Elite = +20,2 pp (0,779 − 0,577), acima do teto. Com 10 seeds dá +16,4 pp, e o instrumento oficial é o de 10. A letalidade absoluta do Chefe chega a 0,86–0,89 no `basico` L5–8. As mortes em ≤ 2 rodadas no `cartas` L1 vão de 150 para 228 em 650 lutas. | Sem ação agora, porque C2 vale no instrumento oficial. Monitorar no cenário dirigido de Chefe (follow-up da §8) antes do beta. |
| P3-5 | P3 | docs/spec285/arena_lethality.py | Rodada a partir do checkout principal (OneDrive), a arena carrega o overlay runtime `bestiary_template` (`load_bestiary` = curadoria ∪ overlay). Isso põe 2 criaturas a mais nos pools de Lacaio/Padrão (705 contra 675 lutas) e produz uma falsa violação de C3. Medições de "idêntico ao `main`" exigem árvore limpa. | Documentar no docstring da arena ou isolar o store (ex.: forçar um store vazio/tmp na arena). |

Não encontrei P0/P1. Também não encontrei: structured output novo (não há LLM
novo), valor de LLM sem validação (`acoes_por_rodada`/`protecao_natural` passam
por `int()` com `try`, clamp `max(0, …)` e fallback), writer persistente novo (só
o gerador, round-trip confirmado), segredo em log nem mudança em `evals/`.

## Correções aplicadas

Nenhuma até esta revisão (o revisor não edita código).

## Pendências

- P2-1: ratificação do desvio da Proteção natural pelo dono e revisão da curva na SPEC-049 (coordenador).
- P2-2: teste de "terminal entre ações". Pode entrar antes do pouso, em uma linha, ou como follow-up imediato (executor).
- P3-1 a P3-5: registrar na spec/README ou em follow-up de tooling da arena (coordenador decide).
- Já registrado na §8: cenário dirigido de Chefe no playtest; `behavior.phases` segue inerte.

## Comandos rodados

```text
git diff 36cda92..spec-295 --stat → 8 arquivos, +702/−53
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec295_chefe_no_topo.py tests/test_spec287_encounter_scale.py tests/test_letalidade_early.py → 82 passed
probe (scratchpad): regeneração do bestiário inteiro em memória pelo gerador → 0 entradas diferentes de data/bestiary.json
arena_lethality.py 3 --levels 1,5,8 (branch) vs (main 36cda92 limpo via git archive, mesmo venv) → 18/18 células Lacaio/Padrão/Elite idênticas; só "chefe" muda
arena no checkout principal (OneDrive) → falsas diferenças em Lacaio/Padrão por overlay runtime do bestiário (P3-5)
```
