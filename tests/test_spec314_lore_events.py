"""SPEC-314 Etapa 3 — lore de fação secreta e nomes em eventos (R13, R14)."""

from __future__ import annotations

from langchain_core.documents import Document

import rag
import services.context_builder as cb
from tests.spec310_helpers import make_state

PLANO = "Sabem que Malagor está contido na armadura do Palácio de Obsidiana"


def _docs():
    return [
        (
            Document(
                page_content=PLANO, metadata={"id": "filhos_chama_azul", "visibility": "public"}
            ),
            0.1,
        ),
        (
            Document(
                page_content="Taverna comum.", metadata={"id": "taverna", "visibility": "public"}
            ),
            0.2,
        ),
        (
            Document(page_content="Mercado.", metadata={"id": "mercado", "visibility": "public"}),
            0.3,
        ),
        (
            Document(page_content="Muralha.", metadata={"id": "muralha", "visibility": "public"}),
            0.4,
        ),
    ]


class _FakeDB:
    def similarity_search_with_score_by_vector(self, vector, k=0, **_k):
        return _docs()[:k]


def test_rag_exclude_ids(monkeypatch):
    monkeypatch.setattr(rag, "_has_faiss_index", lambda p: True)
    monkeypatch.setattr(rag, "_embeddings_for_index", lambda p: object())
    monkeypatch.setattr(rag.FAISS, "load_local", lambda *a, **k: _FakeDB())
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    assert PLANO in rag.query_global_by_vector([0.1], "lore", "public")
    out = rag.query_global_by_vector(
        [0.1], "lore", "public", exclude_ids=frozenset({"filhos_chama_azul"})
    )
    assert PLANO not in out
    assert all(t in out for t in ("Taverna", "Mercado", "Muralha"))  # K=3 reposto após o filtro


def _stub_rag(monkeypatch):
    calls = []

    def fake(query, index_name="lore", max_visibility="public", exclude_ids=frozenset(), **_k):
        calls.append(exclude_ids)
        return "Taverna comum." if "filhos_chama_azul" in exclude_ids else f"Taverna. {PLANO}"

    monkeypatch.setattr(cb, "query_rag", fake)
    monkeypatch.setattr(cb, "RAG_AVAILABLE", True)
    return calls


def test_pack_npc_redige_lore_secreto(monkeypatch):
    calls = _stub_rag(monkeypatch)
    st = make_state()
    for purpose in ("npc", "story", "combat_narration"):
        pack = cb.build_context_pack(st, "Chama Azul", purpose)
        assert PLANO not in pack.lore_block
    st["faction_intel"] = {"filhos_chama_azul": {"known": True, "knows_goal": True}}
    pack = cb.build_context_pack(st, "Chama Azul", "npc")
    assert PLANO in pack.lore_block
    assert all("filhos_chama_azul" not in c for c in calls[-1:])


def test_pack_exceção_membro_da_propria_faccao(monkeypatch):
    _stub_rag(monkeypatch)
    st = make_state(faction_membership={"mao_sombria": {"status": "ativo", "rank": 0}})
    from services import faction_gate as fg

    assert "mao_sombria" not in fg.redacted_lore_ids(st, "mao_sombria")
    assert "mao_sombria" in fg.redacted_lore_ids(st, "")


def test_planning_nao_redige(monkeypatch):
    _stub_rag(monkeypatch)
    pack = cb.build_context_pack(make_state(), "Chama Azul", "planning")
    assert PLANO in pack.lore_block


def test_relacao_com_secreta_desconhecida_mascara_nome():
    ev = {
        "type": "faction_relation_changed",
        "turn": 3,
        "target_id": "filhos_chama_azul",
        "payload": {"other_faction_id": "legiao_ferro", "relation": "guerra"},
    }
    st = make_state()
    txt = cb.render_event(ev, None, st)
    assert "uma facção desconhecida" in txt and "Chama Azul" not in txt and "Legião" in txt
    st["faction_intel"] = {"filhos_chama_azul": {"known": True}}
    assert "Chama Azul" in cb.render_event(ev, None, st)
    assert "Chama Azul" in cb.render_event(ev, None)  # sem state: comportamento antigo
    ctl = {
        "type": "location_control_changed",
        "turn": 3,
        "target_id": "na_anel_ferro",
        "payload": {"new_controller_id": "mao_sombria"},
    }
    assert "uma facção desconhecida" in cb.render_event(ctl, None, make_state())
