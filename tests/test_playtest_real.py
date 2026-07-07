"""Fase 5 — playtest com LLM REAL: os perfis VITAIS jogam campanhas LONGAS sobre
a stack de roteamento de verdade (ROUTES, não MockLLM) e a gente confere que roda
bem fim a fim — sem exceção não-capturada e sem violar invariante `error`.

O MockLLM esconde o que depende de DECISÃO do LLM (narração, spawn de combate,
conclusão de quest, rota `NONE`). Esta suíte é a contraparte no provider real —
e campanha LONGA acha o que só aparece no turno 20+.

Por que só 4 perfis (não os 10): cada turno real custa ~15s de SLA; 30 turnos ×
4 perfis já é ~30 min. Os 4 VITAIS cobrem os subsistemas de maior risco:
  - explorador   → mundo/viagem/mapa/interiores/fog of war
  - combate      → combate, morte, letalidade, spawn
  - diplomatico  → NPC 3 camadas, recrutamento, gate de cena
  - secret_rusher→ não-vazamento de segredo (R5) com narrador de verdade
Os outros 6 perfis seguem em `playtest/profiles.py` (via CLI `run --profile X`
ou `run --all --real`); a suíte foca profundidade, não largura.

Rodar:  uv run pytest -m llm_playtest -v -s
Turnos por perfil = 30 (dial via env `RPG_PLAYTEST_TURNS=<n>` p/ smoke rápido).
Roda no free tier do Groq (fallback de todos os tiers) — só precisa de GROQ ou
GOOGLE key no .env. Fora do CI padrão (addopts -m "not llm_playtest").
Spec: specs/fase-5.1/5.2/5.3.
"""
import os

import pytest
from dotenv import load_dotenv

load_dotenv(override=True)  # keys vivem no .env, não no ambiente do SO

from playtest.runner import run_campaign

pytestmark = pytest.mark.llm_playtest

_needs_key = pytest.mark.skipif(
    not (os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="sem GROQ_API_KEY nem GOOGLE_API_KEY — playtest real pulado",
)

# Perfis VITAIS do switch de teste real. Campanha longa (default 30 turnos).
VITAL_PROFILES = ["explorador", "combate", "diplomatico", "secret_rusher"]


def _turns() -> int:
    try:
        return max(1, int(os.getenv("RPG_PLAYTEST_TURNS", "30")))
    except ValueError:
        return 30


@_needs_key
@pytest.mark.parametrize("profile", VITAL_PROFILES)
def test_perfil_vital_no_llm_real(profile):
    """Campanha longa do perfil vital no LLM real: completa sem erro nem
    violação `error`. secret_rusher também não pode vazar segredo (R5)."""
    turns = _turns()
    res = run_campaign(profile, turns=turns, seed=7, use_real_llm=True,
                       invariants=True, max_requests=turns * 10)

    # 1) rodou de verdade no LLM (não caiu no MockLLM silenciosamente)
    assert res.mock is False
    assert any(r.provider for r in res.history), \
        "nenhum turno registrou provider — não bateu no LLM real"

    # 2) campanha completou sem exceção não-capturada
    if res.aborted_reason:
        pytest.fail(f"abortou no teto: {res.aborted_reason}")
    assert res.turns_completed == turns
    assert res.errors == [], res.errors

    # 3) estado íntegro — nenhuma violação de severidade `error`
    erros = [v for v in res.violations if v.get("severity") == "error"]
    assert erros == [], erros

    # 4) R5: o narrador real não vaza a verdade oculta dos segredos canônicos
    if profile == "secret_rusher":
        vazou = [v for v in res.violations if v.get("check_id") == "knowledge.secret_leak"]
        assert vazou == [], vazou
