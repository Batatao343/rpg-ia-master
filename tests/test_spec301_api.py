"""SPEC-301 Etapa 8 — API: membership só com rótulos (R22)."""

from __future__ import annotations

import json

import api
from services import dossiers as dz
from services import faction_membership as fm
from services import player_knowledge as pk
from services.dossier_visibility import assert_no_private_fields, leak_view
from tests.spec301_support import joined, make_state

FORBIDDEN = ("merit", "influence", "rival_awareness", "offenses", "cooldown_until_day", "marks")


def _block(state):
    return api._factions_block(
        state["factions"],
        state["faction_intel"],
        5,
        state["event_log"],
        state["world_projection"],
        state=state,
    )


def _member_state(**rec):
    st = joined(make_state(), "legiao_ferro", merit=7, rank_index=1, **rec)
    st["faction_membership"]["legiao_ferro"]["rival_awareness"] = {"filhos_chama_azul": -1}
    for f in st["factions"]:
        if f["id"] == "legiao_ferro":
            f["influence"] = 5
    return st


def test_factions_block_membership_sem_merit_influence():
    out = _block(_member_state())
    raw = json.dumps(out)
    for key in FORBIDDEN:
        assert key not in raw, key
    row = next(f for f in out if f["id"] == "legiao_ferro")
    assert set(row["membership"]) == {
        "status",
        "rank_name",
        "standing_label",
        "perks",
        "active_mission_id",
    }
    assert row["membership"]["rank_name"] == "Legionário"


def test_membership_so_para_faccao_com_vinculo():
    st = _member_state()
    st["faction_intel"]["mao_sombria"] = {"known": True}
    out = _block(st)
    assert "membership" in next(f for f in out if f["id"] == "legiao_ferro")
    assert "membership" not in next(f for f in out if f["id"] == "mao_sombria")
    # sem state (chamadas legadas): bloco idêntico ao de antes
    legacy = api._factions_block(st["factions"], st["faction_intel"], 5)
    assert all("membership" not in f for f in legacy)


def test_standing_label_enum_fechado():
    labels = set()
    for status in (
        "ativo",
        "suspeito",
        "expulso",
        "traidor",
        "ex_membro",
        "dissolvida",
        "rito_pendente",
    ):
        st = _member_state(status=status)
        labels.add(fm.membership_view(st, "legiao_ferro")["standing_label"])
    for idx in (0, 1, 4):
        st = joined(make_state(), "legiao_ferro", rank_index=idx)
        labels.add(fm.membership_view(st, "legiao_ferro")["standing_label"])
    assert labels <= set(fm.STANDING_LABELS)
    assert {"recém-chegado", "visto com bons olhos", "a liderança nota seu trabalho"} <= labels


def test_assert_no_player_leak_continua_verde():
    st = _member_state()
    st["game_id"] = "pytest_leak301"
    st["messages"] = []
    st["narrative_summary"] = ""
    st["chronicle"] = []
    payload = dz.build_dossiers(st)
    assert assert_no_private_fields(payload) == []
    assert pk.assert_no_player_leak(leak_view(payload), st) == []


def test_state_response_nao_vaza_numeros_de_membership():
    st = _member_state()
    blob = json.dumps(_block(st))
    assert '"merit"' not in blob and '"influence"' not in blob
