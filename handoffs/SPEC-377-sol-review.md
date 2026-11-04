# SPEC-377 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1 que impede o pouso; o resto é P2)
> **Revisor:** Opus / papel Sol · **Data:** 2026-11-03 · **Commit revisado:** `d43be8b9`

## Escopo

Branch `spec-377`, `main...HEAD` (5 commits: `d7b596f1`, `c85e176c`, `a75762d6`, `7f4e6c14`,
`d43be8b9`). Itens 1 (poda da lei), 3 ("vivo"/"lado" e R15) e 4 (facção, D4=a). O item 2
(Fôlego) fica de fora: é do dono (`lote-v2`). Arquivos: `services/law_day_hook.py` (novo),
`services/world_engine.py`, `agents/storyteller.py`, `services/card_effects.py`,
`services/conflict_turn.py`, `services/companion_orders.py`, `services/faction_display.py`,
`services/faction_gate.py`, `tests/test_law_prune.py`, `tests/test_card_alive.py`,
`tests/test_faction_visibility.py` e `docs/spec377/`.

Conferido contra o cabeçalho (D1=a, D3=a, D4=a) e a W3:
- **Item 1.** O hook está em `post`, ordem 30, depois de `rumors`. O guard
  `world_engine.mode()=="on"` fica dentro do hook (R6), e `law.mode()=="off"` e `state is None`
  devolvem o resultado vazio. Os quatro casos têm teste parametrizado. O `carry` leva o estado
  podado ao dia seguinte (`world_engine.py:514`). O `mark_hunters` agora roda depois do merge
  de `sim_updates`, e isso está certo: o `state` já foi reatribuído com o `state_patch` podado
  em `storyteller.py:1368`, e `get_law` → `normalize_law` monta um dict novo, então o patch não
  ressuscita a entrada podada. Por inspeção (não rodei a versão antiga): na ordem antiga, o `law_state` podado
  sobrescreve a marca e `hunters_last_clock` volta a `-1`, então
  `test_poda_e_cacadores_mesmo_turno_preserva_hunters_last_clock` falha. Round-trip: o
  `law_state` podado (`wanted == {}`) continua sendo um dict não vazio (tem `version`, `crimes`
  etc.), entra no save (`persistence.py:636`) e volta por `normalize_law`. O hook não cria
  writer novo: o dono continua sendo `law.py`.
- **Item 3.** Os 3 caminhos do R15 estão em `card_effects._opponents` e `_allies`: área, o
  fallback `opp[:1]` e a cura do baralho inimigo. Também está coberta a rodada seguinte, só com
  a flag. Por inspeção, os 4 testes do rendido falham sem a correção (o código antigo devolve `e1` na área, no `opp[:1]` e nos aliados de `e2`). Os outros consumidores de alvo
  de Carta já excluíam o rendido: a UI e a validação usam `combat_targeting` →
  `ct._targetable`, e o preview e as intenções também. Quanto ao status sem a flag
  (`rendido`/`morto`/`fugiu`), o runtime sempre grava a flag junto (`_mark_dead`, fuga,
  `surrendered=True` em `conflict_orchestrator.py:694,2750`), e o manifest deriva o status a
  partir da flag. O R16 (terminal) está fotografado e não mudou.
