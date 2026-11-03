# SPEC-377 — revisão independente (independent-review)

> **Veredito:** `SAFE-WITH-CHANGES` (no template: `CHANGES_REQUIRED` no texto da spec antes de `approved`; nenhum item é UNSAFE)
> **Revisor:** spec-reviewer (Opus), não é o autor · **Data:** 2026-11-03 · **Commit revisado:** `b278f6af` (main)

## Escopo

Revisão crítica da spec `draft` `specs/SPEC-377-refactor-divergencias-combate-lei-faccao.md`, comparada com
o código da `main` e com a auditoria §6/§6.5. Não há código implementado. Usei sondas só de leitura
(scripts no scratchpad, `uv run --frozen python`, que importam e chamam funções sem gravar nada) e
pytest focado. Não editei spec, código, testes nem dados.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/storyteller.py:1693` × `:1708` | A spec diz (§3, item 1) que "só esse hook escreve `law_state`". **Falso.** No turno de emboscada por caçadores, `updates.update(_law_mod.mark_hunters(...))` (1693) grava `law_state` com `hunters_last_clock`. Logo depois, `updates.update({k: v for k, v in sim_updates.items() if k != "npcs"})` (1708) **sobrescreve** esse valor com o `law_state` podado que veio de `world_tick.state_patch` (1367), e esse não tem a marca. Basta uma jurisdição ser podada no mesmo dia em que os caçadores de outra atacam: `hunters_last_clock` some, e a próxima viagem pode trazer uma nova onda sem o espaçamento (`law.py:1083`). Hoje isso não acontece, porque nenhum hook gera `law_state`. | Acrescentar `agents/storyteller.py` aos arquivos do item 1 (a W1 dá vazio hoje). Corrigir a ordem: aplicar `mark_hunters` depois do merge de `sim_updates`, ou tirar `law_state` desse merge quando `mark_hunters` rodou (o `state` já está podado na 1368, então `mark_hunters` já parte do estado podado). Adicionar o teste `test_poda_e_cacadores_mesmo_turno_preserva_hunters_last_clock`. |
| P1-2 | P1 | `scripts/cards/sim.py:434`, `:454`, `:542` | A R8 diz que só o relatório e o lint usam a regra do lint, e que "a taxa por Postura não muda". Isso vale para a arena base, mas o protocolo **`lote-v2`** (SPEC-358) monta a Carta de referência com `"custo_folego": fx.custo_folego(card)` (434) e escolhe o X pela faixa `fx.budget_band` (454). Essa referência **luta** na arena e paga o custo explícito via `card_piles`. Unificar a regra muda `vitoria_ref`/`delta_pp`/`dominante` do avaliador congelado. A R24 trava o diff do arquivo, não o resultado. | Na R8 e na R24, declarar que o `lote-v2` das Cartas divergentes muda, e medir no relatório antes/depois. Pela regra de integridade (AGENTS §evals; SPEC-380 §7 diz que "a 377 já vai pedir eval authoring"), registrar que a saída do avaliador muda e marcar `EVAL_AUTHORING_REQUIRED: true` (ou justificar o `false` no cabeçalho, já que a SPEC-380 conta com o contrário). |
| P2-1 | P2 | spec R9 [H], R10 | **Hipótese refutada** pela medição. No modo bruto (1.505 Cartas em `data/cards/**`) e no modo catálogo (`cards._load_cards`, 1.505), há **só 2 divergências**, ambas do motivo (b): `cor_toque` (`corruptor.json`, dot livre: jogo 1, lint 0) e `toque_corrosivo` (`exemplos.json`, idem). Os motivos (a) e (c) dão zero. Nada se concentra em `arcanista`/`bestiario`/`tiers_5_plus`/`inimigos`. Nas duas Cartas, o lint (`check_budget`/`budget_error`) **não muda** (faixa (0,7) → (-2,9), score 2,4 e 4,2: ambas dentro nas duas regras). O modo (iii), Ruptura/evolução, não foi medido. | Reescrever a R9 com o número real. A D2 pode vir **pré-decidida em (a)** (regra do jogo), porque o jogo não muda, o lint não muda e a SPEC-328 R6 ("0 se livre e sem dano") apoia: dot é dano. O passo 3 (arena 40 min) sai do caminho normal. Fica só o modo (iii) na Etapa 0 e a medição do `lote-v2` das 2 Cartas (P1-2). |
| P2-2 | P2 | spec R6 → `npc_world.py:721-723` | A spec dá o guard do `npc_world.day_hook` como modelo de "o shadow nunca escreve `law_state`". Esse guard só olha `RPG_NPC_WORLD == off`. Ele **não** olha `RPG_WORLD_ENGINE`. E o `storyteller` mescla `state_patch` sem olhar o modo (1364-1368). Copiar o modelo ao pé da letra faria o hook da lei escrever no save com o motor em shadow. | Na R6, exigir explicitamente `world_engine.mode() == "on"` dentro do `law.day_hook`, e tirar a frase "o modelo é o guard do npc_world". |
| P2-3 | P2 | spec D1 / §7 | A D1 diz que a mudança só afeta o jogo "depois de suborno ou pena com heat zerado". Depois de pena/multa (`resolve_fine`, `serve_sentence`, `_prison_choice`) o `_clear_wanted(keep_heat=0)` **já** zera `known_at`/`signals_shown`/`hunters_last_clock` (`law.py:1140-1143`), então podar não muda nada ali. Com decaimento natural, `bounty > 0` mantém a entrada (`daily_tick` exige `bounty` 0), então a poda também não age. Na prática, o efeito existe **só** depois de suborno com `keep_heat > 0` (`law.py:1353-1357`). | Corrigir o texto da D1/R2 ("só após suborno"). Isso também diz ao dono que o alcance é pequeno. |
| P2-4 | P2 | spec §4 item 1 passo 4 | O playtest `--turns 10 --seed 0` dificilmente produz suborno seguido de dias de decaimento e de crime novo. Ele vai mostrar "sem diferença" sem ter exercitado o caminho. | Manter o playtest como guarda de regressão e declarar que ele não prova a correção. A prova é o teste de caracterização, mais o de P1-1. |
| P2-5 | P2 | spec R15 | O bug está confirmado no nível de `card_effects`, e é **maior** do que a spec descreve: (1) `alvo == "inimigos"` inclui o rendido; (2) Carta hostil sem alvo cai em `opp[:1]` e escolhe o rendido quando o id dele vem primeiro na ordenação (`card_effects.py:668-673`); (3) `_allies` de um inimigo inclui o rendido, então a cura ou o buff de baralho inimigo pode cair nele. O flag persiste entre rodadas (`agents/combat.py:2404`, manifesto), então o efeito não se limita à "mesma rodada". | A R15 e o teste de caracterização devem cobrir os 3 caminhos e "rodada seguinte". A correção pontual em `card_effects._alive` (incluir `surrendered`/status `rendido`) cobre os três. Medir a arena conforme o passo 4. |
| P2-6 | P2 | spec R16 | `ct._targetable` (`conflict_turn.py:310-320`) **aceita** alvo em `estado_terminal`, mas `card_effects._alive` o exclui. Ou seja, o ataque declarado em alvo terminal passa e a Carta de área não. A R16 ("não é alvo de efeito novo") precisa dessa nuance, senão o executor "unifica" errado. | Incluir na R16 e no teste `test_terminal_nao_e_alvo_de_carta` a linha `ct._targetable(terminal) is True` como foto do comportamento atual. |
| P3-1 | P3 | spec R7/§3 | Os números de linha estão velhos depois do pouso da 368. Hoje: `cards.custo_folego` = `cards.py:447`; `card_effects.custo_folego` = `card_effects.py:1596`; os chamadores de `card_piles` ficam em `525,537,588,738` (não `496,508,528,654`). | Atualizar. Outra diferença menor entre as duas versões: `int(dano_base)` não protegido no lint (levanta `ValueError`) e `tier` default 0 contra 1 (inócuo). |
| P3-2 | P3 | spec cabeçalho / D5 | A W1 de 03/11 (rodada agora): a `spec-368` **já pousou** (não há branch; `712f0228` na main). Os itens 2 e 3 não esperam mais por ela. A única interseção com os arquivos da spec é `world_utils.py` (`spec-370`), que o item 4 só lê. `agents/combat.py`, `enemy_*` = `spec-371` (fora do escopo, ok). | Atualizar "Depende de" e a D5. Rodar a W1 de novo no início de cada etapa. |

### Conferência por requisito

| Req. | Resultado | Evidência |
|---|---|---|
| R1 | OK | `daily_tick` sem chamador (`git grep`); hooks em `world_engine.py:735-738`; SPEC-299:7,291,517 |
| R2 (a)(b)(c) | **Confirmado** (com P2-3) | A sonda montou uma entrada pós-suborno com heat efetivo 0 e depois um homicídio entregue por patrulha no clock 200. **Sem poda:** `known_at` fica `{nova_arcadia:20,...}`, `signals_shown=[perguntaram_por_voce]`, nível `cacado`, `hunter_encounter` = **True no mesmo clock** e nenhum sinal novo. **Com `daily_tick`:** `known_at` = `{200,201,201}`, sinais `[]`, caçador False |
| R2 (d) | OK | `law.py:850`. Detalhe: com a poda, `last_loc` fica parado e o crime seguinte roda `recognition_check` no local atual. É o mesmo comportamento do 1º crime, coerente |
| R3/R4 | OK | O decaimento é monotônico, e `daily_tick` avalia no período 0 do dia, então a leitura posterior no mesmo dia também dá 0 |
| R5 | OK | `normalize_law`; sem `law_state`, `keep == {} == wanted` → `{}` |
| R6 | Ajustar (P2-2) | |
| Ordem `order=30` | Indiferente | `merged.state_patch.update` usa "último vence", e nenhum outro hook escreve `law_state`. O conflito real é **depois** do tick (P1-1) |
| Carry multi-dia | OK | `world_engine.py:508,514` usa `state={**state, **carry}` |
| R7 | OK nos 3 motivos; números velhos (P3-1) | |
| R8 | **Incompleto** (P1-2) | |
| R9/R10 | Hipótese refutada (P2-1) | 2 divergências, as duas (b) |
| R11 | OK | Os imports locais conferem; não há ciclo |
| R12 | OK | Lint: `int("x")` levanta; jogo: `try/except` |
| R13/R14 | OK | Os 5 predicados conferem; `_side_of` é privado em cada módulo |
| R15 | **Bug confirmado** (unidade), maior (P2-5) | A sonda deu `_targets_for(alvo=inimigos)` = `[a_orc(rendido), b_orc]`; fallback = `[a_orc]`; `_allies(b_orc)` inclui o rendido; `orch._alive`/`ct._targetable` = False |
| R16 | Intencional, com nuance (P2-6) | `conflict_orchestrator.py:177-181` (`_can_act`) |
| R18/R19 | **Confirmado: duas políticas de propósito** | SPEC-293 §1 (qualquer fação não conhecida → papel, não-onisciência da Fase 2); SPEC-314 R3 + D1 do dono ("fação pública desconhecida aparece no bloco? **Sim**, nome e região"); `faction_gate.py:295-303` |
| R21 (b)/(c) | Reverte decisão passada | (c) contradiz a SPEC-314 D1 (decisão do dono); (b) desfaz a SPEC-293 (aprovada). A D4 deve dizer isso com essas palavras |
| R24 | Viável como diff, insuficiente como garantia (P1-2) | |

**O que o jogador vê hoje (item 4):** no HUD, no manifesto, no desfecho, no log e no dossiê, o combatente
de fação **pública ou secreta** não conhecida aparece como papel ou "Combatente desconhecido". O NPC, o
contexto e os rumores citam fação **pública** pelo nome e escondem a **secreta** ("[facção
desconhecida]"). Isso é coerente com as duas specs.

**Choques:** SPEC-380 §7/D3 espera que a 377 peça eval authoring, e o cabeçalho diz `false` (P1-2).
SPEC-376 exclui `law.daily_tick` da poda e manda para a 377: ok. SPEC-378 começa depois da 377 (`_fold` de
`law`/`faction_*`): ok. SPEC-384: nenhum choque encontrado. SPEC-382 extrai partes do storyteller "no
mesmo arquivo": se a correção de P1-1 entrar antes, a 382 herda. Coordenar a ordem.

**Caracterização e smoke:** os testes propostos fotografam os dois lados nos itens 1, 3 e 4. Faltam o caso
de P1-1 e os 3 caminhos de P2-5. O smoke §6 basta para os itens 3 e 4. O passo "1 rodada com Carta de área
contra rendido" depende de o LLM produzir uma rendição, e isso não é garantido. Aceitar a prova offline e
declarar no hand-back se o smoke não produziu rendição.

## Correções aplicadas

Nenhuma. A revisão é de spec, e o autor aplica as mudanças.

## Pendências

Top 3 mudanças para a spec virar `approved`:

1. P1-1: `storyteller.py` entra no item 1, com o reordenamento do `mark_hunters` e um teste do turno
   "poda + caçadores".
2. P1-2 + P2-1: corrigir a R8/R24 (o `lote-v2` usa a regra do lint dentro da luta), rever o
   `EVAL_AUTHORING_REQUIRED` e reescrever a Etapa 0 do Fôlego com o número real (2 Cartas, motivo
   (b), lint inalterado). Recomendar a D2 = (a) sem arena.
3. P2-2/P2-5: a guarda `world_engine.mode()=="on"` explícita no hook, e a R15 ampliada (área, fallback
   `opp[:1]`, `_allies` inimigo, rodadas seguintes).

## Comandos rodados

```text
W1 (auditoria §6.2) sobre todas as branches com commits à frente → interseção só world_utils.py (spec-370); spec-368 já pousada
probe_law.py (RPG_LAW=on, sem gravar) → sem poda: caçador no mesmo clock, sem sinal novo; com poda: known_at novo, sem caçador
probe_folego.py / probe_folego_raw.py → 1505 Cartas, 470 explícitas, 2 divergentes (cor_toque, toque_corrosivo; motivo b)
probe_band.py → check_budget/budget_error iguais nas duas regras para as 2 Cartas
probe_alive.py → card_effects mira o rendido (área, fallback, aliados); orch/ct não
pytest -n 2 test_spec299_hunters/law_state/wanted_signals + test_card_piles + test_card_effects_grammar → 102 passed (rc=0)
```
