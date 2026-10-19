"""SPEC-206 — taxonomia de conhecimento visível ao jogador (offline, zero LLM)."""

from __future__ import annotations

import copy
import json
import os
import uuid
from typing import get_args

import pytest

from services import discovery as disc
from services import memory_provenance as mp
from services import player_knowledge as pk

HIDDEN_LOC = "mon_verme_primordial_das_raizes_do_mundo"  # visibility: hidden no grafo
HIDDEN_NAME = "Verme-Primordial das Raízes do Mundo"
RATO = "enemy_rato_peste_anel_lama"


def _state(**extra):
    base = {
        "game_id": "pytest_spec206",
        "narrative_summary": "",
        "messages": [],
        "player": {"name": "Tester", "class_name": "Devoto do Abismo", "race": "Humano"},
        "world": {
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
            "turn_count": 10,
            "visited": ["nova_arcadia"],
        },
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "bestiary_knowledge": {},
        "event_log": [],
        "world_projection": {},
        "memory_facts": [],
    }
    base.update(extra)
    return base


def _reveal(target, event_id="ev_reveal_1", turn=7):
    return {
        "event_log": [
            {
                "event_id": event_id,
                "type": "secret_revealed",
                "target_id": target,
                "payload": {"detail": "x"},
                "turn": turn,
            }
        ],
        "world_projection": {
            "revealed_facts": {
                event_id: {
                    "entity_id": target,
                    "fact": "Desperta sob a montanha.",
                    "revealed_at_turn": turn,
                    "revealed_by_event": event_id,
                }
            }
        },
    }


def _mem(text, provenance, *, source_id=None, turn=3, entities=("nova_arcadia",)):
    return mp.make_memory_fact(
        text,
        provenance=provenance,
        source_id=source_id,
        source_turn=turn,
        canonical_entity_ids=list(entities),
    )


# ---------------------------------------------------------------------------
# Etapa 1 — derivação pura
# ---------------------------------------------------------------------------

DERIVATION_ROWS = [
    (
        "visited",
        {"id": "nova_arcadia"},
        {},
        ("fact", "confirmed", "canonical_event", "visited:nova_arcadia"),
    ),
    (
        "revealed_fact",
        {"event_id": "e9", "revealed_at_turn": 4},
        {},
        ("fact", "confirmed", "canonical_event", "event:e9"),
    ),
    (
        "bestiary",
        {"id": RATO, "seen": 1, "fought": 1},
        {},
        ("fact", "confirmed", "canonical_event", f"bestiary:{RATO}"),
    ),
    (
        "bestiary",
        {"id": RATO, "seen": 1},
        {},
        ("rumor", "reported", "npc_claim", f"bestiary:{RATO}"),
    ),
    (
        "npc",
        {"name": "Grum", "knowledge_source": "met"},
        {},
        ("fact", "confirmed", "canonical_event", "npc:Grum"),
    ),
    (
        "npc",
        {"name": "Grum", "knowledge_source": "mentioned"},
        {},
        ("rumor", "reported", "npc_claim", "npc:Grum"),
    ),
    (
        "npc",
        {"name": "Grum", "entity_id": "npc_grum", "knowledge_source": "lore"},
        {},
        ("report", "reported", "npc_claim", "npc:npc_grum"),
    ),
    (
        "faction",
        {"id": "legiao_ferro", "known": True},
        {},
        ("report", "reported", "npc_claim", "faction:legiao_ferro"),
    ),
    (
        "faction",
        {"id": "legiao_ferro", "known": True, "knows_goal": True},
        {},
        ("report", "reported", "npc_claim", "faction:legiao_ferro"),
    ),
]


@pytest.mark.parametrize("origin,record,_extra,expected", DERIVATION_ROWS)
def test_derivation_table_is_total(origin, record, _extra, expected):
    stamp = pk.derive_stamp(origin, record, _state())
    assert (
        stamp["knowledge_kind"],
        stamp["certainty"],
        stamp["source_kind"],
        stamp["source_ref"],
    ) == expected
    assert stamp["label"] == pk.KIND_LABEL_PT[stamp["knowledge_kind"]]