- **Item 4.** Só docstrings e a matriz de 6 facções. Nenhuma mudança de comportamento.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/test_spec363_golden_guard.py:23-25` (vs `services/conflict_turn.py:291-302`) | `test_engine_modules_untouched_by_spec363` roda `git diff --quiet main -- services/conflict_orchestrator.py services/conflict_turn.py`, ou seja, compara a árvore de trabalho com a ref local `main`. O teste não verifica a branch. O executor diz que ele "passa após o fast-forward", e isso é literalmente verdade: depois do ff, a `main` é igual a HEAD. Só que o `/spec-land` roda a suíte completa **no worktree, antes** do `wt.sh land` (passo 3, antes do passo 4 da skill). Nesse momento o teste falha (reproduzi: `1 failed`), e a suíte fica vermelha, o que bloqueia o pouso. Depois do pouso, o guard fica tautológico (compara a `main` com ela mesma) e trava qualquer spec futura que toque esses dois arquivos. Ele não protege nada de verdade: o golden da 330 tem guard próprio (`test_golden_files_have_no_diff_against_main` e `test_spec353_golden_guard`, ambos verdes) e está em `evals/protected-paths.txt`. A SPEC-377 é a primeira spec a tocar `conflict_turn.py` depois da 363. Os guards seguintes (355, 364, 367) já foram escritos limitados à própria branch. | Limitar `test_engine_modules_untouched_by_spec363` à branch `spec-363` (`pytest.skip` quando `git rev-parse --abbrev-ref HEAD != "spec-363"`), seguindo o padrão de `test_spec364_golden_guard.py` e `test_spec367_guards.py`. Fazer isso num commit próprio e declarado (`test(guard): scope SPEC-363 engine guard to its branch (SPEC-377)`), com uma linha no §9 da spec. Manter `test_golden_files_have_no_diff_against_main` sem limitação. **Não** desfazer o rename: o R14 pede `_turn_side` em `conflict_turn.py`, e a mudança nesse arquivo é só nome e docstring, sem efeito no motor. |
| P2-1 | P2 | `services/conflict_turn.py:292-294` | `_turn_side` ficou com duas strings seguidas. A nova virou a docstring, e a original (que explica o `None` sem `sides`) virou uma expressão morta. | Juntar as duas numa única docstring (`hero`/`ally` → `hero`; `None` sem `sides`). |
| P2-2 | P2 | `services/card_effects.py:296-298, 402, 412` e spec §3 (item 3, "correção do R15 em `card_effects._alive`") | A correção foi para `_opponents`/`_allies` (exclui só a flag `surrendered`), e não para `_alive` como a spec descreve. A escolha é melhor: mudar `_alive` alteraria `is_down` (`:308`, `:343`) e faria o rendido contar como caído. O desvio, porém, não foi registrado na spec. Além disso, o `d43be8b9` tirou as docstrings de `_alive`/`_card_side` e "compactou" o `_alive` para caber no `size_budget` (1826/1828), quando o item 3 pede justamente nomes e docstrings em `card_effects.py`. | Registrar o desvio no §3/§9 (onde fica e por que não em `_alive`). Recuperar a docstring de 1 linha de `_alive` compensando em outro ponto, ou aceitar e anotar. Follow-up de extração (o arquivo está a 2 linhas do teto). |
| P2-3 | P2 | `docs/spec377/` e spec §4/§5 | Faltam evidências declaradas. A Etapa 0 do item 3 (`alive_consumidores.md`) não foi publicada. A matriz do item 4 (`faccao_matriz.py`/`.md`, R20) existe só no teste. Não há "W1 revisada registrada por etapa" nem o "playtest curto sem violação `law.*` nova" (critério do item 1). A caracterização "hoje" do rendido (W3: `test_rendido_alvo_de_carta_hoje` no commit de renome, invertida no de correção) não foi commitada: os testes já entraram invertidos. Por inspeção, eles falham sem a correção. | Publicar o mapa de consumidores (o parágrafo "Item 3" deste handoff serve de rascunho) e registrar a W1. Rodar o playtest curto com `RPG_LAW=on RPG_WORLD_ENGINE=on` e anexar o resumo. Se a matriz ficar só no teste, anotar na spec. |
| P2-4 | P2 | `docs/spec377/arena-antes.json` = `arena-depois.json` (bytes iguais) | A arena não exercita o R15, porque o bot não se rende (o README diz isso). A evidência de "arena 45–85 %" vale como não-regressão, não como prova do R15. Médico está em 45,8 %, perto do piso. | Nada a corrigir. Só deixar explícito no critério de aceite que quem prova o R15 são os testes unitários. |

## Correções aplicadas

Nenhuma ainda. O executor deve aplicar o P1-1 (obrigatório para o pouso) e o P2-1/P2-2
(baratos).

## Pendências

- Item 2 (Fôlego): fica com o dono (publicar `lote-v2` via `/eval-publish`).
- Smoke real §6 (≤ 6 requests) dos itens 3 e 4: coordenador.
- `card_effects.py` está a 2 linhas do teto de tamanho: extrair numa spec de refatoração.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_law_prune.py tests/test_card_alive.py tests/test_faction_visibility.py tests/test_spec363_golden_guard.py → 1 failed (test_engine_modules_untouched_by_spec363), 34 passed
bash scripts/dev/pt.sh tests/test_law_prune.py tests/test_card_alive.py tests/test_faction_visibility.py → 33 passed
bash scripts/dev/pt.sh <20 arquivos: card_effects_*, scene_cards*, spec299_hunters/law_state, spec303_hook, spec293, spec314_faction_gate/no_leak, spec346_board_no_llm/mech_log, conflito_orquestrador/morte, spec325_orders, spec353_golden_guard, size_budget, handoff_names> → 397 passed
bash scripts/dev/py.sh docs/spec355/arena_spec355.py base --seeds 0:20 --classes "Devoto do Abismo" → 60,2 % (consagrado 65,8 / zeloso 56,7 / enlutado 61,9); seção idêntica a arena-depois.json
git diff main...HEAD -- services/conflict_turn.py → só renome _side_of→_turn_side e docstrings
```
