"""SPEC-298 Etapas 7-8 — visibilidade (sem números), avisos e prompts."""

import api
from services import dossiers as dz
from services import reputation as rep

FORBIDDEN_KEYS = {"relationship", "reputation", "disposition_label", "history"}


def _state(**extra):
    base = {
        "game_id": "pytest_spec298",
        "narrative_summary": "",
        "messages": [],
        "player": {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano", "gold": 5},
        "world": {
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
            "turn_count": 12,
            "visited": ["nova_arcadia"],
        },
        "npcs": {
            "Grum": {
                "id": "npc_grum",
                "name": "Grum",
                "role": "Ferreiro",
                "location": "Nova Arcádia",
                "knowledge_source": "met",
                "known_by_player": True,
                "in_scene": True,
                "relationship": 8,
                "created_turn": 2,
                "last_seen_turn": 9,
                "hidden_traits": [],
                "revealed_traits": [],
                "memory": [],
                "recent_changes": [
                    {"turn": 9, "text": "Grum parece mais à vontade com você."},
                    {"turn": 10, "text": "a"},
                    {"turn": 11, "text": "b"},
                    {"turn": 12, "text": "c"},
                ],
            }
        },
        "factions": [
            {
                "id": "legiao_ferro",
                "name": "Legião de Ferro",
                "reputation": 55,
                "disposition": "aliado",
                "recent_changes": [{"turn": 12, "text": "Legião de Ferro vai lembrar disso."}],
            }
        ],
        "faction_intel": {"legiao_ferro": {"known": True}},
        "bestiary_knowledge": {},
        "event_log": [
            {
                "event_id": "e1",
                "turn": 12,
                "type": "reputation_changed",
                "target_id": "legiao_ferro",
                "payload": {"delta": 4, "new_value": 55},
            }
        ],
        "world_projection": {},
        "memory_facts": [],
        "chronicle": [],
        "reputation_notices": [
            {"kind": "npc", "subject_id": "npc_grum", "text": "Grum não gostou disso.", "turn": 12},
            {"kind": "npc", "subject_id": "npc_grum", "text": "velho", "turn": 3},
        ],
    }
    base.update(extra)
    return base


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            _keys(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, found)
    return found


def test_payloads_sem_relationship_reputation():
    state = _state()
    resp = api.format_response(state)
    payload = resp.model_dump() if hasattr(resp, "model_dump") else resp
    assert not (FORBIDDEN_KEYS & _keys(payload)), FORBIDDEN_KEYS & _keys(payload)
    dossiers = dz.build_dossiers(state)
    assert not (FORBIDDEN_KEYS & _keys(dossiers))
    # rótulos presentes no lugar dos números
    assert payload["npcs"][0]["attitude_label"] == "amistoso"
    assert payload["factions"][0]["standing_label"] == "aliado"


def test_recent_changes_max_3():
    payload = api.format_response(_state())
    changes = payload.npcs[0]["recent_changes"]
    assert len(changes) == 3 and changes[-1]["text"] == "c"


def test_avisos_regras_de_emissao():
    resp = api.format_response(_state())
    texts = [n["text"] for n in resp.reputation_notices]
    assert texts == ["Grum não gostou disso."]  # só os do turno corrente


def test_avisos_passam_por_conceal_for(monkeypatch):
    import services.faction_display as fd

    calls = []
    real = fd.conceal_for
    monkeypatch.setattr(fd, "conceal_for", lambda st, obj: (calls.append(1), real(st, obj))[1])
    api.format_response(_state())
    assert calls


def test_dossie_npc_e_faccao_tem_rotulo():
    dossiers = dz.build_dossiers(_state())
    npc = dossiers["sections"]["npcs"][0]
    assert npc["attitude_label"] == "amistoso" and len(npc["recent_changes"]) == 3
    fac = dossiers["sections"]["factions"]
    if fac:
        assert fac[0]["standing_label"] == "aliado"


# --- Etapa 7: prompts -------------------------------------------------------
def test_prompt_npc_tem_atitude_sem_numero():
    npc = {
        "relationship": 2,
        "relationship_basis": {"race": -2, "origin": 0, "fame": 0, "faction": 0},
    }
    block = rep.attitude_block(_state(), npc)
    assert block.startswith("<ATITUDE>") and "desconfiado" in block
    assert "preconceito" in block
    assert not any(ch.isdigit() for ch in block)


def test_atitude_cita_motivo_raca_quando_aplicavel():
    friendly = rep.attitude_block(_state(), {"relationship": 7, "relationship_basis": {"race": 1}})
    assert "simpatiza com a raça" in friendly
    neutral = rep.attitude_block(_state(), {"relationship": 5, "relationship_basis": {"race": 0}})
    assert "raça" not in neutral


def test_atitude_inclui_resultado_social():
    block = rep.attitude_block(
        _state(), {"relationship": 5}, {"approach": "intimidar", "success": False}
    )
    assert "NÃO se deixa intimidar" in block


def test_prompt_storyteller_fama_so_se_conhecida():
    assert rep.fame_line(_state()) == ""
    state = _state(location_fame={"nova_arcadia": {"renown": 35, "infamy": 12}})
    line = rep.fame_line(state)
    assert "afamado" in line and "malvisto" in line
    assert not any(ch.isdigit() for ch in line)
