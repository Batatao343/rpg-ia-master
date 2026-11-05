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

- [ ] R1: reação sai não jogável com motivo; nenhuma sugestão da vista gera 409.
- [ ] R2: `invalid_reason` no item da mão e frase na UI.
- [ ] R3: `outcome_reason: "objective_failed"` gravado e lido pelos consumidores; `outcome` intacto; save antigo carrega.
- [ ] R4: chip com Vitalidade 0 legível.
- [ ] R5: causa registrada (e corrigida, se for bug).
- [ ] R6: item 4 da 369 refeito no staging com o driver corrigido.
- [ ] R7: guardas e suíte completa verdes no pouso.

## 5. Decisões

- **D-398-1 (delegada pelo dono, 05/11):** `outcome_reason` aditivo em vez de um valor novo de `outcome`. Motivo: o contrato fica estável e a correção é só de leitura.

## 6. Registro de implementação

(vazio)
