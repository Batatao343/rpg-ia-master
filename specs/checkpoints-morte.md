# SPEC — Checkpoints + restore na morte (substitui a "2ª chance com poção")

> **Status:** `done` (2026-07-21 — 8 decisões + fundação + vertical de morte + higiene do Saque órfão; smoke real em validação)
> **Criada:** 2026-07-20 · **Atualizada:** 2026-07-20 · **Origem:** decisão do usuário sobre a letalidade por zona perigosa (run `20260720-093014`)
> **Substitui:** o modelo "O Saque = 2ª chance com poção grátis" ([balanceamento-early-game](balanceamento-early-game.md) R3 + [pos-saque-recuperacao](pos-saque-recuperacao.md))
> **Interage com:** [letalidade-early-game-v2](letalidade-early-game-v2.md) (A — survivability), [checkpoints ≠ nerf de perigo]

---

## 1. Contexto & Objetivo

Decisão do usuário sobre o achado C do run (explorador one-shot em zona
high-danger, nível 1–2): **"O jogador DEVE ser punido por ir a lugares
perigosos."** O soft-gate (aviso/escala por nível) foi REJEITADO — perigo é
perigo. Em vez de suavizar a zona OU dar 2ª chance com item grátis, o modelo
passa a ser **checkpoint + restore**: o jogo salva um ponto seguro a cada X
turnos (e/ou em marcos), e a morte **reverte para esse checkpoint** — o jogador
perde o progresso desde o último checkpoint (punição real), mas não perde a saga.

Isto **substitui** a "2ª chance sem item" do Saque (hoje `apply_downed` deixa 1
poção e a campanha segue). Punição vira "voltar no tempo", não "ganhar de graça".

**Objetivo:** morte é consequência (perde turnos/loot desde o checkpoint), não
fim-de-saga arbitrário; ir a zona perigosa sub-nivelado continua sendo burrice
punida — só que recuperável a um custo.

## 2. Requisitos

- **R1 — Checkpoint automático determinístico.** O jogo grava um snapshot
  restaurável do `GameState` em pontos definidos (cadência + marcos — ver §2.1).
  Snapshot = estado COMPLETO serializável (mesmo shape que `persistence`), isolado
  do save "vivo".
- **R2 — Tela de morte + restore (D2).** Quando o golpe seria letal (hoje:
  `game_over=True` + `player_died`), NÃO vira memorial automático: abre a escolha
  "Continuar do checkpoint" / "Aceitar a morte". "Continuar" **reverte ao último
  checkpoint** (D5, 1 slot) e a saga segue dali, com reversão explícita ao jogador
  (narração "a Roda te trouxe de volta a…", HUD indica o ponto).
- **R3 — Punição = progresso perdido (D3).** Restaurar custa todo turno/loot/XP
  desde o checkpoint. SEM custo extra e SEM item de consolação. (Reavaliar se
  ficar leve demais — fora do MVP.)
- **R4 — Remover a "2ª chance com poção" (D4).** `apply_downed` deixa de conceder
  poção grátis; a queda letal aciona a tela de morte (R2). `pos-saque-recuperacao`
  (carência/beat de recuperação) é reavaliada — o que sobrepõe vira redundante e
  sai (sem código morto).
- **R5 — Sem save-scumming na API stateless.** Checkpoint vive no servidor por
  `game_id` (não confiável no cliente). **1 slot** por save (D5, sobrescreve).
- **R6 — Memorial voluntário preserva o fluxo atual.** "Aceitar a morte" seta o
  `game_over`/memorial que já existe (crônica-memorial + 409 da API + gate
  `game_over→__end__`). O memorial NÃO é removido — só deixa de ser imposto por
  dano. Nenhum permadeath automático (D8).
- **R7 — Harness (D6).** Ao detectar a morte, o runner sempre "Continua"
  (auto-restore em memória) e incrementa `deaths`; `first_death_turn` preservado.
  Nunca escolhe memorial.
- **R8 — Sem checkpoint ainda (D7).** Morte antes do 1º checkpoint restaura do
  **estado inicial da sessão** (checkpoint zero implícito) — nunca game_over por
  falta de ponto. Save antigo sem o campo carrega normal.

### 2.1 DECISÕES — RESOLVIDAS (2026-07-20)

