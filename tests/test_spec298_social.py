"""SPEC-298 Etapa 6 — abordagens sociais, informação por faixa e favores (R20-R24)."""

import pytest

from agents.npc import _resolve_social
from agents.router import RouterDecision, RouteType
from services import conflict_resolution as cr
from services import reputation as rep


def _npc(rel=5, traits=(), **extra):
    return {
        "id": "npc_brenna",
        "name": "Brenna",
        "relationship": rel,
        "hidden_traits": list(traits),
        "revealed_traits": [],
        "race_id": "",
        **extra,
    }


def _state(npc=None, gold=10, day=3, turn=7, **extra):
    st = {
        "game_id": "g298",
        "player": {"name": "T", "gold": gold, "virtudes": {"forca": 3, "mente": 3}},
        "world": {
            "turn_count": turn,
            "current_location_id": "nova_arcadia",
            "world_clock": {"day": day, "period": "manha"},
        },
        "npcs": {"Brenna": npc or _npc()},
        "factions": [],
    }
    st.update(extra)
    return st


def _fake_roll(success, calls=None):
    def fake(actor, virtude_key, dificuldade, *, ruptura=False, rng=None):
        if calls is not None:
            calls.append((virtude_key, dificuldade, rng.random() if rng else None))
        return {"sucesso": success, "total": 99 if success else 0, "dificuldade": dificuldade}

    return fake


def test_router_social_approach_invalido_vira_conversar():
    base = {"route": RouteType.NPC, "loot_context": None, "target": None, "reasoning": "r"}
    d = RouterDecision(**base, confidence=0.9, social_approach="ameacar", favor_kind="roubar")
    assert d.social_approach == "conversar" and d.favor_kind is None
    ok = RouterDecision(**base, confidence=0.9, social_approach="pedir_favor", favor_kind="esconder")
    assert (ok.social_approach, ok.favor_kind) == ("pedir_favor", "esconder")
    assert RouterDecision(**base, confidence=0.9).social_approach is None
    assert rep.normalize_social_intent("xyz", "abc") == {"approach": "conversar", "favor_kind": None}


def test_intimidar_usa_trait_e_infamia_no_dc(monkeypatch):
    calls = []
    monkeypatch.setattr(cr, "general_test", _fake_roll(True, calls))
    npc = _npc(traits=["covarde"])  # intimidacao -3
    rep.social_check(_state(npc), npc, "intimidar")
    assert calls[-1][:2] == ("forca", 9)
    st = _state(npc, location_fame={"nova_arcadia": {"renown": 0, "infamy": 35}})
    rep.social_check(st, npc, "intimidar")
    assert calls[-1][1] == 7  # 12 - 3 (covarde) - 2 (temido)
    st = _state(npc, location_fame={"nova_arcadia": {"renown": 0, "infamy": 70}})
    rep.social_check(st, npc, "intimidar")
    assert calls[-1][1] == 6  # odiado -3


def test_intimidar_seed_deterministica(monkeypatch):
    calls = []
    monkeypatch.setattr(cr, "general_test", _fake_roll(True, calls))
    npc = _npc()
    rep.social_check(_state(npc), npc, "intimidar")
    rep.social_check(_state(npc), npc, "intimidar")
    assert calls[0][2] == calls[1][2]
    rep.social_check(_state(npc, turn=8), npc, "intimidar")
    assert calls[2][2] != calls[0][2]


def test_intimidar_sucesso_eleva_revelacao_e_custa_relacao(monkeypatch):
    monkeypatch.setattr(cr, "general_test", _fake_roll(True))
    npc = _npc(rel=5)
    social, row, _extra, notices = _resolve_social(_state(npc), "Brenna", npc, {"approach": "intimidar"})
    assert social["success"] and social["reveal_mode"] == "up"
    assert row["relationship"] == 4
    assert any(n["text"] == "Brenna não gostou disso." for n in notices)
    assert rep.clamp_reveal("progresso", "neutro", "up") == "objetivo"
    assert rep.clamp_reveal("progresso", "desconfiado", "up") == "existencia"


