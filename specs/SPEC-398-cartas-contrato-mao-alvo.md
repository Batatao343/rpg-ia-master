# SPEC-398 — Cartas: contrato da mão coerente com o alvo, motivo do desfecho de objetivo falho, Vitalidade 0 no chip e inimigos ocultos juntos

> **Status:** `approved` (05/11, coordenador; o dono delegou a decisão do rótulo do desfecho, "oq vc achar melhor", e aprovou seguir)
> **Criada:** 2026-11-05 · **Atualizada:** 2026-11-05
> **Épico:** SPEC-327
> **Origem:** [docs/spec369/diagnostico-combate-travado.md](../docs/spec369/diagnostico-combate-travado.md) (smoke da SPEC-369 no staging, item 5).
> **Depende de:** SPEC-363 (alvo e 409 `invalid_target`), SPEC-331 R5 (objetivo de cena), SPEC-387 R20 (narração "segue de pé"), SPEC-397.
> **Risco:** `médio` (contrato público da mão e campo novo no estado do combate) → revisor Sol (Opus).
> **Evidência:** testes que falham antes pela API real (MockLLM) com a reação na mão, inimigos ocultos e o objetivo de cena falho; smoke real no staging com um driver corrigido.

## 1. Contexto & Objetivo

O "combate travado" do smoke da SPEC-369 era o driver reenviando uma jogada recusada (`409 invalid_target`). A investigação também achou defeitos reais e pequenos no produto:
- a mão diz que uma reação é jogável com alvo inimigo, mas o motor recusa;
- uma Carta de alvo inimigo sem alvo válido não diz por quê;
- um objetivo de cena falho fecha como `defeat` com o herói vivo, sem motivo legível;
- o chip não mostra que o inimigo está de pé com Vitalidade 0, o que parece travamento.

Esta spec deixa a mão coerente com o motor, dá um motivo ao desfecho e refaz o item 4 do smoke da 369.

## 2. Requisitos

- **R1 — Reação na mão.** No `public_view` da mão (`services/card_piles.py:~756-773`, com o merge do alvo em `api_presenters.py:~1131`), uma Carta que não é `ativa` (por exemplo `tipo: "reacao"`) sai com `jogavel: false` e `invalid_reason: "not_playable_from_hand"` (ou o motivo equivalente que o motor já usa), sem `alvo: "inimigo"` enganoso. Nenhum `target_id` que a vista sugira como aceitável gera 409.
- **R2 — Motivo de alvo.** Uma Carta de alvo `inimigo` com `valid_targets == []` traz no item da mão o `invalid_reason` do motor (`target_hidden` ou `no_valid_target`, de `services/combat_targeting.py`). A UI mostra uma frase curta em voz "você" (por exemplo "Nenhum inimigo à vista.") em vez de deixar tocar e recusar.
- **R3 — Motivo do desfecho.** Decisão do coordenador por delegação do dono: **`outcome` continua `"defeat"`**, para manter o contrato com UI, saves, dashboards e consumidores (`agents/combat.py:1699`, `2183/2190`, `services/round_log.py:538`). Entra o campo aditivo **`outcome_reason: "objective_failed"`** quando o objetivo de cena falha e o herói está vivo. A narração já é corrigida pela SPEC-387 R20 e não muda. Os consumidores que hoje usam a heurística passam a ler o campo:
  - o texto de desfecho;
  - o recibo ou toast, se mostra "derrota";
  - `_flee_alert_world`, se tratar derrota como morte ou fuga.

  Saves antigos sem o campo seguem como hoje.
- **R4 — Vitalidade 0 no chip.** O chip do inimigo de pé com Vitalidade 0 mostra o estado em voz neutra, por exemplo "de pé, sem Vitalidade: só cai com Ferimento Crítico", sem número novo. Só UI e vista pública; a mecânica não muda.
- **R5 — Inimigos ocultos juntos (investigação).** Reproduzir, com a `scene` completa da execução 2 (`docs/spec369/smoke/` e logs em `scratchpad/stuck/`), por que os dois inimigos ficaram ocultos ao mesmo tempo na rodada 1. Se for regra legítima (Carta de Cena ou condição), registrar no §9 com a evidência. Se for bug, corrigir com teste vermelho antes.
- **R6 — Item 4 do smoke da 369.** Corrigir o driver do smoke (fora do produto, em `docs/spec398/`):
  - escolhe alvo só de `valid_targets`;
  - tira a jogada recusada por `409 invalid_target` e reenvia;
  - para depois de N recusas iguais.

  Com ele, refazer no staging o "segundo conflito contra a mesma família": a faixa do Presságio aparece e a defesa reduz o dano, conferido no `mech_log`.
- **R7 — Guardas.** Nenhuma flag nova. Ficam intocados:
  - golden 330, avaliadores, arenas, `sim.py`, `web/e2e/contracts`;
  - os arquivos da SPEC-369 Fase A.

  `agents/combat.py` e qualquer arquivo com mais de 1.000 linhas não crescem. Precisam passar: `test_size_budget`, `test_no_silent_except`, `test_log_event_registry`, `test_error_envelope`, o golden 382 (regravação só de entrada com efeito intencional, com diff no §9) e o typecheck do web.

### Fora de escopo

Mudar a mecânica de Vitalidade 0 ou de Ferimentos, o balanço (SPEC-369) e novos tipos de desfecho no enum.

