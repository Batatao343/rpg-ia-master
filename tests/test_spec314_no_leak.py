"""SPEC-314 Etapa 4 — não-vazamento no prompt inteiro (R15, R19, R20)."""

from __future__ import annotations

import re

import pytest

import agents.npc as npc
import agents.storyteller as stt
import gamedata
import services.context_builder as cb
from services import npc_self as ns
from tests.spec310_helpers import HERE, sergeant
from tests.test_ambient_consumers import _Spy, _story_state
from tests.test_spec310_npc_prompt import _state

SECRETAS = ("mao_sombria", "filhos_chama_azul", "druidas_renegados", "cultistas_destilacao")
RIVAIS_DA_LEGIAO = {"filhos_chama_azul", "mao_sombria"}
REL = {"neutro": 5, "leal": 10}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    monkeypatch.delenv("RPG_NPC_SELF", raising=False)


def _fac(fid: str) -> dict:
    return next(f for f in gamedata.seed_factions() if f["id"] == fid)


def _codex_body(fid: str) -> str:
    text = open(f"data/codex/factions/{fid}.md", encoding="utf-8").read()
    return text.split("---", 2)[2].strip()


def _prompt(monkeypatch, state: dict) -> str:
    """Prompt inteiro do npc_actor; o leitor de lore devolve a página REAL do Codex (via exclude_ids)."""

    def fake_rag(query, index_name="lore", max_visibility="public", exclude_ids=frozenset(), **_k):
        pages = [fid for fid in SECRETAS if fid not in exclude_ids]
        return "\n---\n".join(_codex_body(fid) for fid in pages)

    spy = _Spy()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    monkeypatch.setattr(cb, "query_rag", fake_rag)
    monkeypatch.setattr(cb, "RAG_AVAILABLE", True)
    npc.npc_actor_node(state)
    return spy.prompts[0]


@pytest.mark.parametrize("fid", SECRETAS)
@pytest.mark.parametrize("intel", ["ausente", "known", "goal"])
@pytest.mark.parametrize("tier", ["neutro", "leal"])
def test_prompt_inteiro_por_faccao_secreta(monkeypatch, fid, intel, tier):
    st = _state(sergeant(relationship=REL[tier]))
    st["faction_intel"] = {
        "ausente": {},
        "known": {fid: {"known": True}},
        "goal": {fid: {"known": True, "knows_goal": True}},
    }[intel]
    p = _prompt(monkeypatch, st)
    f = _fac(fid)
    goal_ok = intel == "goal" or (
        intel == "known" and tier == "leal" and fid in RIVAIS_DA_LEGIAO
    )  # R2/D2
    assert (f["goal"] in p) is goal_ok
    # R1 vale para o bloco de facções (arestas do grafo e o menu de ganchos da 313 são follow-up)
    bloco = re.search(r"<FACÇÕES_DO_MUNDO>.*?</FACÇÕES_DO_MUNDO>", p, flags=re.S).group(0)
    assert (f["name"] in bloco) is (intel != "ausente")
    assert (_codex_body(fid)[:80] in p) is (intel == "goal")  # R13


def test_caso_thrace(monkeypatch):
    thrace = sergeant(
        id="npc_comandante_thrace", name="Comandante Thrace", role="Comandante", relationship=5
    )
    st = _state(thrace, active_npc_name="Thrace", npcs={"Thrace": thrace})
    st["faction_intel"] = {"filhos_chama_azul": {"known": True, "knows_goal": False}}
    p = _prompt(monkeypatch, st)
    assert "Os Filhos da Chama Azul" in p
    assert "Chama Azul (Nova Arcádia) · plano: você não sabe" in p
    assert "Palácio de Obsidiana" not in p and "Libertar Malagor" not in p


def test_identity_leal_coerente():
    row = sergeant(id="npc_pardal", faction_id="mao_sombria", relationship=10)
    st = _state(row)
    st["faction_intel"] = {}
    lines = ns._identity_lines(st, "Ruiva", row)
    assert (
        lines == ["Você serve em segredo a A Mão Sombria; só admita a quem confia de verdade."]
        or "só admita a quem confia de verdade" in lines[0]
    )
    row5 = {**row, "relationship": 5}
    assert "não pode ser nomeada" in ns._identity_lines(st, "Ruiva", row5)[0]


def test_storyteller_sem_goal(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    st = _story_state({"current_location_id": HERE, "current_location": "Anel de Ferro"})
    st["factions"] = gamedata.seed_factions()
    st["faction_intel"] = {f: {"known": True} for f in SECRETAS}
    stt.storyteller_node(st)
    prompt = spy.prompts[0]
    for f in gamedata.seed_factions():
        assert f["goal"] not in prompt
    assert not re.search(r"Libertar Malagor", prompt)
