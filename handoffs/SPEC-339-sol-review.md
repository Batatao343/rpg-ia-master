# SPEC-339 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `5c62e129`

## Escopo

Branch `spec-339`, `git diff main...spec-339` (commits `a6cf8350..5c62e129`):
`services/conflict_orchestrator.py` (marcador `_pula_tick`, `_mark_fresh_conditions`, R8b),
`combat_mechanics.py` (`_renovada` no refresh), `scripts/cards/sim.py` (desempate por hash),
`services/card_lint.py` + testes (remoção do lint provisório), `evals/protected-paths.txt` (D7),
`tests/test_spec339_duracao_condicoes.py`, `docs/spec339/*`. Fora: smoke de API (§6.2–6.4, não
rodado pelo executor), suíte completa (do coordenador).

O que está correto e foi conferido:

- Regra R1 nas duas ordens com presságio `off`: confirmada por teste e por sonda própria
  (`bas_dev_voto` real, aliado, 4 rodadas): Provocação d=1 vale exatamente 1 turno do inimigo
  em `heroes` e em `enemy`.
- R2: o `stun` nunca recebe marcador (fora de `_LATE_READ_CONTROLS`). Continua negando 1 turno.
- R3: com `dot > 0` o marcador é ignorado no tick, e `_mark_fresh_conditions` nem marca controle com dot.
- R5: sem marcador, o tick fica igual ao anterior. A view `api._combat_block._conds` é whitelist (`name/dot/duration`), então nem
  `_pula_tick` nem `_renovada` vazam. O teste cobre.
- Sem empilhamento: `if not c.get(_SKIP_KEY)` impede marcar duas vezes. Cada marca vale 1 pulo, consumido por `pop`.
- R10/D7: `tests/fixtures/` sem diff contra a `main` (golden byte-idêntico). A proteção está em commit
  próprio (`5c62e129`), e `test_eval_governance`/`test_ci_eval_gates` passam.
- R13: lint provisório e lista de pendentes removidos, com teste de que uma Carta de onda com `taunt`/`marca` d=1 passa.
- `sim.full_deck`: o hash sha256 não tem sal, então o resultado é determinístico entre processos. A semântica da arena
  (tier desc, cópias por patamar) é preservada; só muda o desempate dentro do tier. Os dois braços
  antes/depois usam o mesmo baralho. A coluna 335 está corretamente marcada como não comparável.
