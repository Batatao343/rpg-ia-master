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