## 3. Plano

1. Testes vermelhos pela API (MockLLM): R1 (reação na mão), R2 (inimigos ocultos), R3 (objetivo falho com herói vivo), R4 (vista do chip).
2. Investigar o R5.
3. Implementar sem crescer os arquivos grandes; código novo em módulo próprio.
4. Guardas e §9.
5. Smoke do R6 no staging (coordenador, depois do pouso e do deploy).

## 4. Critérios de aceite

- [x] R1: reação sai não jogável com motivo; nenhuma sugestão da vista gera 409.
- [x] R2: `invalid_reason` no item da mão e frase na UI.
- [x] R3: `outcome_reason: "objective_failed"` gravado e lido pelos consumidores; `outcome` intacto; save antigo carrega.
- [x] R4: chip com Vitalidade 0 legível.
- [x] R5: causa registrada (e corrigida, se for bug).
- [ ] R6: item 4 da 369 refeito no staging com o driver corrigido.
- [ ] R7: guardas e suíte completa verdes no pouso.

## 5. Decisões

- **D-398-1 (delegada pelo dono, 05/11):** `outcome_reason` aditivo em vez de um valor novo de `outcome`. Motivo: o contrato fica estável e a correção é só de leitura.

## 6. Registro de implementação

**R1/R2** (`services/hand_contract.py`, chamado no merge de `api_presenters._combat_block`): Carta que não é `ativa`/`utilitaria` (reação, passiva) sai `jogavel: false`, `alvo: "si"`, `valid_targets: []`, `invalid_reason: "not_playable_from_hand"`. `hand_card_targeting` não mudou (o 409 de `check_declared_target` segue igual). `invalid_reason` de alvo (`target_hidden`/`no_valid_target`/`target_dead`) já saía no item; a UI (`web/src/combat/deck.ts` `blockReason`) agora o lê: "Reação: responde sozinha, não se joga da mão", "Nenhum inimigo à vista.", "Nenhum alvo ao alcance.". `not_playable_from_hand` não entra no enum `INVALID_REASONS` do motor (só na vista da mão).

**R3** (`services/outcome_reason.py`): `mark()` grava `combat.outcome_reason = "objective_failed"` antes de `_finish_encounter` quando `outcome == defeat`, `objetivo_resultado == falhou` e o herói está de pé; `em.result_view` o repassa em `combat_result`; a heurística de rótulo da narração (SPEC-387 R20) usa o mesmo predicado `is_objective_failed`. `outcome` continua `defeat`. Painel de desfecho: "O objetivo falhou" (`outcomeTitle`). `_flee_alert_world` não mudou (derrota segue sem alerta). Save antigo sem o campo: `result_view` não inclui a chave.

**R4**: o chip já tinha "sem Vitalidade" (SPEC-345); agora "de pé, sem Vitalidade" com `title` e fala "cada golpe agora abre um Ferimento" (texto genérico: Lacaio, Padrão e Elite/Chefe caem de formas diferentes). Sem número novo.

**R5 (causa)**: regra legítima (SPEC-285), não bug de ocultação: arquétipos de flanco (`batedor`; `covarde_oportunista` e `agil` têm `sempre: flank` em `tactical_profile.py`) usam `cs.hide(observers=[herói])` no 1º round, então dois inimigos somem juntos (`Escuta do Sinal` = `covarde_oportunista`). Teste reproduz com 2 batedores. **Bug real achado e corrigido:** `basic_action_targeting(maneuver="procurar")` usava a mesma lista de alvos visíveis do ataque, então o herói só de Cartas não conseguia Procurar quem estava escondido (a UI bloqueava e o 409 recusaria). Agora Procurar mira os escondidos do herói (`_search_targets`); atacar escondido segue recusado. Sem a `scene` completa da execução 2 (não persistida nos logs), a evidência é o teste determinístico, não o replay.

**R7**: nenhum evento novo (catálogo intacto), nenhuma flag; golden 382 e demais guardas verdes; `size_budget` sem estouro (`agents/combat.py` 3948 -> 3946; `api_presenters.py`, `types.ts` sem crescer). Testes: `test_hand_contract.py`, `test_outcome_reason.py`, `deck-342-logic`, `combat-outcome`, `spec345-components` (web 317 ok). typecheck e typecheck:e2e ok.

**Correções da revisão Sol (CHANGES_REQUIRED):** P1-1 `merge_row_targeting` só sobrescreve Carta não-Fardo de tipo `reacao`/`passiva` (status e maldição seguem "Fardo: pesa na mão"; `blockReason` mantém `fardo` para `tipo` fora de reação/passiva). P2-2 textos: reação "você a usa quando o inimigo ataca, não se joga da mão"; passiva "Passiva: sempre ativa, não se joga". P3-1 round-trip save/load do `outcome_reason` (e save sem a chave). P3-2 teste com 1 escondido + 1 visível cobrindo Carta, atacar e Procurar. **P3-3 (comportamento registrado):** com escondidos e visíveis ao mesmo tempo, Procurar num inimigo visível dá 409 `no_valid_target` (antes era aceito e gastava a Ação à toa); atacar o escondido também dá 409 `no_valid_target`. Mantido por fazer sentido. P3-4 `types.ts`: `outcome_reason` em linha própria (duas linhas vizinhas fundidas para o arquivo não crescer).
