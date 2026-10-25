"""SPEC-310 Etapa 6 — injeção, orçamento, kill switch e telemetria no npc_actor (spy no prompt)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.npc as npc
import gamedata
from services import npc_self as ns
from tests.spec310_helpers import HERE, HOME, sergeant, sim_entry
from tests.test_ambient_consumers import _Spy, _story_state

SEEDED = {
    "desire_id": "des_juntar_ouro",
    "fear_id": "fear_escuro",
    "secret_id": "sec_desertor",
    "contradiction_id": "con_generoso_sovina",
    "mannerism_id": "man_bate_o_dedo",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    monkeypatch.delenv("RPG_NPC_SELF", raising=False)


def _state(row: dict | None = None, **over) -> dict:
    st = _story_state({"current_location_id": HERE, "current_location": "Anel de Ferro"})
    st.update(
        factions=gamedata.seed_factions(),
        active_npc_name="Ruiva",
        npcs={"Ruiva": row if row is not None else sergeant(seed_motives=SEEDED)},
        npc_sim=sim_entry(location_id=HERE, since_day=1, return_day=4),
        messages=[HumanMessage(content="Quem é você?")],
    )
    st.update(over)
    return st


def _prompt(monkeypatch, state: dict) -> str:
    spy = _Spy()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    npc.npc_actor_node(state)
    return spy.prompts[0]


def test_prompt_tem_blocos_na_ordem_apos_role(monkeypatch):
    p = _prompt(monkeypatch, _state())
    order = [p.index(t) for t in ("</ROLE>", "<SOBRE_VOCE>", "<MOTIVACOES_INTERNAS>", "<ATITUDE>")]
    assert order == sorted(order)
    assert "Anel de Lama" in p and "Você deseja:" in p and "seu passado de armas" in p
    assert "desertou" not in p


def test_bloco_vazio_sem_tag(monkeypatch):
    row = {
        "id": "npc_x",
        "name": "Ruiva",
        "role": "Ferreiro",
        "persona": "Seca.",
        "location": "Anel de Ferro",
        "relationship": 5,
        "memory": [],
    }
    monkeypatch.setattr(ns, "agenda_lines", lambda *a, **k: [])
    monkeypatch.setattr(ns, "place_lines", lambda *a, **k: [])
    p = _prompt(monkeypatch, _state(row, npc_sim={}))
    assert "<MOTIVACOES_INTERNAS>" not in p and "<SOBRE_VOCE>" not in p
    assert "</ROLE>\n    <ATITUDE>" in p  # nenhuma linha em branco extra


def test_orcamento_corta_por_prioridade(monkeypatch):
    st = _state()
    st["world_sim"] = {"relation_bands": {"filhos_chama_azul|legiao_ferro": "guerra"}}
    st["faction_intel"] = {"filhos_chama_azul": {"known": True}}
    full = ns.npc_self_blocks(st, "Ruiva", st["npcs"]["Ruiva"])
    assert "guerra" in full.sobre_voce and "Você serve em" in full.sobre_voce
    assert len(full.text()) <= ns.SELF_MAX_CHARS + ns.MOTIVES_MAX_CHARS + ns.KNOWS_MAX_CHARS
    monkeypatch.setattr(ns, "SELF_MAX_CHARS", len(full.sobre_voce) - 5)
    cut = ns.npc_self_blocks(st, "Ruiva", st["npcs"]["Ruiva"])
    assert "guerra" not in cut.sobre_voce  # relação sai antes
    assert "Você serve em" in cut.sobre_voce and "de passagem" in cut.sobre_voce
    assert len(cut.sobre_voce) <= ns.SELF_MAX_CHARS
    monkeypatch.setattr(ns, "MOTIVES_MAX_CHARS", 190)
    tiny = ns.npc_self_blocks(st, "Ruiva", st["npcs"]["Ruiva"]).motivacoes
    assert 0 < len(tiny) <= 190 and "não recite" in tiny


def test_flag_off_prompt_identico(monkeypatch):
    monkeypatch.setenv("RPG_NPC_SELF", "off")
    off = _prompt(monkeypatch, _state())
    monkeypatch.delenv("RPG_NPC_SELF")
    monkeypatch.setattr(npc, "_npc_self_prompt", lambda *a, **k: "")
    removed = _prompt(monkeypatch, _state())
    assert off == removed
    assert "<SOBRE_VOCE>" not in off


def test_excecao_no_modulo_nao_derruba_turno(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("falha")

    calls = []
    monkeypatch.setattr(ns, "agenda_lines", boom)
    monkeypatch.setattr("observability.telemetry.log_fallback", lambda *a, **k: calls.append(a[:2]))
    p = _prompt(monkeypatch, _state())
    assert "<SOBRE_VOCE>" not in p and "<MOTIVACOES_INTERNAS>" not in p
    assert ("npc", "self_block_failed") in calls


def test_telemetria_sem_texto(monkeypatch):
    events = []
    monkeypatch.setattr("observability.telemetry.log_event", lambda *a, **k: events.append((a, k)))
    _prompt(monkeypatch, _state())
    (kw,) = [k for a, k in events if a[:2] == ("npc", "self_block")]
    assert set(kw) <= {"sections", "chars", "truncated", "level"}
    assert isinstance(kw["chars"], int) and kw["chars"] <= 1950
    assert "Ruiva" not in str(kw) and HOME not in str(kw)
