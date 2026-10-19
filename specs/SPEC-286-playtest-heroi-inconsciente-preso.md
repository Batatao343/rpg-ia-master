# SPEC-286 — Playtest preso com herói inconsciente (perfil, rota do guard, contrato JSONL)

> **Status:** `done` (aprovada sob a autorização do dono de 19/10 para tudo que não exige ação externa dele)
> **Criada:** 2026-10-19 · **Origem:** achado da SPEC-283 (reproduzível na main)
> **EXECUTOR_MODEL:** `Sonnet` · **REVIEW_REQUIRED:** `false` (só harness de playtest; produto intacto)

## 1. Contexto
`playtest run --profile combate --turns 200` com seeds 23/24 saía exit 1 sem erro/violação: após vencer
um combate o herói ficava inconsciente e o perfil continuava propondo "Viajo para X em busca de abrigo
antes de descansar" (turnos 142–200 repetidos). O `action_guard` recusa tudo que não seja recuperação;
o turno nem chegava ao router, então `route` ficava `''` e o manifesto marcava "contrato JSONL inválido".

## 2. Diagnóstico
- (a) O JOGO tem saída válida: o guard avisa "Declare descanso, tratamento ou aguarde socorro" e
  `evaluate_action` aceita recuperação (`_RECOVERY`, `fullmatch`) em UNCONSCIOUS/INCAPACITATED. Não é bug de produto.
- (b) Bug do perfil: `_recovery_decision` viajava quando `danger_level > 3`, mesmo inconsciente; e o texto
  de descanso ("Descanso: monto acampamento para recuperar as forças.") não casa o `fullmatch` estrito.
- (c) Bug do harness: recusa do guard encerra o grafo antes do `dm_router`, rota `''`.

## 3. Requisitos
- R1: inconsciente/incapacitado nunca viaja; o texto de recuperação é aceito pelo guard (`Descanso para me recuperar.`).
- R2: turno recusado pelo guard grava `route="action_guard"` e `guard_code` (ex. `blocked_unconscious`) no JSONL.
- R3: o contrato JSONL aceita `action_guard` (sem exigir `archivist` em `nodes_executed`).
- R4: regressão offline + prova com seeds 21/23/24.

## 4. Critérios de aceite
- [x] `tests/test_spec286_heroi_inconsciente.py` (3 testes): todos os perfis recuperam inconscientes; incapacitado idem; rota do guard não vazia.
- [x] `playtest run --profile combate --turns 200 --seed N` para N=21, 23, 24: exit 0, 200 turnos, 0 erro/violação, 0 `route ''`, 0 recusas do guard (antes: exit 1, 59+ turnos perdidos).
- [x] Suíte completa registrada no hand-back.