| # | Questão | **Decisão** |
|---|---|---|
| D1 | Cadência do checkpoint | **a cada 10 turnos E ao entrar em zona segura** (cidade danger≤1 / descanso / beat concluído) |
| D2 | Gatilho do restore | **tela de escolha** na morte: "Continuar do checkpoint" OU "Aceitar a morte" |
| D3 | Custo extra | **nenhum** — perder o progresso desde o checkpoint já é a punição |
| D4 | Destino "O Saque" | **removido** — a 2ª chance com poção grátis sai; a queda letal aciona a tela de morte |
| D5 | Nº de checkpoints | **1 slot** (sobrescreve o anterior) |
| D6 | Política do harness | **restaura e conta mortes** (auto-restore, sem humano p/ a tela); mantém `first_death_turn` |
| D7 | Sem checkpoint disponível | **restaura do início da sessão** (o estado inicial é o checkpoint zero) |
| D8 | Modo permadeath imposto | **não existe** — nunca se impõe fim de saga |

**Modelo consolidado (a chave — esclarecimento do usuário):** o **memorial é uma
ESCOLHA do jogador, nunca imposto.** Na tela de morte (D2) ele decide:
- **"Continuar do checkpoint"** → restaura ao último checkpoint (ou ao início da
  sessão se ainda não houver, D7). Punição = perder o progresso desde ali (D3).
- **"Aceitar a morte"** → **memorial**: a saga encerra, a crônica vira memorial
  (o `game_over`/memorial ATUAL, preservado — mas agora só por esta via voluntária).

Consequência: `game_over` deixa de ser imposto por dano; morte por golpe SEMPRE
abre a tela. O memorial (crônica + 409 da API + gate `game_over→__end__`) **continua
existindo**, acionado só quando o jogador elege "Aceitar a morte". O harness, sem
humano, sempre escolhe "Continuar" (D6) e nunca vira memorial.

### Fora de escopo

- Suavizar zona perigosa / soft-gate de nível (REJEITADO pelo usuário).
- Survivability de early-game (poções/HP/dano/recovery) — é a spec A.
- Autosave contínuo / múltiplos saves nomeados pelo jogador (já existe tela de saves).

## 3. Design técnico (esboço — fecha após §2.1)

- **`persistence.py`** ou novo `services/checkpoints.py`:
  `write_checkpoint(state)` / `load_checkpoint(game_id)` / `has_checkpoint(game_id)`.
  Arquivo `saves/{game_id}.checkpoint.json` (mesmo serializador de mensagens
  LangChain que `save_game_state`).
- **Gatilho de gravação:** determinístico, no fim do turno (archivist ou pós-save
  em `api.py`/`game_engine.py`) — quando `turn % N == 0` OU entrou em zona segura.
- **Gatilho de restore:** onde hoje `game_over=True` é setado
  ([agents/combat.py:712](agents/combat.py)) — em vez de memorial, se
  `has_checkpoint`, oferecer/aplicar restore (D2). API: novo endpoint
  `POST /game/restore` (ou parâmetro na ação) que troca o save vivo pelo
  checkpoint; CLI: prompt no loop.
- **`main.py`:** o gate `game_over → __end__` continua; o restore acontece FORA
  do grafo (recarrega estado), não como nó.
- **Harness:** `runner.py` ganha `--restore-on-death` (D6): ao detectar
  `game_over`, recarrega o checkpoint em memória e segue, incrementando
  `deaths`; `first_death_turn` continua sendo o 1º.

## 4. Plano passo a passo (após aprovação de §2.1)

1. **Testes primeiro:** `write/load/has_checkpoint` round-trip; morte com
   checkpoint → estado revertido (turnos desde o checkpoint sumiram, saga viva);
   morte sem checkpoint → política D7; save antigo carrega.
2. **Implementação:** módulo de checkpoint + gatilhos (grava/restaura) + endpoint/
   CLI + flag do harness; aposentar poção-grátis do Saque (D4).
3. **Verificação:** `uv run pytest` verde; smoke real de morte→restore.

## 5. Critérios de aceite

- [x] §2.1 decidido e cravado na spec (8 decisões, 2026-07-20)
- [x] Checkpoint grava/restaura round-trip fiel (teste); grava a cada 10 turnos + zona segura (D1), 1 slot (D5)
- [x] Tela de morte com 2 opções; "Continuar" reverte ao checkpoint e a saga segue; "Aceitar" → memorial (D2)
- [x] Morte antes do 1º checkpoint restaura do início da sessão (D7 — checkpoint inicial no /game/new)
- [x] "2ª chance com poção" removida do fluxo (D4, combat não chama mais apply_downed); sem regressão de save antigo
- [x] Harness auto-restaura + conta `deaths` (`deaths_log`); `first_death_turn` preservado (D6/R7)
- [x] Memorial (crônica/409/gate) intacto, só por via voluntária "Aceitar" (R6)
- [x] `uv run pytest` verde (1020); `npm run build` verde
- [x] Código órfão do Saque + testes removidos (higiene §7.1); zero símbolo órfão
- [x] **Smoke real `done`** (run `20260721-042146`, combate/sangromante 25t, DeepSeek
      $0.051, 0 erro de motor): morreu **4× (1ª no t13), auto-restaurou cada vez e
      seguiu até t25** — antes a campanha abortava no t13. `deaths=4` no summary,
      %ativa 44%. **Bug pego pelo smoke:** o invariante `vitals.dead_no_game_over`
      falso-disparava na morte (hp=0 agora vem com `death_pending`, não game_over) →
      corrigido (aceita `death_pending`) + teste. Suíte 1019 → 1020.

