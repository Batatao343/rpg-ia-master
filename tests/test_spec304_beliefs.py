"""SPEC-304 Etapa 6: crença do jogador e não-onisciência (R20-R24)."""

from __future__ import annotations

import ast
import json
import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient

from services import context_builder as cb
from services import dossiers, npc_world
from services import event_processor as ep
from services import world_perception as wperc
from tests.spec304_helpers import (
    BRUNNA,
    BRUNNA_ID,
    known_npc,
    setup_env,
    step,
    waiting_state,
)

ODRIN = "npc_mv_odrin_calcario"
KILL_ID = "ev-kill-offscreen-1"
DEATH_PLACE = "Saídas Baixas"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")


def _dead_state(*, belief: bool = False) -> dict:
    """Odrin morreu fora de cena; o jogador (em Nova Arcádia) ainda NÃO soube."""
    st = waiting_state()
    st["party"], st["companion_souls"] = [], {}
    st["world"] = {**st["world"], "current_location": "Nova Arcádia", "visited": ["nova_arcadia"]}
    st["npcs"] = {
        "Odrin Calcário": known_npc(
            ODRIN,
            "Odrin Calcário",
            home_location_id="nova_arcadia",  # a morte foi em OUTRO lugar (Saidas Baixas)
            status="morto",
            location="Nova Arcádia",  # onde o jogador o viu pela ultima vez
            in_scene=False,
            knowledge_source="met",
            created_turn=1,
            last_seen_turn=2,
            role="mediador",
        )
    }
    st["event_log"] = [
        {
            "event_id": KILL_ID,
            "type": "npc_killed",
            "actor_id": "world",
            "target_id": ODRIN,
            "turn": 5,
            "source": "engine",
            "payload": {
                "offscreen": True,
                "peril_id": "p1",
                "location_id": "ma_saidas_baixas",
                "cause": "emboscada",
                "fate": "morto",
            },
        }
    ]
    st["world_projection"] = {"entities": {ODRIN: {"alive": False}}}
    st["npc_sim"] = {
        "version": 1,
        "roster": [ODRIN],
        "perils": [],
        "npcs": {
            ODRIN: {
                "dead": True,
                "fate": "morto",
                "fate_event_id": KILL_ID,
                "pos": {"location_id": "ma_saidas_baixas", "since_day": 3},
            }
        },
    }
    st["npc_beliefs"] = (
        {
            ODRIN: {
                "status_known": "morto",
                "location_known": "ma_saidas_baixas",
                "source_event_id": KILL_ID,
                "channel": "rumor",
                "as_of_day": 6,
            }
        }
        if belief
        else {}
    )
    return st


def _item(kind: str, tpl: str, npc: str = ODRIN, **kw) -> dict:
    return {
        "item_id": f"i-{tpl}",
        "day": 3,
        "kind": kind,
        "region_id": "montanhas_afiadas",
        "location_id": "ma_saidas_baixas",
        "template_id": tpl,
        "params": {"npc_id": npc, **kw.pop("params", {})},
        "subject_id": kw.pop("subject_id", KILL_ID),
        **kw,
    }


def test_belief_from_perceived_item_only():
    st = _dead_state()
    beliefs, learned = npc_world.on_perceived(st, [])
    assert beliefs == {} and learned == []  # nada percebido -> nada se sabe
    item = _item("npc_perigo", "npc_perigo.rumor", subject_id="warn-1")
    beliefs, learned = npc_world.on_perceived(st, [item])
    b = beliefs[ODRIN]
    assert b["status_known"] == "em_perigo" and b["channel"] == "rumor"
    assert b["location_known"] == "ma_saidas_baixas" and b["source_event_id"] == "warn-1"
    assert learned == []
    died = _item("npc_destino", "npc_destino.morto")
    beliefs, learned = npc_world.on_perceived({**st, "npc_beliefs": beliefs}, [died])
    assert (
        beliefs[ODRIN]["status_known"] == "morto" and beliefs[ODRIN]["source_event_id"] == KILL_ID
    )
    assert [e["type"] for e in learned] == ["npc_fate_learned"] and learned[0]["source"] == "engine"
    assert (
        learned[0]["payload"]["fate"] == "morto"
        and learned[0]["payload"]["source_event_id"] == KILL_ID
    )
    assert npc_world.record_beliefs(st, [died])[ODRIN]["status_known"] == "morto"


