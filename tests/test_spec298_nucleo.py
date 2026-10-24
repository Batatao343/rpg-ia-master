def test_storyteller_new_npc_ignores_llm_initial_relationship(monkeypatch):
    """Smoke real 24/10: NPC introduzido pelo narrador herdava `initial_relationship`
    do LLM fora de 0..10. A relação inicial é Python (R8, faixa 2..8)."""
    import agents.storyteller as stt

    monkeypatch.setattr(
        stt,
        "generate_new_npc",
        lambda *a, **k: {"name": "Pregador", "role": "pregador", "initial_relationship": -7},
    )
    out = stt._with_new_npc(
        {},
        "Pregador",
        "Nova Arcádia",
        "",
        home_id="nova_arcadia",
        state={"world": {"current_location_id": "nova_arcadia"}, "player": {}},
    )
    npc = next(iter(out.values()))
    assert 2 <= npc["relationship"] <= 8
    assert npc["relationship_basis"]