- Desvio R8b (buff de reação em si mesmo fora) é aceitável e está documentado em §5.1.
- Sem structured output novo, sem LLM, sem segredo em log, sem writer persistente novo.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/conflict_orchestrator.py:259-268` | O R8b para "Proteção/AC dados por aliado" (D2 aprovado) não funciona no caso real. `same_side` exige que portador e ator estejam na **mesma lista** de `sides`, mas jogador (`hero`) e companheiro (`ally`) ficam em listas diferentes. Sonda: companheiro dá `protection +2` ao jogador no turno do companheiro, e `_mark_fresh_conditions(...) == 0`. Na ordem companheiro → jogador → inimigo, o buff expira no fim do turno do jogador, antes de o inimigo atacar. É o bug original, intacto para buff de aliado. O resto do módulo trata `hero ∪ ally` como um time só (`:350`, `:396`). | Calcular `team = set(sides.get("hero", [])) \| set(sides.get("ally", []))` e usar `same_side = aid in team and current_actor_id in team`. Acrescentar teste em `run_round` com aliado dando Proteção ao jogador, na ordem aliado-primeiro, que prove que o buff está ativo quando o inimigo ataca. |
| P1-2 | P1 (pode virar follow-up: só com `RPG_ENEMY_INTENT=on`, hoje `off` em todos os ambientes) | `services/conflict_orchestrator.py:2296-2303` + `:2280-2286`; teste `tests/test_spec339_duracao_condicoes.py:535-551` | Com o presságio `on`, o `taunt` é lido no **congelamento**, antes do tick. Na ordem `enemy` (inimigo antes), a Provocação d=1 aplicada na rodada 1 ainda está presente no congelamento da rodada 2 (o pulo é consumido ali) **e** no da rodada 3. São 2 declarações afetadas para d=1, contra 1 na ordem `heroes`. Sonda: `on/enemy`, rodada 3 com `Voto Sussurrado` ainda ativo no início e `e → player`. Isso viola "d turnos próprios" e o R9. O teste do R9 é parametrizado só com `hero_first`. | Antes de ligar o presságio: decidir a regra no modo `on`. Opções: (a) o congelamento consome a leitura (marcar `taunt` como "já lido" no forecast e descontar no tick seguinte, mesmo com `_pula_tick`); ou (b) no modo `on`, não marcar `taunt` quando o aplicador age depois do portador na rodada. Cobrir as duas ordens no teste do R9 via `run_round` (não via `forecast_round` isolado). |
| P2-1 | P2 | `combat_mechanics.py:524-528` | O refresh mais fraco infla a duração. Com `taunt` d=3 ativo, reaplicar d=1 dá `duration = max(3,1) = 3` **e** `_pula_tick`, ou seja, 1 turno a mais do que a condição já tinha (confirmado por sonda). | Só gravar `_renovada` quando `cond.duration >= c.duration` antes do `max` (o refresh efetivamente reinicia a contagem). |
| P2-2 | P2 | `combat_mechanics.py:526-528`; chamadores fora de `_run_round`: `world_utils.py:1647` (armadilha), `inventory.py:341/363` | Fora de combate, um refresh deixa `_renovada` gravado no estado (e no save) até a próxima passada de `_mark_fresh_conditions`. Nela, a condição antiga é tratada como "nova" e pode ganhar `_pula_tick` (debuff defensivo ou controle de leitura tardia), ou seja, 1 turno extra na 1ª rodada do próximo combate. | No início de `_run_round`, limpar `_renovada` de todos os atores (pop sem marcar), ou gravar `_renovada` só quando houver contexto de rodada ativo. |
| P2-3 | P2 | `tests/test_spec339_duracao_condicoes.py:119`, `:550` | `logs[:1]` só checa a 1ª linha do log (asserção fraca). No R9, `forecast_round` faz `_fork_rng(rng)`, então o `_Rng0` é descartado e o teste passa pela semente 3, não pela chance forçada (com `_Rng0(2)` o alvo congelado é `ally`). | Asserção sobre todas as linhas antes do 1º turno do portador. No R9, forçar a chance via monkeypatch de `_taunt_target`/chance, ou documentar que a semente foi escolhida. |
| P2-4 | P2 | `services/conflict_orchestrator.py:250-252` | O R4 diz que "autoaplicado no próprio turno não muda", mas um controle posto pelo próprio ator **sem** `source_actor_id` é marcado (tratado como reação). Hoje nenhuma Carta faz isso, e está documentado em §5.1. | Só registrar. Se aparecer Carta de controle em si mesmo, exigir `source_actor_id` no caminho de aplicação. |

## Correções aplicadas

Nenhuma ainda (revisão inicial).

## Pendências

- P1-1: corrigir nesta spec (executor), com teste.
- P1-2: aceitável como follow-up **bloqueante para ligar `RPG_ENEMY_INTENT=on`**, se o coordenador
  preferir não segurar o bugfix do caminho `off`. Nesse caso, registrar na spec (§5.1) e na 329/334.
- P2-1/P2-2: recomendados nesta spec (correções de poucas linhas).
- Bandeiras `dominante` novas (`cor1_alm_culpa_antiga`, `san_exp_espetaculo`) e Sangromante acima de 75 %:
  com o dono/336 (R16), como está no relatório.

## Comandos rodados

```text
git diff main...spec-339 --stat → 14 arquivos; tests/fixtures/ sem diff (golden byte-idêntico)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -p no:warnings -n 2 tests/test_spec339_duracao_condicoes.py tests/test_card_lint.py tests/test_card_sim.py tests/test_card_effects_grammar.py tests/test_conflito_orquestrador.py tests/test_mecanica_orfa.py tests/test_keywords_valoria.py tests/test_enemy_intent.py tests/test_eval_governance.py tests/test_ci_eval_gates.py tests/test_card_acervo_reparo.py → rc=0 (~440 passed)
sonda (scratchpad) run_round bas_dev_voto + aliado, intent off/on × heroes/enemy → off ok nas 2 ordens; on/enemy: taunt d=1 presente no congelamento das rodadas 2 e 3 (P1-2)
sonda _mark_fresh_conditions companheiro→jogador protection+2 → 0 marcadas (P1-1); refresh taunt d=1 sobre d=3 → marcada (P2-1)
```