def test_belief_on_meeting_in_person():
    st = _dead_state()
    st["npcs"]["Odrin Calcário"].update(status="", in_scene=True)
    st["world_projection"] = {}
    st["npc_sim"]["npcs"][ODRIN] = {
        "pos": {"location_id": "nova_arcadia", "since_day": 3},
        "archetype": "sedentario",
    }
    beliefs, _ = npc_world.on_perceived(st, [])
    b = beliefs[ODRIN]
    assert b["channel"] == "testemunho" and b["location_known"] == "nova_arcadia"
    assert b["status_known"] == ""


def test_api_npc_status_from_belief_not_truth():
    import api
    from services.npc_layers import visible_npc_view

    st = _dead_state()
    view = visible_npc_view(st["npcs"], st)[0]
    assert view["status"] == "" and view["location"] == "Nova Arcádia"  # a verdade nao vaza
    assert api._npcs_block(st["npcs"], st)[0]["status"] == ""
    st2 = _dead_state(belief=True)
    assert visible_npc_view(st2["npcs"], st2)[0]["status"] == "morto"
    # sem estado (legado): comportamento anterior
    assert visible_npc_view(st["npcs"])[0]["status"] == "morto"


def _dossier(state: dict) -> dict:
    entry = {"name": "Odrin Calcário", "notes": [], "knowledge": {}, "role": "mediador"}
    return dossiers.npc_dossier(entry, state, dossiers._npc_index(state))


def test_dossier_status_and_encounters_filtered():
    hidden = _dossier(_dead_state())
    assert hidden["status"] == ""
    assert "morreu" not in json.dumps(hidden, ensure_ascii=False)
    shown = _dossier(_dead_state(belief=True))
    assert shown["status"] == "morto"
    assert any(e["outcome"] == "morreu" for e in shown["encounters"])


def test_context_builder_skips_unperceived_offscreen_events():
    def facts(state):
        return " ".join(
            f.text
            for f in cb.collect_dynamic_facts(
                state, purpose="story", query="Odrin", current_loc="nova_arcadia", scene_entities=[]
            )
        )

    assert "foi morto" not in facts(_dead_state())
    assert "foi morto" in facts(_dead_state(belief=True))
    # outros tipos de evento continuam entrando
    st = _dead_state()
    st["event_log"].append(
        {"event_id": "e-q", "type": "quest_completed", "target_id": "q", "turn": 5, "payload": {}}
    )
    assert "Missão concluída" in facts(st)


def test_chronicle_milestone_only_on_fate_learned():
    st = _dead_state()
    st["event_log"] = []
    st["pending_world_events"] = [
        {
            "event_id": KILL_ID,
            "type": "npc_killed",
            "actor_id": "world",
            "target_id": ODRIN,
            "source": "engine",
            "payload": {"offscreen": True, "location_id": "ma_saidas_baixas", "fate": "morto"},
        }
    ]
    st["world_projection"] = {}
    out = ep.process_pending_events(st)
    assert not out.get("chronicle")  # aplicada, mas NAO entra na cronica
    st.update(out)
    st["pending_world_events"] = [
        {
            "event_id": "learn-1",
            "type": "npc_fate_learned",
            "actor_id": "world",
            "target_id": ODRIN,
            "source": "engine",
            "payload": {
                "fate": "morto",
                "location_id": "ma_saidas_baixas",
                "source_event_id": KILL_ID,
                "name": "Odrin Calcário",
            },
        }
    ]
    out2 = ep.process_pending_events(st)
    text = " ".join(c["text"] for ch in out2["chronicle"] for c in ch["entries"])
    assert "Chegou a notícia: Odrin Calcário morreu em Saídas Baixas." in text