@pytest.mark.parametrize(
    "provenance,source_id,text,kind,certainty,source_kind",
    [
        ("canonical_event", "ev1", "A ponte caiu.", "fact", "confirmed", "canonical_event"),
        ("canonical_event", "sem_fonte", "A ponte caiu.", "suspicion", "speculative", "inference"),
        (
            "player_observation",
            None,
            "Vi fumaça ao norte.",
            "perception",
            "reported",
            "player_observation",
        ),
        ("npc_claim", "npc:grum", "A ponte caiu ontem à noite.", "rumor", "reported", "npc_claim"),
        ("npc_claim", "npc:grum", "A ponte caiu.", "report", "reported", "npc_claim"),
        ("inference", None, "A ponte pode ter caído.", "suspicion", "speculative", "inference"),
        ("legacy_unverified", None, "A ponte caiu.", "report", "speculative", "legacy_unverified"),
    ],
)
def test_derivation_memory_rows(provenance, source_id, text, kind, certainty, source_kind):
    state = _state(event_log=[{"event_id": "ev1", "type": "npc_killed"}])
    stamp = pk.derive_stamp("memory", _mem(text, provenance, source_id=source_id), state)
    assert (stamp["knowledge_kind"], stamp["certainty"], stamp["source_kind"]) == (
        kind,
        certainty,
        source_kind,
    )
    assert stamp["source_ref"].startswith("memory:mem_")


def test_kind_values_closed():
    assert set(get_args(pk.KnowledgeKind)) == {"fact", "report", "rumor", "suspicion", "perception"}
    assert set(pk.KIND_LABEL_PT) == pk.KNOWLEDGE_KINDS
    with pytest.raises(ValueError):
        pk._stamp("fato", "canonical_event", "x:y", None, None)


def test_source_kind_reuses_memory_provenance():
    from typing import get_type_hints

    hints = get_type_hints(pk.KnowledgeStamp)
    assert hints["source_kind"] == mp.MemoryProvenance
    assert hints["certainty"] == mp.MemoryConfidence
    assert set(get_args(mp.MemoryConfidence)) == set(mp._CONFIDENCE_BY_PROVENANCE.values())


def test_legacy_maps_to_unverified_report():
    rows = mp.normalize_memory_facts(["Um fato antigo em string."])
    stamp = pk.derive_stamp("memory", rows[0], _state())
    assert stamp["knowledge_kind"] == "report"
    assert stamp["certainty"] == "speculative"
    assert stamp["label"] == "Relato não verificado"


def test_turns_none_when_missing():
    stamp = pk.derive_stamp("npc", {"name": "X", "knowledge_source": "met"}, _state())
    assert stamp["first_seen_turn"] is None and stamp["last_updated_turn"] is None
    stamp = pk.derive_stamp("visited", {"id": "nova_arcadia"}, _state())
    assert stamp["first_seen_turn"] is None and stamp["last_updated_turn"] is None
    stamp = pk.derive_stamp(
        "bestiary", {"id": RATO, "fought": 1, "first_seen_turn": 2, "last_update_turn": 5}, _state()
    )
    assert (stamp["first_seen_turn"], stamp["last_updated_turn"]) == (2, 5)


def test_faction_stale_only_with_old_intel():
    st = _state()
    fresh = pk.derive_stamp("faction", {"id": "f", "knows_goal": True, "intel_turn": 10}, st)
    old = pk.derive_stamp("faction", {"id": "f", "knows_goal": True, "intel_turn": 3}, st)
    assert fresh["stale"] is False and old["stale"] is True and old["last_updated_turn"] == 3


# ---------------------------------------------------------------------------
# Etapa 2 — visibilidade fail-closed
# ---------------------------------------------------------------------------


