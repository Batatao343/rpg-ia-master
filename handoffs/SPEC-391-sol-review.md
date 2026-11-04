# SPEC-391 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (1 achado P2 bloqueante, correção pequena; o resto são P3/follow-ups)
> **Revisor:** Opus (papel Sol, `spec-reviewer`) · **Data:** 2026-11-04 · **Commit revisado:** `4ed2d074`

## Escopo

Branch `spec-391`, intervalo `55b85c2c..4ed2d074` (6 commits, 18 arquivos): `services/reinforcement_cards.py`
(novo), `services/enemy_decks.py`, `services/conflict_orchestrator.py`, `services/enemy_intent.py`,
`services/reinforcements.py`, `agents/combat.py` (1 import), `api_presenters.py`, `data/cards/inimigos/chamados.json`,
`observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`, `config/flags.yaml`, web (`types.ts`,
`conflictChips.ts`, `DeckCombat.tsx`, `conflict-chips.test.mjs`), `tests/test_reinforcement_cards.py`, a spec.
Comparado com R1–R20, §3, §7 e os blocos "Execução". Fora: gate §8 (coordenador), smoke §6, suíte completa.

O que confere:

- **Máquina de estados** (`telegraphed → called → fired | cancelled`): transições em `_progress`/`_fire`/`_cancel`
  corretas; 1×/conflito (`fired`/`cancelled` encerram; `telegraph` só com estado vazio). Despacho legado × Carta
  por `via == "carta"` (`advance`, `reinforcement_cards.py:217`), nunca por `warned_round`; o espelho
  `warned_round` só nasce em `called` (R10 + invariante `golden_reinforcement` intactos).
- **Save/load:** além dos testes (round-trip JSON), rodei um round-trip **real** por `persistence.save_game_state`
  → `load_game_state` em `telegraphed` e em `called`: o fluxo continua, chega 1 `_r1`, Carta 1× no baralho,
  sem promessa duplicada. Save do R16 (sem `via`) segue o legado; save sem o campo entra no fluxo novo.
- **Precedência R4/R5:** `declaration_plan` é equivalente ao guard antigo quando não há chamado pendente
  (mesmas condições `active`/`forced_attack`/`flee|surrender`/`trigger ∈ {None, sempre}`; `plan(..., scene)`
  sem promessa de chamado = `plan(...)`). Com chamado pendente, vale com qualquer gatilho; `taunt`/`silence`
  ainda bloqueiam (vira frustração, contra-jogo legítimo). `record_promise` não sobrescreve a vaga do chamado.
- **Flag `off`:** `_advance_reinforcements` sai antes de chamar o módulo; nas mudanças de `enemy_decks`/
  `enemy_intent` todo caminho novo depende de promessa `tipo: chamado` ou de `chegou_na_rodada`, que só o fluxo
  `on` grava. Byte-idêntico por construção; oráculo da Etapa 1 verde.
- **Determinismo:** sem `random` novo; `deck_seed` herdado antes de `ensure_combat_sheet` (apply_deck usa);
  0 LLM medido no teste.
- **Payload/web:** `payload_fields` mantém a regra de ouro (nada do template antes da chegada; teste de vazamento
  verde). `combat.round` do payload é a rodada recém-resolvida, então `arrivalNotes` acende na resposta da
  chegada (conferido por sonda). `tsc --noEmit` limpo, `eslint` limpo, 5/5 testes web.
- **Arena congelada:** `git diff d0298e51..HEAD -- docs/spec391/arena_reforco_cartas.py` vazio. `sim.py`,
  arenas 285/332/368, `_decks.json`, `lider_matilha.json` e `evals/` sem diff.
