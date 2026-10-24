"""SPEC-305 Etapa 3: so nasce quest do que o jogador viu ou ouviu."""

from __future__ import annotations

import ast
import pathlib

import pytest

from services import quest_log as ql
from services import world_quests as wq
from tests.spec305_helpers import add_crisis, base_state, crisis_item

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_unperceived_crisis_creates_no_quest():
    state = base_state()
    add_crisis(state)
    assert wq.offer_from_perceived(state, [], 17)[1] == []
    assert wq.offer_from_heard(state, 17)[1] == []


def test_testemunho_creates_quest_with_heard_via():
    state = base_state()
    add_crisis(state)
    _q, created = wq.offer_from_perceived(state, [crisis_item()], 17)
    q = created[0]
    assert q["world_kind"] == "conter_praga" and q["deadline_day"] == 23
    assert q["heard_via"] == {"channel": "testemunho", "event_id": "ev-open-1", "day": 17}
    assert q["location_id"] == "brekmar" and q["status"] == "active"


def test_cartaz_only_in_cidade_or_vila():
    def item_for(region: str, loc: str) -> dict:
        return crisis_item(
            kind="praga",
            region=region,
            loc=loc,
            tpl="aviso.surto",
            item_kind="aviso",
            subject="ev-w",
        )

    # cidade (nova_arcadia): aviso regional da propria regiao vira cartaz
    in_town = base_state(loc="na_anel_dourado")
    add_crisis(in_town, region="nova_arcadia", loc="nova_arcadia", start=None, warned=16)
    _q, created = wq.offer_from_perceived(in_town, [item_for("nova_arcadia", "nova_arcadia")], 17)
    assert created and created[0]["heard_via"]["channel"] == "cartaz"
    # fora de cidade/vila (brekmar: porto/sem_lei): o aviso regional nao vira quest
    out = base_state(loc="bk_docas_velhas")
    add_crisis(out, region="brekmar", loc="brekmar", start=None, warned=16)
    assert wq.offer_from_perceived(out, [item_for("brekmar", "brekmar")], 17)[1] == []


def test_npc_channel_uses_npc_name_as_origin(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    state = base_state()
    add_crisis(state)
    state["event_log"] = [
        {
            "event_id": "ev-open-1",
            "type": "location_state_changed",
            "payload": {"crisis_id": "crise-1"},
        }
    ]
    state["location_heard"] = {"brekmar": ["ev-open-1"]}
    state["npcs"] = {"Marta": {"name": "Marta", "in_scene": True}}
    state["active_npc_name"] = "Marta"
    _q, created = wq.offer_from_heard(state, 17)
    assert created[0]["origin_name"] == "Marta"
    assert created[0]["heard_via"]["channel"] == "npc"
    assert "Marta" in created[0]["description"]


def test_rumor_requires_location_heard_and_215_on(monkeypatch):
    state = base_state()
    add_crisis(state)
    state["event_log"] = [
        {
            "event_id": "ev-open-1",
            "type": "location_state_changed",
            "payload": {"crisis_id": "crise-1"},
        }
    ]
    state["location_heard"] = {"brekmar": ["ev-open-1"]}
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    assert wq.offer_from_heard(state, 17)[1] == []  # test_rumor_off_without_215
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    created = wq.offer_from_heard(state, 17)[1]
    assert created and created[0]["heard_via"]["channel"] == "rumor"
    state["location_heard"] = {}
    assert wq.offer_from_heard(state, 17)[1] == []


def test_unknown_faction_never_named_in_any_template():
    state = base_state()
    state["factions"] = [{"id": "legiao_ferro", "name": "Legião de Ferro", "region": "Brekmar"}]
    state["faction_intel"] = {}
    cfg = wq._cfg()["kinds"]
    for kind, spec in cfg.items():
        seed = wq.QuestSeed(
            kind=kind,
            world_source_id="s",
            region_id="brekmar",
            location_id="brekmar",
            other_location_id="nova_arcadia",
            deadline_day=30,
            faction_id="legiao_ferro",
            item_id="art_adaga_vidro_dragao",
        )
        for channel in ("testemunho", "cartaz", "npc", "rumor", "mensageiro"):
            out = wq.render_quest_text(state, seed, channel)
            blob = " ".join(out.values())
            assert "Legião de Ferro" not in blob, (kind, channel)
            assert "{" not in blob, (kind, channel)
            assert not any(ch.isdigit() for ch in blob), (kind, channel)
        assert spec["title"]


def test_world_quest_cap_and_ordering():
    state = base_state()
    for i, (kind, region) in enumerate(
        [("praga", "brekmar"), ("fome", "brekmar"), ("guerra", "brekmar"), ("abismo", "brekmar")]
    ):
        add_crisis(state, kind, region, cid=f"c{i}", escalation=20 + i, faction_id="legiao_ferro")
    items = [crisis_item(kind=k, subject=f"ev{k}") for k in ("praga", "fome", "guerra", "abismo")]
    quests, created = wq.offer_from_perceived(state, items, 17)
    assert len(created) == wq.MAX_WORLD_QUESTS_ACTIVE
    assert [q["deadline_day"] for q in created] == [20, 21, 22]  # prazo mais curto primeiro
    assert len(quests) == 3


def test_llm_duplicate_of_world_quest_ignored():
    state = base_state()
    add_crisis(state)
    quests, created = wq.offer_from_perceived(state, [crisis_item()], 17)
    proposal = {
        "title": "Tratar os doentes",
        "description": "Cure os doentes da febre.",
        "location_id": "brekmar",
    }
    out, new = ql.register_proposed_quests(quests, [proposal], turn=5)
    assert new == [] and len(out) == 1
    other = {"title": "Entregar carta", "description": "Leve a carta.", "location_id": "brekmar"}
    assert len(ql.register_proposed_quests(quests, [other], turn=5)[1]) == 1


def test_only_world_quests_module_builds_world_kind():
    """R7: nenhum outro modulo monta dict com `world_kind` (so le/propaga)."""
    allowed = {"services/world_quests.py"}
    offenders = []
    for path in (
        list(ROOT.glob("services/*.py")) + list(ROOT.glob("agents/*.py")) + [ROOT / "api.py"]
    ):
        rel = path.relative_to(ROOT).as_posix()
        if rel in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == "world_kind" for k in node.keys
            ):
                if rel not in ("services/event_processor.py",):  # payload do derivado de alivio
                    offenders.append(rel)
    assert offenders == []


def test_modes(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_QUESTS", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    assert wq.mode() == "off"  # test_requires_world_engine_on
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    assert wq.mode() == "on"
    monkeypatch.setenv("RPG_WORLD_QUESTS", "shadow")
    state = base_state()
    add_crisis(state)
    quests, created = wq.offer_from_perceived(state, [crisis_item()], 17)
    assert quests == [] and created == []  # test_shadow_writes_nothing


@pytest.mark.parametrize("bad", ["", "xx"])
def test_invalid_mode_falls_back_to_default(monkeypatch, bad):
    monkeypatch.setenv("RPG_WORLD_QUESTS", bad)
    assert wq.mode() == "on"
