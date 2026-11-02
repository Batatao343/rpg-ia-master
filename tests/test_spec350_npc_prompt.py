"""SPEC-350 Etapa 5 — ficha de trama no prompt do NPC (R22, R23, R26, R28)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.npc as npc
import gamedata
from services import npc_layers
from services import npc_self as ns
from services import plot_threads as pt
from tests.spec310_helpers import HERE, make_state
from tests.test_ambient_consumers import _Spy, _story_state


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    monkeypatch.delenv("RPG_NPC_SELF", raising=False)
    pt.clear_cache()
    yield
    pt.clear_cache()


def _row(npc_id: str, name: str, **over) -> dict:
    row = {
        "id": npc_id,
        "name": name,
        "role": "x",
        "persona": "Seca.",
        "location": "Anel de Lama",
        "faction_id": "",
        "home_location_id": "na_anel_lama",
        "relationship": 5,
        "memory": [],
        "in_scene": True,
    }
    row.update(over)
    return row


def _blocks(row, key="Netta"):
    return ns.npc_self_blocks(make_state(npcs={key: row}), key, row)


def test_canonical_npc_gets_motives_from_sheet():
    b = _blocks(_row("npc_velha_netta", "Velha Netta"))
    lines = b.motivacoes.splitlines()
    assert lines[1].startswith("Você deseja: que nenhum marcado")
    assert lines[2].startswith("Você teme: o dia em que o Doutor")
    assert lines[3].startswith("Há um assunto que você evita: o que ela dá aos marcados")
    assert lines[4].startswith("Seu jeito: áspera e prática")
    assert "«Senta. Não pergunta. Paga depois, se viver.»" in lines[4]


def test_avoided_topic_line_present_for_every_sheet():
    for nid, sheet in pt.catalog().cast.items():
        blk = _blocks(_row(nid, nid), nid)
        assert f"Há um assunto que você evita: {sheet.segredo_topico}." in blk.motivacoes, nid
        assert "Você deseja:" in blk.motivacoes and "Você teme:" in blk.motivacoes, nid


def test_seed_motives_win_over_sheet():
    seeded = {"desire_id": "des_juntar_ouro", "fear_id": "fear_escuro"}
    b = _blocks(_row("npc_velha_netta", "Velha Netta", seed_motives=seeded))
    assert "que nenhum marcado" not in b.motivacoes


def test_sheet_resolved_by_name_when_id_is_generated():
    b = _blocks(_row("velha_netta", "Velha Netta"))
    assert "Você deseja: que nenhum marcado" in b.motivacoes


def test_stake_line_after_identity_and_cut_by_budget():
    b = _blocks(_row("npc_velha_netta", "Velha Netta"))
    lines = b.sobre_voce.splitlines()
    stake = next(i for i, ln in enumerate(lines) if ln.startswith("O que está em jogo para você:"))
    assert stake >= 1 and "outra trama" not in b.sobre_voce
    for nid in pt.catalog().cast:
        row = _row(nid, nid)
        blk = _blocks(row, nid)
        assert len(blk.sobre_voce) <= ns.SELF_MAX_CHARS
        assert len(blk.motivacoes) <= ns.MOTIVES_MAX_CHARS
        assert len(blk.text()) <= ns.TOTAL_MAX_CHARS


def test_only_first_thread_stake_and_no_pergunta():
    sheet = pt.cast_sheet("npc_comandante_thrace")
    assert len(sheet.threads) >= 2
    b = _blocks(_row("npc_comandante_thrace", "Comandante Thrace"), "Thrace")
    assert b.sobre_voce.count("O que está em jogo") <= 1
    for thr in pt.catalog().threads:
        assert thr.pergunta not in b.text()


def test_secret_never_literal_in_prompt():
    import re

    for nid in ("npc_tr_dalva_torneira", "npc_tr_ludovina_agulha", "npc_mv_mara_do_setimo_sino"):
        sheet = pt.cast_sheet(nid)
        path = pt._public_docs  # noqa: F841 (garante o import)
        secret = open(
            f"data/codex/npcs/segredos/{sheet.segredo_doc_id}.md", encoding="utf-8"
        ).read()
        body = secret.split("Segredo:", 1)[1].strip()
        text = _blocks(_row(nid, nid), nid).text()
        for sentence in re.split(r"(?<=[.!?])\s+", body):
            assert sentence not in text


def _prompt(monkeypatch, state):
    spy = _Spy()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    npc.npc_actor_node(state)
    return spy


def _actor_state():
    st = _story_state({"current_location_id": HERE, "current_location": "Anel de Ferro"})
    st.update(
        factions=gamedata.seed_factions(),
        active_npc_name="Velha Netta",
        npcs={"Velha Netta": _row("npc_velha_netta", "Velha Netta")},
        messages=[HumanMessage(content="Quem é você?")],
    )
    return st


def test_flag_off_prompt_byte_identical(monkeypatch):
    calls = []
    real = pt.sheet_for_row
    monkeypatch.setattr(pt, "sheet_for_row", lambda *a, **k: calls.append(1) or real(*a, **k))
    monkeypatch.setenv("RPG_PLOT_THREADS", "off")
    off = _prompt(monkeypatch, _actor_state()).prompts[0]
    assert calls == []
    monkeypatch.setattr(pt, "sheet_for_row", lambda *a, **k: None)
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    on_without_sheet = _prompt(monkeypatch, _actor_state()).prompts[0]
    assert off == on_without_sheet
    assert "Você deseja" not in off and "em jogo para você" not in off


def test_no_extra_llm_invokes_and_prompt_has_sheet(monkeypatch):
    monkeypatch.setenv("RPG_PLOT_THREADS", "off")
    n_off = len(_prompt(monkeypatch, _actor_state()).prompts)
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    spy = _prompt(monkeypatch, _actor_state())
    assert len(spy.prompts) == n_off
    assert "Você deseja: que nenhum marcado" in spy.prompts[0]


def test_state_payload_has_no_sheet_fields():
    row = _row("npc_velha_netta", "Velha Netta")
    sheet = pt.cast_sheet("npc_velha_netta")
    blob = str(npc_layers.visible_npc_view({"Velha Netta": row}, make_state()))
    for text in (sheet.desejo, sheet.medo, sheet.segredo_topico, sheet.voz.fala):
        assert text not in blob
