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


def test_rede_carmesim_iminencia_detectada():
    # curadoria 2026-07-19: a iminência calculada (décadas→meses) é a VERDADE
    # oculta da Rede Carmesim; nome/monitoramento é público no norte.
    hit = ss.find_unrevealed(
        "O plano acelera o despertar de décadas para meses.", {})
    assert hit and hit[0] == "rede_carmesim"
    out = ss.sanitize_beat(
        "Revele que a Câmara mede a Rede acelerando mais rápido do que admitem.", {})
    assert "Investigue" in out and "acelerando" not in out.lower()


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


# --- spec D (2026-07-20): segredo já conhecido pelo jogador não é vazamento ---

class _Msg:
    """Mensagem mínima que _last_narration entende (content + type)."""
    def __init__(self, content, type="ai"):
        self.content = content
        self.type = type


def test_revealed_corpus_inclui_resumo_narrativo():
    # a Velha Magda contou o pacto ao jogador -> registrado no resumo diegético
    state = {"narrative_summary": "A Velha Magda revelou o pacto com Daruun ao herói."}
    assert ss.find_unrevealed("o pacto com daruun ainda queima na memória", state) is None


def test_known_secrets_explicito_desarma_assinatura():
    state = {"player": {"known_secrets": ["pacto com daruun"]}}
    assert ss.find_unrevealed("Onde Valerius esconde o pacto com Daruun.", state) is None


def test_invariante_secret_leak_ignora_conhecido_pelo_player():
    # narração REPETE o segredo, mas o jogador já sabe (resumo) -> sem violação
    state = {
        "messages": [_Msg("O coração da besta bate no Poço dos Ossos, onde Valerius "
                           "esconde o pacto com Daruun.")],
        "narrative_summary": "A Velha Magda já te disse: o pacto com Daruun.",
    }
    viol = inv.check_knowledge(state, None, turn=40)
    assert not any(v.check_id == "knowledge.secret_leak" for v in viol)


def test_invariante_secret_leak_ainda_dispara_quando_nao_conhecido():
    # sem o jogador saber, a narração vazando o segredo AINDA é violação
    state = {
        "messages": [_Msg("Valerius esconde o pacto com Daruun em troca de imortalidade.")],
        "narrative_summary": "O herói chega a Nova Arcádia.",
    }
    viol = inv.check_knowledge(state, None, turn=5)
    assert any(v.check_id == "knowledge.secret_leak" for v in viol)


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
