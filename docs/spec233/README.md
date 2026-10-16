# SPEC-233 — evidência

Testes de reprodução (vermelhos no HEAD, verdes agora): `tests/test_bug_mundo_perigo_luz_clima.py` (9 testes, R1-R9).
Mudanças: `world_utils.py` (effective_danger, decay, luz estrutural, flag one-shot, clima por steps), `agents/world_simulator.py`
(clamp base±1 + decaimento), `services/graph_resolver.py` (filtro nas edges dinâmicas), `agents/storyteller.py`
(dedupe exceto reforços, fações por delta, except preserva mecânica e texto em 2ª pessoa), `main.py`/`api.py` (laboratório
encerrado -> 409 `simulation_finished`), `playtest/invariants.py` (`world.danger_mismatch`).
Playtest offline 40t: explorador 20261016-023806-197930, normal 20261016-023809-277698 (0 erros/violações).
Limites: smoke com LLM real (seção 6 da spec) não executado; README do simulador não atualizado além desta nota
(contrato: ação após vitória responde 409).

## Revisão (2026-10-16)

Revisão Sol independente: APPROVED_WITH_FOLLOWUPS — corrigidos: ascensão de facção apagada pelo decaimento do drift,
leitura de override em dict no world_simulator, `turn_baseline`/rastro/`player_downed` no `except` do storyteller.
Coordenador: `ensure_world` recalcula sempre o perigo efetivo (save antigo corrigido no load). Laboratório: o frontend
já bloqueia a entrada e oferece "Configurar nova simulação" com a mesma condição do 409. Smoke §6: mecânica Python
coberta por `test_dungeon_is_dark_without_torch`, `test_finished_simulation_rejects_action` e
`test_storyteller_exception_keeps_rest`.