def test_hidden_entity_omitted_without_reveal():
    state = _state()
    state["world"]["visited"] = ["nova_arcadia", HIDDEN_LOC]
    codex = disc.player_codex(state)
    assert [loc["id"] for loc in codex["locations"]] == ["nova_arcadia"]
    assert codex["meta"]["counts"]["locations"] == 1
    blob = json.dumps(codex, ensure_ascii=False)
    assert HIDDEN_LOC not in blob and HIDDEN_NAME not in blob
    assert pk.assert_no_player_leak(codex, state) == []


def test_hidden_npc_omitted(monkeypatch):
    real = pk._entity_visibility
    monkeypatch.setattr(
        pk, "_entity_visibility", lambda eid: "hidden" if eid == "npc_fake_oculto" else real(eid)
    )
    state = _state(
        npcs={"Sombra": {"name": "Sombra", "id": "npc_fake_oculto", "knowledge_source": "met"}}
    )
    monkeypatch.setattr(
        "services.entity_identity.resolve_npc_entity_id", lambda npc, fallback="": npc.get("id")
    )
    codex = disc.player_codex(state)
    assert codex["characters"] == [] and codex["meta"]["counts"]["characters"] == 0


def test_hidden_entity_shown_after_secret_revealed_event():
    state = _state(**_reveal(HIDDEN_LOC))
    state["world"]["visited"] = ["nova_arcadia", HIDDEN_LOC]
    # O nome do Verme É assinatura do segredo `rei_subterraneo` (mapeado só a
    # mon_rei_subterraneo): revelar a entidade sem revelar o segredo continua
    # fail-closed (R6) — a entrada some e conta como redação.
    codex = disc.player_codex(state)
    assert HIDDEN_LOC not in {loc["id"] for loc in codex["locations"]}
    assert codex["meta"]["redactions"] >= 1
    assert pk.assert_no_player_leak(codex, state) == []
    # Com o segredo também revelado por evento canônico, a entrada aparece.
    state["event_log"].append(
        {
            "event_id": "ev_reveal_2",
            "type": "secret_revealed",
            "target_id": "mon_rei_subterraneo",
            "payload": {},
        }
    )
    state["world"]["visited"] = ["nova_arcadia", HIDDEN_LOC]
    codex = disc.player_codex(state)
    assert HIDDEN_LOC in {loc["id"] for loc in codex["locations"]}
    secret = codex["secrets"][0]
    assert secret["knowledge"]["knowledge_kind"] == "fact"
    assert secret["knowledge"]["source_ref"] == "event:ev_reveal_1"
    assert pk.assert_no_player_leak(codex, state) == []


def test_summary_or_known_secrets_do_not_reveal():
    state = _state(
        narrative_summary=f"O herói descobriu o {HIDDEN_NAME}. {HIDDEN_LOC}",
        player={"name": "T", "known_secrets": [HIDDEN_LOC, "rei_subterraneo"]},
    )
    state["world"]["visited"] = ["nova_arcadia", HIDDEN_LOC]
    codex = disc.player_codex(state)
    assert HIDDEN_LOC not in {loc["id"] for loc in codex["locations"]}
    assert pk.assert_no_player_leak(codex, state) == []


def test_unknown_visibility_is_secret(monkeypatch):
    monkeypatch.setattr(
        pk, "_entity_visibility", lambda eid: "segredissimo" if eid == "nova_arcadia" else None
    )
    assert pk.entity_is_player_visible("nova_arcadia", _state()) is False
    assert pk.entity_is_player_visible("outra", _state()) is True


def test_unavailable_graph_is_secret(monkeypatch):
    from services import graph_resolver as gr

    def boom(_eid):
        raise RuntimeError("grafo indisponível")

    monkeypatch.setattr(gr, "get_entity", boom)
    assert pk.entity_is_player_visible("nova_arcadia", _state()) is False


