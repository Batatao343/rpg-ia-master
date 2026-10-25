"""SPEC-317 R8 — combate comum não paga embedding/retrieval de lore."""

from __future__ import annotations

from agents import combat
from services import context_builder, context_sources


def _count_embeddings(monkeypatch) -> list:
    calls: list = []

    def fake_embed(text, **_kw):
        calls.append(text)
        return context_sources.EmbeddedContextQuery(text, None, None, None)

    monkeypatch.setattr(context_sources, "embed_context_query", fake_embed)
    return calls


def test_include_lore_false_makes_zero_embedding_calls(monkeypatch):
    calls = _count_embeddings(monkeypatch)
    state = {"world": {"current_location": "Campo", "danger_level": 1}, "player": {}}
    pack = context_builder.build_context_pack(
        state, "Campo", "combat_narration", token_budget=600, include_lore=False
    )
    assert calls == []
    assert "<ESTADO_ATUAL_DO_MUNDO>" in pack.world_state_block
    assert pack.lore_block == ""


def test_default_still_embeds_once(monkeypatch):
    calls = _count_embeddings(monkeypatch)
    state = {"world": {"current_location": "Campo", "danger_level": 1}, "player": {}}
    context_builder.build_context_pack(state, "Campo", "combat_narration", token_budget=600)
    assert len(calls) == 1


def test_combat_round_makes_zero_embedding_calls(monkeypatch):
    calls = _count_embeddings(monkeypatch)
    state = {"world": {"current_location": "Campo", "danger_level": 1}, "player": {}}
    # Cena comum (sem Elite/Abismo): nenhum pack é montado em _prepare_scene.
    combat._prepare_scene(
        state,
        [{"id": "e1", "categoria": "lacaio"}],
        {"abyss_charge": 0, "class_name": "Devoto do Abismo"},
        [],
    )
    # Narração da rodada: o pack de combate nunca puxa lore.
    context_builder.build_context_pack(
        state, "Campo ataco", "combat_narration", token_budget=1200, include_lore=False
    )
    assert calls == []