def test_intimidar_falha_fecha_o_npc(monkeypatch):
    monkeypatch.setattr(cr, "general_test", _fake_roll(False))
    npc = _npc(rel=5)
    social, row, _e, _n = _resolve_social(_state(npc), "Brenna", npc, {"approach": "intimidar"})
    assert not social["success"] and social["reveal_mode"] == "none"
    assert row["relationship"] == 4
    assert rep.clamp_reveal("existencia", "leal", "none") == ""


def test_sondar_sucesso_revela_um_traco(monkeypatch):
    monkeypatch.setattr(cr, "general_test", _fake_roll(True))
    npc = _npc(rel=2, traits=["covarde", "ganancioso"])
    social, row, _e, notices = _resolve_social(_state(npc), "Brenna", npc, {"approach": "sondar"})
    assert row["revealed_traits"] == ["covarde"] and row["hidden_traits"] == ["ganancioso"]
    assert any(n["text"] == "Você percebe que Brenna desconfia de você." for n in notices)
    assert row["relationship"] == 2  # sem efeito na relação


def test_sondar_falha_sem_efeito(monkeypatch):
    monkeypatch.setattr(cr, "general_test", _fake_roll(False))
    npc = _npc(traits=["covarde"])
    social, row, _e, notices = _resolve_social(_state(npc), "Brenna", npc, {"approach": "sondar"})
    assert row == npc and notices == [] and not social["success"]


def test_sondar_dc_usa_insight(monkeypatch):
    calls = []
    monkeypatch.setattr(cr, "general_test", _fake_roll(False, calls))
    npc = _npc(traits=["honesto_demais"])  # insight -3
    rep.social_check(_state(npc), npc, "sondar")
    assert calls[-1][:2] == ("mente", 9)


def test_reveal_clamp_por_faixa():
    order = ["", "existencia", "objetivo", "progresso"]
    for tier, top in [("hostil", ""), ("desconfiado", ""), ("neutro", "existencia"),
                      ("amistoso", "objetivo"), ("leal", "progresso")]:  # fmt: skip
        assert rep.clamp_reveal("progresso", tier) == top
        assert rep.clamp_reveal("existencia", tier) == min(
            "existencia", top, key=order.index
        )


def test_teto_linhas_conhecimento_por_faixa():
    from services import npc_knowledge

    npc = _npc(rel=1, relationship_basis={"race": 0})
    assert npc_knowledge._lines_cap(_state(npc), "Brenna") == 0
    npc = _npc(rel=5, relationship_basis={"race": 0})
    assert npc_knowledge._lines_cap(_state(npc), "Brenna") == 4
    npc = _npc(rel=10, relationship_basis={"race": 0})
    assert npc_knowledge._lines_cap(_state(npc), "Brenna") == 8
    legado = _npc(rel=1)  # sem relationship_basis: NPC pré-SPEC-298 mantém o teto antigo
    assert npc_knowledge._lines_cap(_state(legado), "Brenna") == 8


def test_favor_esconder_grava_shelter():
    npc = _npc(rel=8)
    dec = rep.favor_decision(_state(npc), npc, "esconder")
    assert dec["ok"]
    patch = rep.apply_favor(_state(npc), "Brenna", npc, "esconder")
    shelter = patch["world"]["shelter"]
    assert shelter["npc_id"] == "npc_brenna" and shelter["location_id"] == "nova_arcadia"
    assert shelter["until_clock"] > 0
    assert patch["npc"]["favors"]["last_day"] == 3


def test_favor_emprestar_e_divida_vencida():
    npc = _npc(rel=10)
    assert rep.favor_decision(_state(npc), npc, "emprestar")["ok"]
    assert not rep.favor_decision(_state(_npc(rel=8)), _npc(rel=8), "emprestar")["ok"]
    patch = rep.apply_favor(_state(npc, gold=10), "Brenna", npc, "emprestar")
    assert patch["player"]["gold"] == 60
    debt = patch["npc"]["favors"]["debt"]
    assert debt == {"amount": 50, "due_day": 10, "overdue_applied": False}
    st = _state(patch["npc"], day=11)
    out = rep.turn_updates(st)
    assert out["npcs"]["Brenna"]["relationship"] == 8  # -2 uma vez
    assert any("dívida" in n["text"] for n in out["reputation_notices"])
    again = rep.turn_updates(_state(out["npcs"]["Brenna"], day=12, turn=8))
    assert "npcs" not in again