def test_signature_in_text_redacts_entry():
    state = _state(
        factions=[
            {
                "id": "legiao_ferro",
                "name": "Legião de Ferro",
                "goal": "Esconder o pacto com Valerius",
                "defeated": False,
            }
        ],
        faction_intel={"legiao_ferro": {"known": True, "knows_goal": True}},
    )
    codex = disc.player_codex(state)
    assert codex["factions"] == []
    assert codex["meta"]["redactions"] == 1
    assert "pacto com valerius" not in json.dumps(codex, ensure_ascii=False).casefold()


def test_malformed_entry_is_omitted_not_500():
    state = _state()
    raw = {
        "locations": [{"name": "sem id"}, "lixo"],
        "factions": [],
        "characters": [],
        "creatures": [],
        "secrets": [{"entity_id": "", "fact": "x", "turn": 1}],
    }
    out = pk.project_player_knowledge(state, raw)
    assert out["locations"] == [] and out["secrets"] == []
    assert out["meta"]["counts"]["locations"] == 0


# ---------------------------------------------------------------------------
# Etapa 3 — notas e promoção
# ---------------------------------------------------------------------------


def test_note_requires_visible_anchor():
    state = _state(
        memory_facts=[
            _mem("A praça está vazia.", "player_observation", entities=["nova_arcadia"]),
            _mem("Algo sob a montanha.", "player_observation", entities=[HIDDEN_LOC]),
            _mem("Sem âncora.", "player_observation", entities=[]),
            _mem("Mistura oculta.", "player_observation", entities=["nova_arcadia", HIDDEN_LOC]),
        ]
    )
    codex = disc.player_codex(state)
    notes = codex["locations"][0]["notes"]
    assert [n["text"] for n in notes] == ["A praça está vazia."]
    assert notes[0]["knowledge_kind"] == "perception"


def test_repeated_npc_claim_never_promotes():
    rows = [_mem("A ponte caiu.", "npc_claim", source_id=f"npc:n{i}", turn=i) for i in range(5)]
    state = _state(memory_facts=rows)
    kinds = {n["knowledge_kind"] for n in disc.player_codex(state)["locations"][0]["notes"]}
    assert kinds == {"report"}


def test_bestiary_rumor_becomes_fact_only_on_fought():
    state = _state(bestiary_knowledge={RATO: {"seen": 3}})
    cr = disc.player_codex(state)["creatures"][0]
    assert cr["knowledge"]["knowledge_kind"] == "rumor"
    state["bestiary_knowledge"] = {RATO: {"seen": 3, "fought": 1}}
    codex = disc.player_codex(state)
    assert codex["creatures"][0]["knowledge"]["knowledge_kind"] == "fact"
    assert pk.assert_no_player_leak(codex, state) == []


def test_npc_mentioned_to_met():
    state = _state(
        npcs={
            "Grum": {
                "name": "Grum",
                "knowledge_source": "mentioned",
                "created_turn": 2,
                "last_seen_turn": 4,
            }
        }
    )
    ch = disc.player_codex(state)["characters"][0]
    assert ch["knowledge"]["knowledge_kind"] == "rumor"
    assert (ch["knowledge"]["first_seen_turn"], ch["knowledge"]["last_updated_turn"]) == (2, 4)
    assert "_npc_key" not in ch and "_entity_id" not in ch
    state["npcs"]["Grum"]["knowledge_source"] = "met"
    codex = disc.player_codex(state)
    assert codex["characters"][0]["knowledge"]["knowledge_kind"] == "fact"
    assert pk.assert_no_player_leak(codex, state) == []


def test_canonical_without_applicable_source_is_suspicion():
    state = _state(memory_facts=[_mem("A ponte caiu.", "canonical_event", source_id="inventado")])
    note = disc.player_codex(state)["locations"][0]["notes"][0]
    assert (note["knowledge_kind"], note["source_kind"]) == ("suspicion", "inference")
    # o ledger não muda
    assert state["memory_facts"][0]["provenance"] == "canonical_event"


def test_rumor_marker_from_shared_pattern():
    from services import narrative_evidence as ne

    assert ne._QUALIFIED is ne.QUALIFIED_MARKER  # guard narrativo inalterado
    assert pk.QUALIFIED_MARKER is ne.QUALIFIED_MARKER
    assert pk._is_rumor_text("Dizem que é boato da taverna")
    assert not pk._is_rumor_text("O portão foi fechado.")


