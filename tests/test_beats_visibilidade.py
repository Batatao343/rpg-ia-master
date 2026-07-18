"""Suíte da spec beats-visibilidade-ptbr — sanitizar segredo + PT-BR nos beats.

Offline/determinístico. Ver specs/beats-visibilidade-ptbr.md.
"""
from services import secret_signatures as ss
from playtest import invariants as inv


# --- R1: módulo compartilhado -----------------------------------------------

def test_find_unrevealed_detecta_pacto():
    hit = ss.find_unrevealed("O pacto com Valerius é a ponta do iceberg.", {})
    assert hit and hit[0] == "pacto_valerius"


def test_revelado_nao_dispara():
    state = {"event_log": [{"type": "secret_revealed", "target_id": "pacto_valerius",
                            "payload": {"phrase": "pacto com valerius"}}]}
    assert ss.find_unrevealed("o pacto com valerius", state) is None


def test_invariants_usa_o_modulo():
    # alias mantido para quem importava de invariants
    assert inv._SECRET_SIGNATURES is ss.SECRET_SIGNATURES


# --- R2: sanitizador --------------------------------------------------------

def test_sanitize_beat_neutraliza_segredo():
    out = ss.sanitize_beat("Revele que o pacto com Daruun consumiu a família.", {})
    assert "pacto" not in out.lower() and "daruun" not in out.lower()
    assert "Investigue" in out


def test_sanitize_beat_limpo_passa_intacto():
    beat = "Explore as ruínas de Skallgard e enfrente os bandidos."
    assert ss.sanitize_beat(beat, {}) == beat


# --- R4: heurística de idioma -----------------------------------------------

def test_looks_english_detecta_beat_ingles():
    assert ss.looks_english("Explore the mysteries of Nova Arcadia.") is True


def test_pt_com_nomes_proprios_nao_dispara():
    assert ss.looks_english("Explore as ruínas de Skallgard") is False
    assert ss.looks_english("Revele a inscrição antiga na parede") is False


def test_looks_english_texto_curto_seguro():
    assert ss.looks_english("") is False


# --- R5: invariante checa beats ---------------------------------------------

def test_invariante_secret_leak_no_beat():
    state = {
        "messages": [],
        "campaign_plan": {"beats": [
            {"description": "O pacto com Valerius consumiu a família dele.", "status": "pending"}]},
    }
    viol = inv.check_knowledge(state, None, turn=14)
    assert any(v.check_id == "knowledge.secret_leak" for v in viol)
    assert any(v.details.get("origem") == "beat" for v in viol)


def test_invariante_beat_limpo_nao_dispara():
    state = {"messages": [], "campaign_plan": {"beats": [
        {"description": "Investigue os boatos sobre a Rede Carmesim.", "status": "pending"}]}}
    assert inv.check_knowledge(state, None, 14) == []


# --- achado F: fallback do planner em pt-BR (era inglês) ---------------------

def test_fallback_do_planner_e_pt_br(monkeypatch):
    import agents.campaign_manager as cm

    class _Boom:
        def with_structured_output(self, _m):
            return self
        def invoke(self, _msgs):
            raise RuntimeError("provider caiu")

    monkeypatch.setattr(cm, "get_llm", lambda *a, **k: _Boom())
    plan = cm._build_plan({"world": {"current_location": "Nova Arcádia", "turn_count": 3},
                           "messages": []})
    assert plan is not None
    for b in plan["beats"]:
        assert not ss.looks_english(b["description"]), b["description"]
    assert not ss.looks_english(plan["climax"])