## 6. Riscos & compatibilidade

- **Save-scumming:** checkpoint no servidor por `game_id` mitiga; API stateless
  não expõe o slot ao cliente.
- **Colisão com `pos-saque-recuperacao`:** parte (poção grátis, carência) fica
  redundante — a spec revisa/aposenta o que sobrepõe, sem deixar código morto.
- **Tom narrativo:** o restore precisa de justificativa diegética (a "Roda"/ciclo
  do Abismo?) pra não quebrar imersão — coordenar flavor com a lore de Valoria.
- **Harness:** se restaurar e continuar, campanhas ficam mais longas/caras no
  real — flag default off no `--real`.

---

## 7.1 Estado de implementação (2026-07-20)

**FUNDAÇÃO `done` (testada, não-quebrável, não altera o jogo jogável ainda):**
- `services/checkpoints.py` — `should_checkpoint` (D1: 10 turnos + zona segura),
  `entered_safe_zone`, `snapshot` (deepcopy in-memory), `maybe_write`,
  `resolve_death_choice` (D2: accept→memorial / continue→restaura checkpoint→disco
  →initial_state por D7).
- `persistence.py` — refatorado p/ fonte única (`_state_to_save_data`/
  `_raw_to_state`, reusados pelo save vivo); novos `save_checkpoint`/
  `load_checkpoint`/`has_checkpoint` (D5: slot `{game_id}.checkpoint.json`).
- `tests/test_checkpoints.py` — 12 testes (round-trip, slot único, cadência,
  zona segura, accept/continue/D7). Suíte global verde.

**VERTICAL DE MORTE — `done` (2026-07-20):**
1. `agents/combat.py` — golpe letal seta `death_pending=True` (não `game_over`);
   sem apply_downed/Saque; narração `_narrate_fall` (2ª pessoa) + evento
   `player_downed` com local/causa. ✓
2. `state.py` + `persistence.py` — campo `death_pending` (persiste entre requests
   da API stateless). `main.py` — gate `death_pending → __end__` (não processa
   turno com o herói caído). ✓
3. `playtest/runner.py` — `death_pending` → auto-`resolve_death_choice("continue")`
   (checkpoint in-memory por `should_checkpoint`, senão snapshot inicial),
   `deaths_log`, NÃO encerra a campanha; `telemetry` conta mortes do `deaths_log`
   (o restore limpa o event_log). ✓
4. `api.py` — `maybe_write` no fim do turno (POST e stream); checkpoint inicial no
   `/game/new` (D7); `POST /game/death` {choice}; `/game/action` e o stream
   barram (409) com queda pendente; `GameResponse.death_pending`. **+5 testes.** ✓
5. `web/` — `DeathModal` (2 botões) + `resolveDeath` + CSS; `game_engine.py` prompt
   CLI + checkpoint inicial. `npm run build` verde. ✓

**HIGIENE DO SAQUE ÓRFÃO — `done` (2026-07-21):** o "O Saque" e o
`pos-saque-recuperacao` foram INTEGRALMENTE aposentados (substituídos por este
modelo de checkpoint/restore). Removidos:
- `combat_mechanics.apply_downed` + `death_outcome`;
- `agents/combat._death_template` + `_narrate_downed`;
- `agents/campaign_manager._downed_recente` + `_prefix_recovery_beat` (beat de recuperação);
- `agents/storyteller._recovery_clause` + o branch `downed_grace_active` do sorteio de encontro;
- `world_utils.downed_grace_active` + limpeza de `downed_recente` no `apply_rest`;
- invariantes `check_downed` (downed.repeated/in_apex/vs_boss) + `check_downed_recovery`;
- campo `state.downed_grace_until_day`.
- Testes: `tests/test_pos_saque.py` REMOVIDO (13); 6 testes do Saque em
  `test_balance_early` + `test_template_morte_digno` removidos. **Suíte 1039 → 1019**
  (net −20 do Saque; o vertical adicionou os seus). Zero símbolo órfão restante
  (só comentários apontando o novo modelo).