def test_rumor_notes_hidden_by_default_d1():
    state = _state(memory_facts=[_mem("Boato: a ponte caiu.", "npc_claim", source_id="npc:a")])
    assert disc.player_codex(state)["locations"][0]["notes"] == []


def test_signature_in_note_replaced_by_public_rumor():
    state = _state(memory_facts=[_mem("Ele fez um pacto com Valerius.", "player_observation")])
    codex = disc.player_codex(state)
    note = codex["locations"][0]["notes"][0]
    assert note["text"] == "os boatos em torno da ascensão de Valerius"
    assert codex["meta"]["redactions"] == 1
    assert pk.assert_no_player_leak(codex, state) == []


# ---------------------------------------------------------------------------
# Etapa 4 — oráculo e endpoint
# ---------------------------------------------------------------------------


def _clean_codex():
    state = _state(bestiary_knowledge={RATO: {"seen": 1}})
    return state, disc.player_codex(state)


def test_oracle_flags_each_leak_class():
    state, codex = _clean_codex()
    assert pk.assert_no_player_leak(codex, state) == []

    leak_a = copy.deepcopy(codex)
    leak_a["locations"].append(
        {
            "id": "x",
            "name": "x",
            "body": "",
            "portrait_url": f"/art/{HIDDEN_LOC}.webp",
            "knowledge": codex["locations"][0]["knowledge"],
            "notes": [],
        }
    )
    leak_a["meta"]["counts"]["locations"] += 1
    assert any(p.startswith("a:hidden_entity") for p in pk.assert_no_player_leak(leak_a, state))

    leak_b = copy.deepcopy(codex)
    leak_b["locations"][0]["body"] = "o rei se aquietou por medo"
    assert any(p.startswith("b:secret_signature") for p in pk.assert_no_player_leak(leak_b, state))

    leak_c = copy.deepcopy(codex)
    leak_c["meta"]["counts"]["creatures"] = 9
    assert "c:count_mismatch:creatures" in pk.assert_no_player_leak(leak_c, state)
    no_meta = {k: v for k, v in codex.items() if k != "meta"}
    assert "c:meta_counts_missing" in pk.assert_no_player_leak(no_meta, state)

    leak_d = copy.deepcopy(codex)
    leak_d["creatures"][0]["knowledge"]["knowledge_kind"] = "fact"
    leak_d["creatures"][0]["knowledge"]["source_kind"] = "canonical_event"
    assert any(
        p.startswith("d:fact_without_source") for p in pk.assert_no_player_leak(leak_d, state)
    )
    leak_d2 = copy.deepcopy(codex)
    leak_d2["locations"][0]["knowledge"]["knowledge_kind"] = "fato"
    assert any(
        p.startswith("d:kind_outside_taxonomy") for p in pk.assert_no_player_leak(leak_d2, state)
    )


def test_codex_endpoint_additive():
    from fastapi.testclient import TestClient

    import api
    import persistence

    game_id = str(uuid.uuid4())
    state = _state(game_id=game_id, bestiary_knowledge={RATO: {"seen": 1, "fought": 1}})
    state["world"]["visited"] = ["nova_arcadia", HIDDEN_LOC]
    assert persistence.save_game_state(state)
    resp = TestClient(api.app).get("/game/codex", params={"game_id": game_id})
    assert resp.status_code == 200
    body = resp.json()
    assert {"locations", "factions", "characters", "creatures", "secrets", "meta"} <= set(body)
    loc = body["locations"][0]
    assert {"id", "name", "body", "knowledge", "notes"} <= set(loc)
    assert body["meta"]["taxonomy_version"] == 1
    assert HIDDEN_LOC not in resp.text
    loaded = persistence.load_game_state(os.path.join(persistence.SAVES_DIR, f"{game_id}.json"))
    assert pk.assert_no_player_leak(body, loaded) == []


