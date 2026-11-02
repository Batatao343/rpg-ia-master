# SPEC-368 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus / papel Sol · **Data:** 2026-11-02 · **Commit revisado:** `10bd0212`

## Escopo

`git diff main...spec-368` (7 commits, `70e626e0..10bd0212`, 32 arquivos) contra
`specs/SPEC-368-cartas-fechamento-epico.md`: rollback R1–R3 (`card_piles.sync_deck_mode`,
`api._cards_block`, `cards.set_prepared`, `persistence._raw_to_state`), conteúdo R4–R8 (4 baralhos de
facção, Dor Surda/`discard`, `essencia_de_cinza`, lint do Ressoar, escolha do `descartar` na UI),
métricas R9–R12 (`docs/spec368/metricas_epico.py`, JSON, evidência em 327/329/331/355), fixtures R13.
Fora: smoke real §6 (coordenador), suíte completa (coordenador).

Integridade de eval: nenhum arquivo em `evals/`, golden da 330, `web/e2e/contracts`,
`scripts/cards/sim.py`, `docs/spec3*/arena_*.py`, orçamento ou `config/flags.yaml` no diff.
`metricas_epico.py` só importa `sim.py` via `importlib` (sem escrever nele) e só escreve no `--out`.
Nenhuma flag nova; nenhum `with_structured_output` novo; 0 LLM por rodada (descarte é Python puro).

Conferido sem achado:
- **R1–R3:** `_cards_block` trabalha sobre cópia rasa e `deactivate_deck` só reatribui chaves da
  cópia → não muta o chamador (teste cobre). `set_prepared` muta o estado de propósito (é escrita).
  No load, a restauração só persiste se houver save posterior; idempotente (2ª chamada é no-op).
  Mesmo critério do nó de combate (`agents/combat.py:2181`, só `off`). O round-trip do adapter de
  eval `legacy_load` (`evals/core/adapters.py:917`) continua idempotente. Hosted passa por
  `services/game_serialization.py:28` → `_raw_to_state`, então também é coberto.
- **R6/R8a:** contrato aditivo (`action_kind="discard"`, `descartar` ≤ 4, campos `descartar_folego`
  /`descarta_escolha` só quando existem). `plan_plays` recusa antes de gastar (Carta não
  descartável, fora da mão, Fôlego próprio insuficiente; sem Pacto); `descartar_escolhidas` é
  transitório (`finally` remove; teste cobre). `pick_discards` só usa `prefer` com `escolha` e
  ignora ids fora da mão. UI: botão separado do card (`.deck-card` continua batendo no atalho de
  teclado), `aria-disabled` + motivo.
- **R8c (Fardo por evento do Abismo):** decisão sustentável. O glossário da 330 (l. 46) só diz que o
  Fardo entra "por efeito de inimigo/Abismo", e isso já existe: `card_status._insert_sussurro`
  (Carga alta) → `_rot_sussurro` (`services/card_status.py:134`) planta o Fardo base. Um gatilho novo
  mexeria no dano medido pela arena da 362 sem decisão do dono. Falta só registrar na própria 330 (P2-2).
- **R9/R10 reprodutíveis:** 2 sementes rodadas 2× → JSON idêntico (exceto `elapsed_s`); 0–19 rodado de
  novo → **idêntico ao `metricas-0-19.json` commitado** (1800 conflitos; 1,92 cartas/rodada; 87,7 %;
  p95 12; R10 +10,1 %). Método: p95 nearest-rank com timeout = 20; ≥ 3 escolhas = Cartas distintas
  pagáveis sem Pacto; uso = jogadas/aparições na mão (n ≥ 5). Correto para o que a spec pede.
- **R4 voz/tema:** as 24 Cartas batem com o bestiário (Costurado de Lentes, Couro Pegado, Aguadeiro de
  Bucho, Caçador Sem Calor; Leitor de Cativos, Cauda Emendada, Arqueiro de Tendão; Viúvo do Esporo,
  Surdo da Colmeia, Ressecado da Travessia; Carregador de Ganchos, Capturador de Groth) e com o Codex
  (`story_cotidiano_deserto_zhur.md:16` lentes de obsidiana/miragem; `npc_groth_algema_fria.md`
  "Algema-fria", inventário; `story_itens_selva_xylos.md` esporo/colmeia). Frases curtas, concretas,
  sem meta; `check_voice` limpo. Uma promessa de texto sem mecânica (P3-3).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `tests/fixtures/spec368_scenarios.py:84` (e `specs/SPEC-368-cartas-fechamento-epico.md:132`, `:195`) | As fixtures do R13 montam dicts de motor em memória (cena/atores/pilhas para `orch.run_round`) e checam no próprio motor; **nenhuma leva o jogo real (save/API/UI) à cena**. Não há writer de save nem seed via API. Itens 8–11 checam só pré-condições (arquivos existem, flag registrada, `vitalidade == 1`); o item 6 acha uma semente de espólio que não é controlável no jogo vivo. O §6 diz "usar as fixtures do R13 para chegar a cada cena" e o §9 diz "as fixtures do R13 levam a cada cena" — falso para o smoke real, que terá de chegar a cada cena jogando com LLM. | Escolher um: (a) `seed_save(item, game_id)` nas fixtures de combate (1–7, 12, 13) que monta um `GameState` com `combat.active` + `pilhas` e grava via `persistence.save_game_state`, com teste de round-trip save→load→`/game/state` mostrando a mão esperada (writer persistente exige round-trip); ou (b) corrigir R13/§6/§9 para "prova offline no motor + roteiro (`passos`)", deixando explícito que o smoke chega às cenas jogando. (a) é o que a spec prometeu. |
