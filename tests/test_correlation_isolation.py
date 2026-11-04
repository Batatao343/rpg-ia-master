"""A correlacao de log (SPEC-240) nao vaza entre testes do mesmo processo.

Handlers chamados direto (``routes.turn._execute_action``) fazem ``bind_correlation`` sem
escopo; em producao cada request roda em contexto proprio, mas no pytest o contexto e o da
thread principal. Sem o isolamento do conftest, o ``game_ref``/``action_ref`` de um teste
aparecia nos eventos do seguinte (ex.: o golden da SPEC-382 divergia so na ordem da suite).
Os dois testes rodam em ordem no mesmo processo em ``-n 0``.
"""

from __future__ import annotations

from observability.telemetry import bind_correlation, correlation


def test_a_unscoped_bind_leaves_context_dirty():
    bind_correlation(game_id="g-leak", action_id="a-leak")
    assert "game_ref" in correlation()


def test_b_next_test_starts_with_clean_correlation():
    assert correlation() == {}
