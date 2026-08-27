# SPEC — Resultado canônico do turno antes da apresentação

> **Status:** `in-progress` — implementação offline verde; aguarda matriz B real
> **Criada/Atualizada:** 2026-08-27
> **Depende de:** `feedback-ledger-recompensas` e eventos estruturados (`done`)
> **Supera:** cobertura apenas intranó de `feedback-ledger-recompensas`

## 1. Contexto & Objetivo

Nos turnos 39, 42, 80 e 94 do quester, a narração disse que nada foi obtido e o
archivist pagou ouro/XP logo depois. O write model estava correto; a view enviada
ao jogador foi produzida cedo demais. Esta spec torna o estado/event log
autoridade e deriva uma apresentação final comum somente depois de todas as
mecânicas síncronas.

O desenho segue CQRS/event sourcing: o agregado de escrita protege consistência;
views são derivadas e descartáveis. Referências: [CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs),
[Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
e [Materialized View](https://learn.microsoft.com/en-us/azure/architecture/patterns/materialized-view).

## 2. Requisitos

- **R1 — Baseline:** início do turno captura somente campos necessários do ledger
  (ouro, XP, nível, inventário, quests e event ids), sem copiar o estado inteiro.
- **R2 — Finalização:** depois do archivist, um finalizer Python calcula
  `last_turn_outcome` idempotente com deltas e eventos confirmados.
- **R3 — Autoridade:** nenhum valor narrado concede recurso; o outcome deriva
  exclusivamente do estado consolidado.
- **R4 — Reconciliação conservadora:** se o texto negar ganho confirmado, remover
  apenas a sentença contraditória e anexar um recibo canônico curto. Não tentar
  reescrever semanticamente toda a prosa.
- **R5 — Uma apresentação:** API comum, SSE, CLI e playtest consomem o mesmo texto
  final; não podem selecionar mensagens diferentes.
- **R6 — Dedupe:** receipt id estável por `game_id + turn + delta`; retries não
  duplicam texto nem recompensa.
- **R7 — Observabilidade:** `turn.outcome_reconciled` registra categorias e ids,
  nunca prompt/prosa completa.
- **R8 — Invariante:** compara baseline/outcome/apresentação, não snapshots
  acidentais de mensagens intermediárias.

### Fora de escopo

Toast visual novo, async do archivist e mudanças nos valores de recompensa.

## 3. Design técnico

- Novo `services/turn_outcome.py`: `capture_baseline`, `finalize_outcome`,
  `render_player_message`; todas puras/idempotentes.
- `state.py`: `turn_baseline` transitório e `last_turn_outcome` persistido.
- Novo `agents/turn_finalizer.py`; todas as saídas de archivist passam por ele
  antes de `END`.
- `api.format_response`, SSE, CLI e `playtest.runner` chamam um helper único
  `player_facing_message(state)`.

## 4. Plano TDD

1. `tests/test_turn_outcome.py`: quest pendente → storyteller nega → archivist
   paga → finalizer remove negação, preserva prosa e confirma ouro/XP uma vez.
2. Cobrir ganho de item, nenhuma mudança, retry idempotente e narrativa que já
   confirma corretamente.
3. Teste contratual compara resposta normal, SSE, CLI helper e harness.
4. Implementar fiação e substituir consumidores; suíte completa.

## 5. Critérios de aceite

- [x] As quatro sequências da matriz A têm regressão curta.
- [x] Estado/event log são fonte única; texto nunca concede economia.
- [x] Quest reward tardia aparece na mesma resposta do turno.
- [x] Nenhuma apresentação contém negação contraditória.
- [x] Retry não duplica recibo/recurso.
- [x] API, SSE, CLI e harness exibem o mesmo texto.
- [x] Suíte completa offline verde e saves antigos carregam.
- [ ] Matriz B real confirma zero contradição de recompensa.

## 6. Smoke real

Completar uma quest com ouro via evento proposto pelo LLM; comparar texto,
`last_turn_outcome`, ledger e resposta SSE.

## 7. Riscos

Sanitização ampla poderia apagar prosa válida; os padrões serão fechados e só
ativados quando o delta canônico contradiz explicitamente a frase.