def _api_text(st: dict) -> tuple[str, str, str]:
    import api
    import persistence

    st = {**st, "game_id": str(uuid.uuid4())}
    st.setdefault("player", {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano"})
    st["chronicle"] = []
    st["narrative_summary"] = ""
    st["factions"], st["faction_intel"] = [], {}
    assert persistence.save_game_state(st)
    client = TestClient(api.app)
    state_json = client.get("/game/state", params={"game_id": st["game_id"]})
    dossier_json = client.get("/game/codex/dossiers", params={"game_id": st["game_id"]})
    assert state_json.status_code == 200 and dossier_json.status_code == 200
    npcs = json.dumps(
        [n for n in state_json.json().get("npcs", []) if "Odrin" in str(n.get("name"))],
        ensure_ascii=False,
    )
    dossier = json.dumps(
        [
            n
            for n in dossier_json.json().get("npcs", dossier_json.json().get("characters", []))
            if "Odrin" in str(n.get("title") or n.get("name"))
        ],
        ensure_ascii=False,
    )
    ctx = " ".join(
        f.text
        for f in cb.collect_dynamic_facts(
            st, purpose="story", query="Odrin", current_loc="nova_arcadia", scene_entities=[]
        )
        if "odrin" in f.text.lower()  # o lore da regiao cita o lugar sem relacao com a morte
    )
    return npcs, dossier, ctx


def test_oracle_no_death_leak_anywhere():
    npcs, dossier, ctx = _api_text(_dead_state())
    assert npcs and "Odrin" in npcs, "o NPC conhecido deve aparecer na API"
    blob = (npcs + dossier + ctx).lower()
    for needle in ("morto", "morreu", "tombou", "saídas baixas", "ma_saidas_baixas"):
        assert needle not in blob, needle
    # controle: depois de PERCEBER, a morte aparece
    npcs2, dossier2, ctx2 = _api_text(_dead_state(belief=True))
    assert "morto" in npcs2.lower() and "foi morto" in ctx2


def test_unknown_npc_never_named_in_templates():
    st = waiting_state()
    st["party"], st["npcs"] = [], {}
    tpls = [t for t in wperc._templates()["templates"] if t.startswith("npc_")]
    assert len(tpls) == 10
    for tid in tpls:
        text = wperc.render(
            st,
            {
                "template_id": tid,
                "params": {
                    "npc_id": BRUNNA_ID,
                    "faccao": "ultimos_anoes_reino",
                    "destino": "brekmar",
                },
                "region_id": "montanhas_afiadas",
                "location_id": "ma_saidas_baixas",
            },
        )
        assert text and "Brunna" not in text and "Ponte-Alta" not in text, (tid, text)
    # conhecida -> nomeia
    st["npcs"] = {BRUNNA: known_npc(BRUNNA_ID, BRUNNA)}
    known = wperc.render(
        st,
        {
            "template_id": "npc_destino.morto",
            "params": {"npc_id": BRUNNA_ID},
            "region_id": "x",
            "location_id": "ma_saidas_baixas",
        },
    )
    assert "Brunna Ponte-Alta" in known
    # lider desconhecido -> rotulo, nunca o nome
    lead = wperc.render(
        {**st, "npcs": {}},
        {
            "template_id": "npc_perigo.rumor",
            "params": {"npc_id": "npc_comandante_thrace"},
            "region_id": "x",
            "location_id": "ma_saidas_baixas",
        },
    )
    assert "Thrace" not in lead and "o líder de" in lead


def test_unknown_faction_label_in_defection_item():
    st = waiting_state()
    item = {
        "template_id": "npc_lado.mudou",
        "params": {"npc_id": "npc_mv_jax_corda_seca", "faccao": "legiao_ferro"},
        "region_id": "brekmar",
        "location_id": "brekmar",
    }
    assert "Legião de Ferro" not in wperc.render(st, item)
    st["faction_intel"] = {"legiao_ferro": {"known": True}}
    assert "Legião de Ferro" in wperc.render(st, item)


def test_zero_new_llm_calls(monkeypatch):
    calls: list[str] = []
    import llm_setup

    real = llm_setup.get_llm
    monkeypatch.setattr(llm_setup, "get_llm", lambda *a, **k: calls.append("llm") or real(*a, **k))
    st = waiting_state()
    for d in range(2, 45):
        step(st, d - 1, d)
    assert st["npc_sim"]["roster"] and calls == []  # simular NPCs nao chama LLM
    root = pathlib.Path(__file__).resolve().parents[1] / "services"
    for name in ("npc_world.py", "npc_perils.py"):
        src = (root / name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
        }
        assert not names & {"get_llm", "with_structured_output", "invoke"}, name


def test_narrator_name_check_accepts_perceived_npc_names_only(monkeypatch):
    from agents import world_simulator as ws

    st = {
        "npcs": {
            "Zed": known_npc("npc_zed", "Zed"),
            "Oculto Forte": known_npc("npc_o", "Oculto Forte", known_by_player=False),
        },
        "factions": [],
        "faction_intel": {},
    }
    assert "Oculto Forte" not in ws._allowed_names(st) and "Zed" in ws._allowed_names(st)
    monkeypatch.setenv("RPG_NPC_WORLD", "off")
    assert "Oculto Forte" in ws._allowed_names(st)  # comportamento anterior preservado