- **Size budget:** `agents/combat.py` 3.957 → 3.957; `conflict_orchestrator.py` 3.049 → 3.046;
  `api_presenters.py` líquido −4; `enemy_decks.py` 714 (< 1.000); módulo novo 259 l., funções ≤ 60 l.
  `dup_helpers`: só colisões de nome (`advance`, `public_view`, `_key`…), nenhum helper duplicado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/reinforcement_cards.py:114-121` (`_cancel`) e `:160-167` | Chamado **frustrado** deixa `inf_chamado_do_bando` sem uso em `leader["cartas"]`. Como o `kind` é `protecao` e a `frequencia` é `cena`, `_enemy_support_card` (`conflict_orchestrator.py:798-832`, `_ENEMY_DEFENSIVE_SUPPORT`) pode jogar a Carta depois, como proteção comum. Reproduzi assim: promessa já fechada, outras Cartas defensivas gastas, ação `support`/`protect` (e `attack` com padrão `reforco_proprio`/`defesa`) nas rodadas 3–6 → `card_id='inf_chamado_do_bando'`. Resultado: o registro mostra "Chamado do Bando +1 Proteção" e nenhum reforço chega. Isso contradiz o R8 ("não há segunda tentativa") e confunde a leitura do tabuleiro. Também dá uma proteção extra que não estava prevista nas lutas frustradas do gate. | Em `_cancel`, enquanto `stage == "telegraphed"` (a Carta ainda não foi jogada), tirar `CALL_CARD` de `leader["cartas"]`. É preciso passar o líder, ou buscá-lo por `actors_by_id` em `_progress`. O orquestrador não cresce. Teste: depois de `test_call_frustrated`, `CALL_CARD not in leader["cartas"]` e `enemy_declaration` com `support` nunca devolve a Carta. |
| P3-1 | P3 | `services/enemy_decks.py:476` (`record_promise`) + `services/reinforcement_cards.py:89-110` (`telegraph`) | O R4 diz que a assinatura substituída "nunca foi pública". Na prática, a promessa da assinatura para N+1 é gravada (e mostrada no `prenuncio`) no presságio da rodada N, calculado no fim de N−1. O `telegraph` do fim de N a sobrescreve sem linha de frustração. O comportamento segue o assert da spec, mas o jogador viu "prepara X" em N e, em N+1, vê o chamado sem explicação. | Registrar na spec (raciocínio do R4) e decidir com o dono se cabe uma linha "troca o golpe pelo chamado". Não bloqueia. |
| P3-2 | P3 | `docs/spec391/arena_reforco_cartas.py:159-183` (avaliador congelado; **não** é do executor) | O critério 3 do §8 (`cancelled / telegraphed ≥ 25 %`) é estruturalmente ~0 na célula do líder sozinho. Derrubar o líder encerra a luta (`out["ended"]` → `win`) antes de `advance_card_flow` rodar, então o contra-jogo bem-sucedido nunca vira `cancelled`. Bate com a observação do executor: 70 chamados, 47 chegadas, 0 cancelados (23 vitórias antes da chegada sem contagem). | O coordenador e o autor do avaliador decidem, antes de rodar o gate: o dono tira o piso (D-391-4 permite) ou o autor de eval (não o executor) emenda o contador com "vitória antes da chegada" e registra a emenda. |
| P3-3 | P3 | `services/reinforcement_cards.py:133`, `:155`, `:217` | `_fire`, `_progress` e `advance` sem type hints (convenção do projeto). `_fire` tem 9 parâmetros posicionais. | Anotar os tipos; passar o líder e o `res` por keyword, ou agrupar. |
| P3-4 | P3 | `tests/test_reinforcement_cards.py:317-330`, `:412-436` | (a) O caso "atordoado" só simula a ausência de `on_declaration`; não há teste no nível do nó para a frustração (R8/R11d: `pressagios_frustrados` → "Presságio frustrado: X" em `registro_rodada`; payload sem `reinforcement` em `cancelled`). (b) O R15 pede `persistence` save → load; os testes usam round-trip JSON. Rodei o caminho real manualmente: passa. (c) O §7 "[H: teste explícito]" pedia teste para "carregar com a flag `off` e chamado pendente". Ele não existe. Nesse caso o `pending_call` não olha a flag e o líder ainda joga a Carta como proteção (sem reforço nem payload). | Follow-up: 1 teste de nó para a frustração (com payload e registro), 1 round-trip por `persistence` com `SAVES_DIR` em `tmp_path`, 1 teste para a flag `off` com estado pendente (assertar o comportamento escolhido). |
| P3-5 | P3 | `web/src/types.ts:283`, `:396` | Reformatação de `Condition`/`InitiativeSlot`, fora do escopo, para compensar as 2 linhas novas no orçamento do arquivo (1.272 → 1.272). Inócuo, mas é ruído no diff. | Aceitável. Se o orçamento obrigar, registre o motivo no commit. |

**Desvios declarados (bloco "Execução"):**

1. **`on_declaration` sem `combat_meta`, marca `scene["chamado_jogado"]`:** aceito. A marca vive na cena
   persistida e é consumida no fim da rodada. Se a luta acaba na mesma rodada, sobra uma marca inerte (inofensiva).
2. **`payload_fields` no módulo novo:** aceito. Mantém o presenter (> 1.000 l.) encolhendo e concentra a
   regra de ouro num ponto testado.
3. **R11c como nota `role="note"` (`data-arrived`) em vez de selo no chip:** aceito. Cumpre "marca na rodada
   da chegada". Posição `distante` e retrato vêm dos caminhos existentes.
4. **R11d não verificado:** aceito como follow-up (P3-4a), **não** como lacuna de comportamento. A nota some por
   construção (`callNote` exige `stage === "called"`; `public_view` devolve `None` em `cancelled`; o teste web
   cobre `reinforcement` ausente). A linha de frustração sai por `pressagios_frustrados` → `round_log.py:435`
   ("Presságio frustrado: …") mais o log "não chega a chamar o bando". Falta só a prova no nível do nó.
5. **R12 (`deck_seed` em `spawn`, `chegou_na_rodada` em `plan`/`_sig_falls_on`):** aceito. Chave ausente no
   legado = byte-idêntico.
6. **R4 (`check_promises` com cena mínima; telegrafo na linha da Carta em `public_round`):** aceito, com a
   ressalva do P3-1.
7. **Eventos/flag/arena/playtest:** aceito. `via` nos 3 eventos, mais `reinforcements_telegraphed`; o catálogo
   e o `EVENTOS_DE_LOG.md` estão em sincronia (teste do registro verde). `flags.yaml` aponta para a SPEC-391.
   Ver P3-2 sobre o contador de cancelados.

## Correções aplicadas

(nenhuma ainda; aguardando o executor para o P2-1)

## Pendências

- P2-1: executor, nesta spec, antes do pouso.
- P3-2: coordenador e autor de eval / dono (D-391-4), antes da Etapa 5.
- P3-1, P3-3, P3-4, P3-5: follow-ups aceitáveis nesta spec ou registrados nela.

## Comandos rodados

```text
git diff 55b85c2c..HEAD --stat → 18 arquivos, +1359/−62
git diff d0298e51..HEAD -- docs/spec391/arena_reforco_cartas.py → vazio
git diff 55b85c2c..HEAD --name-only -- evals scripts/cards/sim.py docs/spec285 docs/spec332 docs/spec368 data/cards/inimigos/_decks.json data/cards/inimigos/lider_matilha.json → vazio
pt.sh test_reinforcement_cards test_spec325_reinforcements test_enemy_decks test_size_budget → 91 passed
pt.sh test_flag_registry test_log_event_registry test_card_lint test_enemy_intent(_node) test_spec355_{promessa_chefe,guardas} test_spec325_flags test_spec371_* … → 202 passed, 1 skipped, 1 xfailed
dup_helpers.py --diff 55b85c2c..HEAD → só colisões de nome
ruff check (arquivos novos/alterados) → limpo
web: node --test tests/conflict-chips.test.mjs → 5/5; tsc --noEmit → rc 0; eslint (3 arquivos) → limpo
sonda (scratchpad): round-trip real via persistence em telegraphed/called → continua, 1 `_r1`, Carta 1×
sonda (scratchpad): Chamado frustrado + defesas gastas → enemy_declaration joga inf_chamado_do_bando (P2-1)
sonda (scratchpad): payload.round == chegou_na_rodada na resposta da chegada → nota "acabou de chegar" acende
```

---

## Re-revisão (delta `50715671..47fe0462`)

> **Veredito:** `APPROVED`, para pousar com `RPG_COMBAT_REINFORCEMENTS=off` (default em `combat_flags._DEFAULT_MODE`). Ficam 3 follow-ups P3, nenhum bloqueante.
> **Revisor:** Opus (papel Sol, `spec-reviewer`) · **Data:** 2026-11-04 · **Commit revisado:** `47fe0462`

### Escopo

6 commits: `8a2c0a36` (P2-1/P3), `481a0774` (emenda da arena, autor de eval), `c5e7c921` (L1), `eb1cabf1` (L2), `044d608c` (L3) e `47fe0462` (gate). Arquivos: `services/reinforcement_cards.py`, `services/reinforcements.py`, `tests/test_reinforcement_cards.py`, `docs/spec391/*` e a spec.

### O que confere

- **P2-1 resolvido.** `_cancel(..., leader)` tira `CALL_CARD` de `leader["cartas"]` só em `stage == "telegraphed"` (a Carta nunca foi jogada). Isso só acontece no caminho `frustrado` (`reinforcement_cards.py:225`). `sem_folga` e `lider_caido` acontecem em `called`, quando a Carta já foi jogada, então removê-la ali não teria efeito. O teste `test_frustrated_call_drops_card_and_never_returns` refaz a minha sonda: `support`/`protect`/`attack` nas rodadas 3–6, e a Carta nunca sai.
- **P3-3 resolvido.** `_fire`, `_progress` e `advance` agora têm tipos, e `_fire` recebe keywords.
- **P3-4 resolvido.** Agora há teste de nó para a frustração (payload sem `reinforcement`/`reinforcement_warning`, registro com "frustrado"), round-trip por `persistence` com `SAVES_DIR` em `tmp_path` (rodadas 1 e 2) e teste para a flag `off` com chamado pendente.
- **Emenda da arena (`481a0774`).** Só acrescenta o contador `countered` (`_countered`, mais `outcome` repassado a `_count_flow`). Sementes, bot, células, denominador (`telegraphed`), `cancelled` e a equivalência `off` não mudaram. A emenda veio antes de qualquer gate, está registrada na spec (§4) e tem teste com 7 casos. `git diff 481a0774..HEAD -- docs/spec391/arena_reforco_cartas.py scripts/cards/sim.py evals docs/spec285 docs/spec332 docs/spec368 data/cards` → vazio: a arena está congelada desde a emenda. A definição nova tem a mesma intenção do critério original (morte e `timeout` não contam como contra-jogo).
- **Flag `off` = legado intacto.** `rf.spawn` e `_template_for` ganharam `slack=0` e `generic=False` como default. O único chamador legado (`reinforcements.py:215`) não passa nenhum dos dois, então o resultado é byte-idêntico. L1, L2 e L3 só valem em `_fire` do fluxo de Carta, e esse fluxo só roda com `mode == "on"`. O `pending_call` agora devolve `None` com a flag diferente de `on`. Para o legado isso não muda nada, porque a promessa `tipo: chamado` só nasce no fluxo `on`. Neutralidade conferida: `neutro-285-{off,on}.json` e `neutro-368-{off,on}.json` diferem só em `elapsed_s`.
- **L2 reaproveita o stun.** A condição `{"control": "stun", "duration": 1}` vai só no recém-chegado (`_recovering`, dentro do laço `for enemy in new`). O teste L2 prova que ela aparece no payload, nega a 1ª ação (nenhuma Carta usada) e expira. Nenhum outro ator é tocado.
- **Assertivas alteradas são do próprio recurso.** `cause "budget" → "sem_folga"` é o nome novo da L1; nenhum outro lugar (eventos, web, docs) lia `"budget"`. O presságio do `_r1` passar da rodada 3 para a 4 é consequência direta da L2, que tira a ação da rodada seguinte à chegada. Nenhuma das duas é regressão.
- **Gate (`47fe0462`).** `gate-resultado.md` registra os 4 gates, o critério da opção 2 e o resultado reprovado. A flag fica `off`, como manda o D-391-5. Os números do gate 4 batem entre o agregado e as linhas de célula.
- **Size budget.** `reinforcement_cards.py` tem 334 l. e `reinforcements.py` 235 (ambos < 1.000). Funções novas ou alteradas ≤ 60 l. (`_fire` ~45). `dup_helpers --diff 50715671..HEAD`: nenhuma colisão. `ruff check` limpo.

### Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-6 | P3 | `services/reinforcement_cards.py:73-78` + `:121-122` | Só no rollback (save com `stage == "telegraphed"` carregado com a flag `off`): o `pending_call` devolve `None`, mas `_cancel` nunca roda, porque `advance_card_flow` sai antes com `mode != "on"`. Assim `CALL_CARD` fica em `leader["cartas"]` e pode voltar como proteção avulsa pelo `_enemy_support_card`, o mesmo sintoma do P2-1. `test_flag_off_with_pending_call_does_not_play_it` cobre só `attack`. Hoje é inalcançável em produção, porque a flag nunca esteve `on` fora da arena e dos testes. | Quando a 391 for religada: filtrar `CALL_CARD` em `_enemy_support_card` / `enemy_card_ids` se a flag não estiver `on`, ou na carga. Estender o teste para `support`/`protect`. |
| P3-7 | P3 | `services/reinforcement_cards.py:144-149` | "Recuperando o fôlego" é um `stun` de verdade, então herda toda a semântica de controle: `card_effects.is_down` (conta como "caído" para Interromper), `controlled` no contexto de reação (`ao_aliado_perder_acao` do líder) e efeitos que removem controle. Fica restrito ao recém-chegado e ao fluxo `on`, mas é mais do que "perde a 1ª ação". | Registrar na spec se a L2 for mantida quando a flag religar, ou trocar por uma marca própria ("pula a 1ª ação") sem `control`. |
| P3-8 | P3 | spec §8 / D-391-5 | L1, L2 e L3 reprovaram, mas pousam no código, cumulativas e dormentes atrás da flag `off`. Se o dono religar a flag, recebe a versão com as três alavancas, não o desenho original. | O coordenador registra no cabeçalho ou no fechamento da spec que o estado pousado é "L1+L2+L3, gate reprovado, flag `off`". Revertê-las ou mantê-las fica para a próxima spec de balanço (a vitória ON de 57–79 % passaria na opção 3). |

### Comandos rodados

```text
git log --oneline 50715671..HEAD → 6 commits; git diff 50715671..HEAD --stat → 12 arquivos
git diff 481a0774..HEAD --name-only -- arena/sim.py/evals/spec285/332/368/data/cards → vazio
pt.sh -n 0 test_reinforcement_cards test_spec325_reinforcements test_size_budget → 73 passed
pt.sh -n 0 test_enemy_decks test_enemy_intent test_flag_registry test_log_event_registry → 71 passed
(serial: RAM livre 0,8 GB no momento)
dup_helpers.py --diff 50715671..HEAD → nenhuma colisão
ruff check (4 arquivos do delta) → All checks passed
neutro-285/368 on×off → iguais exceto elapsed_s
grep stun consumers (card_effects.is_down, orchestrator controlled, reactions ao_aliado_perder_acao) → P3-7
```
