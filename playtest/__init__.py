"""Harness de playtest agêntico (Fase 5).

Roda campanhas longas de forma programática sobre o MESMO grafo LangGraph da
API (`app.invoke`), com perfis de jogador determinísticos (heurística Python,
sem LLM decidindo ação). Custo zero de quota com MockLLM; LLM real é opt-in.

Submódulos:
  - runner    : run_campaign / CampaignResult / TurnRecord
  - profiles  : PROFILES (10 perfis) — cada um next_action(state, rng) -> str
  - invariants: check_all / assert_invariants (Fase 5.2)
  - telemetry : JSONL por turno + summary (Fase 5.3)
  - report    : aggregate / render_markdown (Fase 5.3)
"""