def test_public_panel_unchanged():
    from services import bestiary_knowledge as bk

    assert bk._PUBLIC_FIELDS == (
        "vitalidade",
        "max_vitalidade",
        "esquiva",
        "protecao",
        "integridade_atual",
        "integridade_max",
        "recursos_visiveis",
        "active_conditions",
        "posicao",
        "engajamentos",
    )
    enemy = {
        "id": "e1",
        "name": "Rato",
        "vitalidade": 5,
        "max_vitalidade": 5,
        "esquiva": 2,
        "segredo_interno": "x",
        "cards": ["c"],
        "resistances": {"fogo": 1},
        "armor": {"protecao": 1, "resist_tipos": ["x"]},
        "knowledge": {"knowledge_kind": "fact"},
    }
    panel = bk.public_panel(enemy)
    assert set(panel) <= set(bk._PUBLIC_FIELDS)


def test_legacy_save_roundtrip_projects():
    import persistence

    state = _state(game_id=str(uuid.uuid4()))
    for key in ("memory_facts", "faction_intel", "bestiary_knowledge"):
        state.pop(key, None)
    state["npcs"] = {"Velho": {"name": "Velho"}}  # sem knowledge_source/turnos
    assert persistence.save_game_state(state)
    path = os.path.join(persistence.SAVES_DIR, f"{state['game_id']}.json")
    loaded = persistence.load_game_state(path)
    with open(path, encoding="utf-8") as fh:
        before = json.load(fh)
    codex = disc.player_codex(loaded)
    assert codex["characters"][0]["knowledge"]["knowledge_kind"] == "fact"
    assert pk.assert_no_player_leak(codex, loaded) == []
    assert persistence.save_game_state(loaded)
    with open(path, encoding="utf-8") as fh:
        after = json.load(fh)
    assert (
        after.get("schema_version")
        == before.get("schema_version")
        == persistence.SCHEMA_VERSION
        == 8
    )
    assert set(after) == set(before)


def test_projection_is_read_only():
    state = _state(
        memory_facts=[_mem("A praça.", "player_observation")],
        bestiary_knowledge={RATO: {"seen": 1}},
    )
    snapshot = copy.deepcopy(state)
    disc.player_codex(state)
    assert state == snapshot


def test_no_llm_in_projection(monkeypatch):
    import llm_setup

    def boom(*_a, **_k):
        raise AssertionError("LLM chamado na projeção")

    monkeypatch.setattr(llm_setup, "get_llm", boom)
    state, codex = _clean_codex()
    assert codex["meta"]["counts"]["creatures"] == 1


# ---------------------------------------------------------------------------
# Revisão Astra — evasão por acento/espaço (normalização da varredura R6/R12)
# ---------------------------------------------------------------------------


def test_signature_without_accents_or_with_linebreak_still_redacts():
    state = _state(
        factions=[
            {
                "id": "legiao_ferro",
                "name": "Legião de Ferro",
                "goal": "Dizem que o rei se aquietou\npor medo do VERME-PRIMORDIAL DAS RAIZES do mundo",
                "defeated": False,
            }
        ],
        faction_intel={"legiao_ferro": {"known": True, "knows_goal": True}},
        memory_facts=[_mem("Vi o Verme-Primordial das Raizes do Mundo.", "player_observation")],
    )
    codex = disc.player_codex(state)
    assert codex["factions"] == []
    assert all("raizes" not in n["text"].casefold() for n in codex["locations"][0]["notes"])
    assert pk.assert_no_player_leak(codex, state) == []


def test_oracle_catches_accent_folded_leak():
    state, codex = _clean_codex()
    leak = copy.deepcopy(codex)
    leak["locations"][0]["body"] = (
        "o rei se aquietou\n por medo do verme-primordial das raizes do mundo"
    )
    problems = pk.assert_no_player_leak(leak, state)
    assert any(p.startswith("b:secret_signature") for p in problems)
    assert any(p.startswith("a:hidden_entity") for p in problems)