| P2-1 | P2 | `tests/test_spec368_content.py:20` | O teste do R5 fixa `len(faccoes) == 14`. O bestiário atual (SPEC-349, `c0778c98`, mesmo dia) tem **10 facções com criatura e sem baralho**: `tres_sindicatos_comercio` (3), `mercadores_curiosidades` (3), `clas_tecnologicos` (3), `druidas_ciclo_cinzento` (2), `casa_mares_dominio_lyss`, `ultimos_anoes_reino`, `goblins_mineiros`, `encapuzados_fornalha`, `cidades_estado_sobreviventes_vaelorn_solvhen`, `cultos_despertar_dispersos` (1 cada). Elas caem no pool da família (funciona), mas o critério da 332 "cada facção com ≥ 1 Carta exclusiva" não fecha para o bestiário real, e o teste não pega a deriva. | Derivar o conjunto do bestiário (`{_fold(faction)}` ⊆ `_pools()["faccoes"]`) com lista explícita de pendentes + follow-up nomeado (spec de baralhos das facções da 349), ou autorar os 10 baralhos. Ajustar o texto do R5/§9 para não afirmar "sem exceção". |
| P2-2 | P2 | `specs/SPEC-330-*.md:3` e `:215` | A 330 ainda lista como abertos os follow-ups D-13 (escolha do descartar na UI, `_bump`, Fardo por evento do Abismo). A resolução (a feito, b travado por lint, c decisão de não fazer com motivo) está só na 368 §9. Sem isso a 330 não fecha com evidência. | Registrar no §9/cabeçalho da 330 os três itens com arquivo:linha e o ponteiro para a 368 §9 (pode ser no fechamento do coordenador). |
| P3-1 | P3 | `web/src/combat/deck.ts:75`, `:99` | `discardReason` bloqueia o descarte se a fila já toma Pacto, mas `move` permite reordenar um descarte para depois de uma Carta que pede Pacto; o servidor então recusa a lista inteira (sem gasto, explicado). Correto, mas o jogador só descobre ao encerrar. | Revalidar a fila no `move` (ou bloquear mover descarte para depois de jogada com empréstimo). |
| P3-2 | P3 | `web/src/components/combat/Hand.tsx:31` | Mão só com Dor Surda (+ cartas bloqueadas) mostra "Nenhuma carta responde agora" mesmo com o botão Descartar disponível. | Considerar `discardReasons` em `allBlocked` ou ajustar a nota. |
| P3-3 | P3 | `data/cards/inimigos/faccao_bandos_nomades.json:41` | "Disparo de Tendão": a descrição promete "cada tiro é mais forte que o anterior", mas o efeito é `dano` 5 fixo. | Reescrever a descrição sem prometer escalada (ou usar Ressoar, se couber no orçamento). |
| P3-4 | P3 | `services/card_deck_round.py:107` | Se a 1ª (ou última) jogada da lista for `discard`, `pre_acao`/`pos_acao` presos a `i == 0`/`i == last` se perdem (o `continue` pula). Hoje a API não manda pré/pós na lista, então é latente. | Anexar pré/pós à 1ª/última jogada não-descarte. |
| P3-5 | P3 | `docs/spec368/metricas_epico.py:11`, `:162`, `:165` | (a) Docstring diz "rodadas em que o jogador agiu", o código conta todas as rodadas e as Cartas *planejadas* (não as resolvidas). (b) No R10 `forecast_round` consome o mesmo `rng`, então os braços não são pareados por semente (comparação de médias sobre 1800, não pareada) e o braço `on` também muda o comportamento inimigo (intenções congeladas), não só a visibilidade. O número é reprodutível e o texto da 329 §8 já cita a 2ª parte. | Corrigir a docstring; anotar na 329 §8 que o Δ é não pareado (rng separado para o Presságio daria pareamento, num follow-up). |
| P3-6 | P3 | `tests/test_spec368_replace.py:84` | R11 é replay sintético (30 limpas, 3 com deriva por construção), não taxa real de `replace`; não há harness de latência para stream (registrado na 368 §9). | No smoke §6, registrar a taxa real de `replace` da rota de combate (telemetria do staging) na 355 §10. |

## Correções aplicadas

Nenhuma ainda (revisão inicial).

## Pendências

- P1-1 e P2-1 bloqueiam o `APPROVED` (P1-1 porque o §6 depende dele; P2-1 porque o R5 afirma
  "sem exceção" sobre um catálogo que já derivou).
- P2-2 pode ser feito pelo coordenador no fechamento da 330.
- P3: follow-ups do executor; P3-5/P3-6 viram nota nas specs 329/355.
- Metas 327/329/331 não atingidas estão registradas com número e follow-up (D-368-1), sem mudança de critério: ok.

## Comandos rodados

```text
pytest -n 2 tests/test_spec368_{content,discard,metricas,replace,rollback,scenarios}.py → 40 passed
pytest -n 2 test_card_piles, test_card_lint, test_enemy_decks, test_card_effects_{piles,grammar,review_spec330}, test_cards_prepare_api, test_deck_migration, test_spec35{3},36{3,4}_golden_guard, test_spec363_{hand_targets,rewards_shop} → 281 passed, 1 skipped
node --test web/tests/deck-368-discard.test.mjs → 3 pass
py.sh docs/spec368/metricas_epico.py --seeds 0-1 (2×) → JSON idêntico; 180 conflitos, 1,938 cartas/rodada, p95 9, R10 +12,8 %
py.sh docs/spec368/metricas_epico.py (0-19) → idêntico a docs/spec368/metricas-0-19.json (exceto elapsed_s)
git diff main...HEAD --name-only | grep golden|evals/|e2e/contracts|sim.py|arena_|flags → vazio
```
