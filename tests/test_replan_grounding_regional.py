from agents import campaign_manager as cm


def _plan(location: str, statuses=("pending", "pending")) -> dict:
    return {
        "location": location,
        "beats": [
            {"description": f"beat {i}", "status": status}
            for i, status in enumerate(statuses)
        ],
        "climax": "clímax",
        "current_step": 0,
        "last_planned_turn": 1,
        "arc_title": "Arco",
    }


def test_troca_de_regiao_replaneja_mesmo_com_todos_beats_pendentes():
    state = {
        "world": {"current_location": "Brekmar", "turn_count": 2},
        "campaign_plan": _plan("Nova Arcádia"),
    }
    assert cm._should_replan(state) is True


def test_movimento_intrarregional_preserva_plano():
    state = {
        "world": {"current_location": "Anel Dourado", "turn_count": 2},
        "campaign_plan": _plan("Nova Arcádia"),
    }
    assert cm._should_replan(state) is False


def test_build_plan_ancora_local_atual_mesmo_se_llm_inventar_outro(monkeypatch):
    response = cm.CampaignPlanModel(
        location="Nova Arcádia",
        beats=["Investigue o porto", "Siga o rastro", "Enfrente a ameaça"],
        climax="Revele o perigo",
        arc_title="Sombras do Cais",
    )

    class _LLM:
        def with_structured_output(self, _model):
            return self

        def invoke(self, _messages):
            return response

    monkeypatch.setattr(cm, "get_llm", lambda *a, **k: _LLM())
    monkeypatch.setattr(cm, "build_context_pack", lambda *a, **k: type(
        "Pack", (), {"lore_block": "", "world_state_block": ""})())
    plan = cm._build_plan({
        "world": {"current_location": "Brekmar", "turn_count": 3},
        "messages": [],
        "campaign_plan": {},
    })
    assert plan["location"] == "Brekmar"