def test_pagar_divida_debita_com_clamp_gold():
    npc = _npc(rel=10, favors={"debt": {"amount": 50, "due_day": 10, "overdue_applied": False}})
    ok = rep.pay_debt(_state(npc, gold=70), "Brenna", npc)
    assert ok["ok"] and ok["player"]["gold"] == 20 and ok["npc"]["favors"]["debt"] is None
    poor = rep.pay_debt(_state(npc, gold=10), "Brenna", npc)
    assert not poor["ok"] and poor["code"] == "insufficient_gold"
    assert not rep.pay_debt(_state(_npc()), "Brenna", _npc())["ok"]


def test_interceder_reduz_proximo_delta_negativo():
    npc = _npc(rel=8, faction_id="legiao_ferro")
    assert rep.favor_decision(_state(npc), npc, "interceder")["ok"]
    patch = rep.apply_favor(_state(npc), "Brenna", npc, "interceder")
    st = _state(patch["npc"], factions=[{"id": "legiao_ferro", "name": "L", "reputation": 0}])
    assert rep.intercession_available(st, "legiao_ferro")
    factions, npcs, proposal, applied = rep._apply_faction(
        st, st["factions"], st["npcs"], "legiao_ferro", -12, "d1"
    )
    assert applied == -6 and factions[0]["reputation"] == -6
    assert not rep.intercession_available({**st, "npcs": npcs}, "legiao_ferro")
    _f, _n, _p, second = rep._apply_faction(
        st, factions, npcs, "legiao_ferro", -12, "d2"
    )
    assert second == -12  # consumida


def test_cooldown_favor_3_dias():
    npc = _npc(rel=8, favors={"last_day": 2})
    assert rep.favor_decision(_state(npc, day=3), npc, "esconder")["code"] == "cooldown"
    assert rep.favor_decision(_state(npc, day=5), npc, "esconder")["ok"]


def test_favor_recusado_por_raca():
    npc = _npc(rel=2, race_id="race_elfos")
    st = _state(npc)
    st["player"]["race"] = "Anão da Fuligem"
    assert rep.favor_decision(st, npc, "esconder")["code"] == "refuses"


def test_favor_exige_persuasao_do_traco():
    npc = _npc(rel=9, traits=["desconfiado"])  # persuasao +3 => exige 10
    assert rep.favor_decision(_state(npc), npc, "esconder")["code"] == "too_cold"
    assert rep.favor_decision(_state(_npc(rel=10, traits=["desconfiado"])), _npc(rel=10, traits=["desconfiado"]), "esconder")["ok"]


def test_guard_fallbackllm_router_e_npc(monkeypatch):
    # intenção ausente/obsoleta => conversa normal, sem efeito
    npc = _npc()
    st = _state(npc, social_intent={"approach": "intimidar", "favor_kind": None, "turn": 1})
    assert st["social_intent"]["turn"] != st["world"]["turn_count"]
    # FallbackLLM no router devolve AIMessage => rota STORY sem social_intent
    from langchain_core.messages import AIMessage, HumanMessage

    import agents.router as router

    class _Fallback:
        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, _m):
            return AIMessage(content="erro")

    monkeypatch.setattr(router, "get_llm", lambda *a, **k: _Fallback())
    monkeypatch.setattr(router, "_jev_pending", lambda *a, **k: None, raising=False)
    state = {**st, "messages": [HumanMessage(content="eu ameaço Brenna")], "next": "x"}
    out = router._classify(
        state, state["messages"], "eu ameaço Brenna", state["world"], "Nova Arcádia",
        lambda p: p, False,
    )  # fmt: skip
    assert "social_intent" not in out
    assert out["next"] == "storyteller"


@pytest.mark.parametrize("approach", ["intimidar", "sondar", "pedir_favor", "pagar_divida"])
def test_resolve_social_nunca_levanta_em_npc_vazio(approach):
    social, row, _e, _n = _resolve_social(_state(), "Brenna", _npc(), {"approach": approach})
    assert isinstance(social, dict) and isinstance(row, dict)
