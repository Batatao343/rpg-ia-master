"""SPEC-422: registro deterministico do arquivista (descanso sem gancho e resposta descartada).

Etapa 1 (R11): oraculos de equivalencia das duas extracoes (linhas de rejeicao do resumo e
marca `archive_low` da viagem). O golden do arquivista foi gravado no HEAD ANTES da extracao.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents import archivist
from agents.archivist import MemoryUpdate
from tests.fakes.scripted_llm import ScriptedLLM

_GOLDEN = Path(__file__).parent / "fixtures" / "spec422_rejection_rows_golden.json"

_LOC = "O Anel Dourado é um bairro alto de Brekmar."
_INV = "O viajante carrega o Diário da Casa Vesper."
_NPC = "Skriit Mil-olhos é um homem alto de cabelo grisalho."
_BAD = f"{_LOC} {_INV} {_NPC} Ceslo segue viagem."


def _grounded_state(summary: str) -> dict:
    return {
        "game_id": "g422-golden",
        "player": {"name": "Ceslo", "inventory": [{"id": "pocao_cura", "qty": 1}]},
        "world": {
            "turn_count": 49,
            "current_location_id": "na_anel_dourado",
            "current_location": "Anel Dourado",
        },
        "npcs": {
            "Skriit Mil-olhos": {
                "id": "npc_skriit_mil-olhos",
                "name": "Skriit Mil-olhos",
                "appearance": "Goblin pequeno e encolhido, de pele verde-acinzentada.",
                "in_scene": True,
            }
        },
        "rejected_item_claims": ["Diário da Casa Vesper"],
        "archive_due": True,
        "messages": [HumanMessage(content="oi"), AIMessage(content="Olá.")],
        "narrative_summary": summary,
        "memory_facts": [],
        "chronicle": [],
    }


def _run_golden(scenario: str, monkeypatch) -> dict:
    monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: True)
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "legacy")
    if scenario == "initial":
        state = _grounded_state(_BAD)
        llm = ScriptedLLM(
            {MemoryUpdate: MemoryUpdate(new_summary="Ceslo descansa.", important_facts=[])}
        )
    elif scenario == "success":
        state = _grounded_state("Ceslo investiga.")
        llm = ScriptedLLM({MemoryUpdate: MemoryUpdate(new_summary=_BAD, important_facts=[])})
    else:  # plain
        state = _grounded_state("Ceslo investiga.")
        llm = ScriptedLLM({MemoryUpdate: AIMessage(content="erro")}, text=_BAD)
    monkeypatch.setattr(archivist, "get_llm", lambda **_kw: llm)
    out = archivist.archive_node(state)
    keep = ("narrative_summary", "memory_rejections", "memory_facts", "archivist_last_run")
    return json.loads(json.dumps({k: out.get(k) for k in keep}, sort_keys=True, default=str))


@pytest.mark.parametrize("scenario", ["initial", "success", "plain"])
def test_archivist_rejeicoes_iguais_ao_golden_do_head(scenario, monkeypatch):
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    got = _run_golden(scenario, monkeypatch)
    assert got["memory_rejections"], "o cenario precisa exercitar as linhas de rejeicao"
    assert got == golden[scenario]


def test_summary_rejection_rows_igual_ao_bloco_antigo():
    from services.archive_record import summary_rejection_rows

    loc = [{"location_id": "x", "claimed_region": "Y"}]
    inv = [{"item_name": "Diario", "claim_kind": "rejected_item"}]
    npc = [{"npc_name": "Skriit", "field": "species"}]

    def _old(turn, a, b, c):  # copia literal do bloco antigo de archivist.py
        return [
            *[
                {
                    "turn": int(turn),
                    "provenance": "narrative_summary",
                    "reason": "location_region_contradiction",
                    **row,
                }
                for row in a
            ],
            *[
                {
                    "turn": int(turn),
                    "provenance": "narrative_summary",
                    "reason": "inventory_possession_contradiction",
                    **row,
                }
                for row in b
            ],
            *[
                {
                    "turn": int(turn),
                    "provenance": "narrative_summary",
                    "reason": "npc_identity_contradiction",
                    **row,
                }
                for row in c
            ],
        ]

    for args in ((loc, [], []), ([], inv, []), ([], [], npc), (loc, inv, npc), ([], [], [])):
        assert summary_rejection_rows(7, *args) == _old(7, *args)
    assert summary_rejection_rows("7", loc, inv, npc)[0]["turn"] == 7


def _story_turn(**kw):
    base = dict(  # noqa: C408
        dest="x",
        rested_player=None,
        beat_done=False,
        updates={},
        turn=5,
        state={},
        world={},
        update=SimpleNamespace(introduced_npcs=[]),
        quarantine_llm_payload=False,
        pending_llm_events=[],
        enc=None,
        _fauna_sign_shown=False,
        rest_note="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _old_archive_low(t, same_region, wanted):  # copia literal da condicao antiga do storyteller
    if (
        wanted
        and t.dest
        and t.rested_player is None
        and not t.beat_done
        and not t.updates.get("pending_world_events")
        and "quests" not in t.updates
        and "memory_canonical_facts" not in t.updates
        and same_region()
    ):
        return {"archive_low": t.turn}
    return {}


@pytest.mark.parametrize("policy", ["legacy", "lean"])
@pytest.mark.parametrize(
    "kw",
    [
        {},
        {"dest": None},
        {"rested_player": {"hp": 1}},
        {"beat_done": True},
        {"updates": {"pending_world_events": [{"a": 1}]}},
        {"updates": {"quests": []}},
        {"updates": {"memory_canonical_facts": ["x"]}},
    ],
)
@pytest.mark.parametrize("same_region", [True, False])
def test_story_marks_archive_low_igual(policy, kw, same_region, monkeypatch):
    from services import archive_record, latency_flags

    monkeypatch.setenv("RPG_ARCHIVE_POLICY", policy)
    monkeypatch.delenv("RPG_ARCHIVE_POLICY_SHADOW", raising=False)
    monkeypatch.delenv("RPG_ARCHIVE_RECORD", raising=False)
    t = _story_turn(**kw)
    got = archive_record.story_marks(t, same_region=lambda: same_region)
    assert got == _old_archive_low(t, lambda: same_region, latency_flags.archive_low_wanted())


# --------------------------------------------------------------------------------------------
# Etapa 2: marca do narrador (R3) e `off` identico (I1)
# --------------------------------------------------------------------------------------------


def _run_story(
    monkeypatch, text, update, *, enc=None, roll=None, weather=None, world=None, swamp=False
):
    import random

    import world_utils
    from agents import storyteller as st
    from tests.spec382_node_cases import _Fake, story_state

    state = story_state(text, **(world or {}))
    if weather or swamp:
        if weather:
            state["world"]["weather_state"] = weather
        state["world"]["current_location_id"] = "pantano_melancolia"
        state["world"]["current_location"] = "Pântano da Melancolia"
    fake = _Fake(update, [])
    monkeypatch.setattr(st, "get_llm", lambda *a, **k: fake)
    monkeypatch.setattr(st, "check_encounter", enc or (lambda *a, **k: None))
    if enc:  # a regiao segura de early-game nao sorteia encontro: forca o sorteio
        monkeypatch.setattr(world_utils, "recovery_rest_safe", lambda *a, **k: False)
    if roll:
        monkeypatch.setattr(world_utils, "roll_encounter_type", lambda danger: roll)
    random.seed(1)
    return st.storyteller_node(state)


def _enc_dict(**kw):
    base = {"reason": "controlled", "flavor": "Bandidos bloqueiam a estrada.", "hint": "Bandido"}
    base.update(kw)
    return lambda *a, **k: dict(base)


def _upd(**kw):
    from tests.spec382_node_cases import _upd as upd

    return upd(**kw)


@pytest.fixture
def record_on(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_RECORD", "on")


def test_marca_rest_so_no_descanso_sem_gancho(monkeypatch, record_on):
    out = _run_story(monkeypatch, "Descanso até o amanhecer.", _upd())
    assert out["archive_record"] == {"kind": "rest", "turn": 4}
    assert out["archive_due"] is True


def test_marca_rest_bloqueada_pelo_clima(monkeypatch, record_on):
    out = _run_story(monkeypatch, "Descanso até o amanhecer.", _upd(), weather="miasma")
    mark = out["archive_record"]
    assert mark["kind"] == "rest" and mark["blocked"]


@pytest.mark.parametrize(
    "case",
    [
        "emboscada",
        "armadilha",
        "rastro",
        "social",
        "npc_introduzido",
        "viagem",
        "excecao",
    ],
)
def test_marca_ausente_quando_ha_gancho_ou_encontro(monkeypatch, record_on, case):
    text, update, kw = "Descanso até o amanhecer.", _upd(), {}
    if case == "emboscada":
        kw = {"enc": _enc_dict(), "world": {"danger_level": 4}, "swamp": True}
    elif case == "armadilha":
        kw = {
            "enc": _enc_dict(reason="x"),
            "roll": "trap",
            "world": {"danger_level": 4},
            "swamp": True,
        }
    elif case == "rastro":
        kw = {
            "enc": _enc_dict(reason="x"),
            "roll": "track",
            "world": {"danger_level": 4},
            "swamp": True,
        }
    elif case == "social":
        update = _upd(introduced_npcs=["Porta-voz"])
        kw = {
            "enc": _enc_dict(reason="x"),
            "roll": "social",
            "world": {"danger_level": 4},
            "swamp": True,
        }
    elif case == "npc_introduzido":
        update = _upd(introduced_npcs=["Mira"])
    elif case == "viagem":
        text = "Viajo para Brekmar."
    elif case == "excecao":
        update = RuntimeError("falha no narrador")
    out = _run_story(monkeypatch, text, update, **kw)
    assert "archive_record" not in out


def test_marca_ausente_com_rumor_aceito_no_descanso(monkeypatch, record_on):
    """P2-1: rumor aceito (SPEC-312) abre gancho; o fio `rumor_new` tira a marca do descanso."""
    from agents.storyteller import ProposedRumor, StoryUpdateWithRumors
    from services import rumors

    monkeypatch.setenv("RPG_RUMORS_PROPOSED", "on")
    proposal = ProposedRumor(text="Dizem nas docas que alguem compra o silencio", entity_ids=[])
    update = StoryUpdateWithRumors(narrative="A cena segue calma.", proposed_rumors=[proposal])
    accepted = {"rumors": [{"id": "r1"}]}
    monkeypatch.setattr(
        rumors,
        "accept_proposed",
        lambda st, props, **kw: (accepted, {**(st.get("world") or {})}, []),
    )
    out = _run_story(monkeypatch, "Descanso até o amanhecer.", update)
    assert out["world_sim"] is accepted  # o rumor foi aceito de fato
    assert "archive_record" not in out
    plain = _run_story(monkeypatch, "Descanso até o amanhecer.", _upd())
    assert plain["archive_record"] == {"kind": "rest", "turn": 4}  # controle: sem rumor, marca


def test_marca_ausente_com_off(monkeypatch):
    monkeypatch.delenv("RPG_ARCHIVE_RECORD", raising=False)
    out = _run_story(monkeypatch, "Descanso até o amanhecer.", _upd())
    assert "archive_record" not in out
    monkeypatch.setenv("RPG_ARCHIVE_RECORD", "valor-invalido")  # invalido cai em off
    out = _run_story(monkeypatch, "Descanso até o amanhecer.", _upd())
    assert "archive_record" not in out


def test_marca_shadow_tambem_e_emitida(monkeypatch):
    monkeypatch.setenv("RPG_ARCHIVE_RECORD", "shadow")
    out = _run_story(monkeypatch, "Descanso até o amanhecer.", _upd())
    assert out["archive_record"] == {"kind": "rest", "turn": 4}


def _rest_turn(**kw):
    base = {
        "dest": None,
        "rested_player": {"hp": 5},
        "rest_note": "O jogador DESCANSOU.",
        "turn": 5,
    }
    base.update(kw)
    return _story_turn(**base)


@pytest.mark.parametrize(
    "kw,rumor_new",
    [
        ({"_fauna_sign_shown": True}, False),
        ({"rested_player": {"dead": True}}, False),
        ({"beat_done": True}, False),
        ({"updates": {"quests": []}}, False),
        ({"pending_llm_events": [{"type": "x"}]}, False),
        ({"update": SimpleNamespace(introduced_npcs=["Mira"])}, False),
        ({}, True),
    ],
)
def test_marca_ausente_por_gancho_estruturado(monkeypatch, record_on, kw, rumor_new):
    from services import archive_record

    assert "archive_record" in archive_record.story_marks(_rest_turn(), same_region=lambda: False)
    t = _rest_turn(**kw)
    assert "archive_record" not in archive_record.story_marks(
        t, same_region=lambda: False, rumor_new=rumor_new
    )


# --------------------------------------------------------------------------------------------
# Etapa 3: registro deterministico no arquivista (R1, R2, R4-R6, R10) e invariantes I1-I8
# --------------------------------------------------------------------------------------------

_TURN = 5  # fora da janela de retry (5 % 3 != 0), a 2 turnos do ultimo run (cadencia nao vence)
_SUMMARY = "Ela seguiu pela estrada do norte."
_SENTENCE_END = "e ele recuperou parte das forças."


def _rest_state(**kw) -> dict:
    st = {
        "game_id": "g422",
        "messages": [HumanMessage(content="Descanso."), AIMessage(content="Você dorme.")],
        "world": {
            "turn_count": _TURN,
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "world_clock": {"day": 2, "period": "Manhã"},
        },
        "player": {"name": "Ari", "inventory": []},
        "npcs": {},
        "narrative_summary": _SUMMARY,
        "archive_due": True,
        "archive_record": {"kind": "rest", "turn": _TURN},
        "archivist_last_run": 3,
        "chronicle": [],
        "memory_facts": [],
        "event_log": [],
    }
    st.update(kw)
    return st


def _keeping_script(summary: str = _SUMMARY) -> MemoryUpdate:
    return MemoryUpdate(new_summary=summary, important_facts=[], chronicle_entry="")


def _run_archive(monkeypatch, state, mode, *, script=None, event_updates=None, baseline=None):
    monkeypatch.setenv("RPG_ARCHIVE_RECORD", mode)
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "legacy")
    llm = ScriptedLLM({MemoryUpdate: script or _keeping_script()}, repeat_last=True)
    writes: list = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kw: llm)
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda _g, facts, **_k: writes.append(list(facts)) or True,
    )
    out = archivist._archive_node(state, event_updates=event_updates, baseline=baseline)
    return out, llm, writes


def _without(out: dict, *keys: str) -> dict:
    return {k: v for k, v in out.items() if k not in keys}


def test_descanso_nao_chama_llm_do_arquivista(monkeypatch):
    off, llm_off, _ = _run_archive(monkeypatch, _rest_state(), "off")
    assert [name for name, _ in llm_off.calls] == ["MemoryUpdate"]
    on, llm_on, _ = _run_archive(monkeypatch, _rest_state(), "on")
    assert llm_on.calls == []  # nem o SMART estruturado, nem o texto puro
    assert on["narrative_summary"].startswith(_SUMMARY)
    assert "O herói descansou em Nova Arcádia; agora é" in on["narrative_summary"]
    assert on["narrative_summary"].endswith(_SENTENCE_END)
    assert "archivist_last_run" not in on  # R5: so o LLM avanca o ultimo resumo
    assert off["archivist_last_run"] == _TURN


def test_descanso_bloqueado_usa_frase_do_clima(monkeypatch):
    st = _rest_state(archive_record={"kind": "rest", "turn": _TURN, "blocked": "miasma"})
    on, llm, _ = _run_archive(monkeypatch, st, "on")
    assert llm.calls == []
    assert (
        "tentou descansar em Nova Arcádia, mas o clima (miasma) não deixou"
        in (on["narrative_summary"])
    )


def test_rejeicao_sem_conflito_igual_ao_llm(monkeypatch):
    """I3: T0 (resposta descartada) devolve exatamente o que o LLM "lixo" renderia."""
    junk = MemoryUpdate(
        new_summary="LIXO que o codigo descarta.",
        important_facts=["Fato lixo permanente."],
        chronicle_entry="Cronica lixo do bardo.",
    )

    def state():
        return _rest_state(archive_record=None, narrative_rejections=["event_rejected:x"])

    off, llm_off, _ = _run_archive(monkeypatch, state(), "off", script=junk)
    on, llm_on, _ = _run_archive(monkeypatch, state(), "on", script=junk)
    assert len(llm_off.calls) == 1 and llm_on.calls == []
    assert on == off
    assert on["narrative_summary"] == _SUMMARY
    assert on["archivist_last_run"] == _TURN  # T0 grava, como hoje
    assert not any(e.get("kind") == "prose" for e in on.get("chronicle", []))


_DAY_FACT = "O pão ficou mais caro em Nova Arcádia."


def _canon_ids(out: dict) -> set:
    return {
        row["memory_id"] for row in out["memory_facts"] if row["provenance"] == "canonical_event"
    }


def test_descanso_registra_todos_os_fatos_canonicos(monkeypatch):
    """I2: fatos do dia + evento do motor percebido: mesmo conjunto com `off` e `on`."""
    event = {
        "event_id": "evt-rest-1",
        "type": "npc_killed",
        "target_id": "npc_bandido",
        "turn": _TURN,
        "payload": {},
    }

    def state():
        return _rest_state(memory_canonical_facts=[_DAY_FACT], memory_fact_policy="canonical_only")

    ups = {"event_log": [event]}
    off, _, _ = _run_archive(monkeypatch, state(), "off", event_updates=dict(ups))
    on, llm, _ = _run_archive(monkeypatch, state(), "on", event_updates=dict(ups))
    assert llm.calls == []
    assert len(_canon_ids(off)) >= 2, "o cenario precisa de evento E fato do dia"
    assert _canon_ids(on) == _canon_ids(off)
    assert _without(on, "narrative_summary", "archivist_last_run") == _without(
        off, "narrative_summary", "archivist_last_run"
    )


def test_descanso_drena_fila_de_npc_como_hoje(monkeypatch):
    """I5: fila de NPC: dreno/retencao e `archive_due` identicos ao caminho com LLM."""
    queue = [{"operation": "add_npc_memory", "npc_id": "npc_mira", "facts": ["Mira confia."]}]
    for npc_ok in (True, False):
        monkeypatch.setattr(archivist, "add_npc_memory", lambda *a, ok=npc_ok, **k: ok)
        off, _, _ = _run_archive(monkeypatch, _rest_state(pending_npc_memory=list(queue)), "off")
        on, llm, _ = _run_archive(monkeypatch, _rest_state(pending_npc_memory=list(queue)), "on")
        assert llm.calls == []
        for key in ("pending_npc_memory", "archive_due", "memory_facts"):
            assert on.get(key) == off.get(key), (npc_ok, key)
        assert on["archive_due"] is (not npc_ok)


def test_descanso_com_indice_fora_mantem_pendentes(monkeypatch):
    """I6: indice vetorial fora: fatos ficam pendentes e entram no retry de `turn % 3`."""
    monkeypatch.setattr(archivist, "_persist_memory_records", lambda *_a, **_k: False)
    st = _rest_state(memory_canonical_facts=[_DAY_FACT], memory_fact_policy="canonical_only")
    on, llm, _ = _run_archive(monkeypatch, st, "on")
    assert llm.calls == []
    assert on["pending_memory_facts"], "o indice fora deixa o fato pendente"
    assert on["archive_due"] is True
    pending_ids = {r["memory_id"] for r in on["pending_memory_facts"]}
    assert pending_ids <= {r["memory_id"] for r in on["memory_facts"]}  # o ledger ja o tem
    # na janela de retry (turno 6), com o indice de volta, o pendente e escrito
    monkeypatch.setattr(archivist, "_persist_memory_records", lambda *_a, **_k: True)
    nxt = _rest_state(
        archive_record=None,
        world={**_rest_state()["world"], "turn_count": 6},
        memory_facts=on["memory_facts"],
        pending_memory_facts=on["pending_memory_facts"],
        archive_due=True,
    )
    again, _, _ = _run_archive(monkeypatch, nxt, "off")
    assert again["pending_memory_facts"] == []


def _entries(chronicle) -> list[dict]:
    return [e for chapter in chronicle or [] for e in chapter.get("entries", [])]


def test_descanso_cronica_so_marcos(monkeypatch):
    """I7: sem entrada `prose` nova; o marco que ja existia no turno continua."""
    from services.chronicle import append_entry

    chron = append_entry([], text="A ponte caiu.", turn=_TURN, kind="milestone")
    off, _, _ = _run_archive(
        monkeypatch,
        _rest_state(chronicle=chron),
        "off",
        script=MemoryUpdate(new_summary=_SUMMARY, important_facts=[], chronicle_entry="Cantiga."),
    )
    on, llm, _ = _run_archive(monkeypatch, _rest_state(chronicle=chron), "on")
    assert llm.calls == []
    assert [e["kind"] for e in _entries(off["chronicle"])] == ["milestone", "prose"]
    assert [e["kind"] for e in _entries(on.get("chronicle", chron))] == ["milestone"]


def test_descanso_com_cadencia_vencida_usa_llm(monkeypatch):
    on, llm, _ = _run_archive(monkeypatch, _rest_state(archivist_last_run=_TURN - 10), "on")
    assert len(llm.calls) == 1
    assert on["archivist_last_run"] == _TURN


def test_descanso_com_conflito_usa_llm(monkeypatch):
    conflict = {"conflict_id": "c1", "conflict_turn": _TURN, "facts": ["A ponte caiu."]}
    on, llm, _ = _run_archive(monkeypatch, _rest_state(conflict_summary=conflict), "on")
    assert len(llm.calls) == 1


def test_marca_de_outro_turno_ignorada(monkeypatch):
    st = _rest_state(archive_record={"kind": "rest", "turn": _TURN - 1})
    on, llm, _ = _run_archive(monkeypatch, st, "on")
    assert len(llm.calls) == 1
    assert on["narrative_summary"] == _SUMMARY


def test_dois_descansos_nao_acumulam_frase(monkeypatch):
    first, _, _ = _run_archive(monkeypatch, _rest_state(), "on")
    st = _rest_state(narrative_summary=first["narrative_summary"])
    second, llm, _ = _run_archive(monkeypatch, st, "on")
    assert llm.calls == []
    assert second["narrative_summary"].count("O herói descansou em") == 1
    assert second["narrative_summary"].startswith(_SUMMARY)


def test_projecao_adiada_sem_efeito(monkeypatch):
    """R7: com projecao adiada (baseline) a flag nao tem efeito: o LLM segue chamado."""
    baseline = {"new_event_ids": [], "new_rejections": False}
    on, llm, _ = _run_archive(monkeypatch, _rest_state(), "on", baseline=baseline)
    assert len(llm.calls) == 1


def test_fallback_llm_off_e_shadow_como_hoje(monkeypatch):
    """R10: `FallbackLLM` devolve AIMessage: off e shadow caem no texto puro, sem excecao."""
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_ARCHIVE_RECORD", mode)
        bad = ScriptedLLM.failing("[erro de llm]", is_fallback=True)
        monkeypatch.setattr(archivist, "get_llm", lambda bad=bad, **_kw: bad)
        monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: True)
        out = archivist._archive_node(_rest_state())
        assert out["narrative_summary"] == _SUMMARY, mode
        assert bad.calls, mode


def test_frase_de_descanso_sobrevive_aos_saneadores():
    """I8: para todo local do mapa, a frase nao e rejeitada por nenhum saneador."""
    import gamedata
    from services import archive_record
    from services.memory_provenance import (
        sanitize_inventory_grounding,
        sanitize_location_grounding,
        sanitize_npc_identity_grounding,
    )
    from services.narrative_evidence import build_evidence, validate_narrative

    assert len(gamedata._LOCATIONS_BY_ID) > 5
    for loc_id, loc in gamedata._LOCATIONS_BY_ID.items():
        st = _rest_state(
            world={
                "turn_count": _TURN,
                "current_location_id": loc_id,
                "current_location": loc.get("name", ""),
                "world_clock": {"day": 2, "period": "Noite"},
            }
        )
        for mark in (None, {"kind": "rest", "turn": _TURN, "blocked": "miasma"}):
            text = archive_record.rest_sentence(st, mark)
            for fn in (
                sanitize_location_grounding,
                lambda t, st=st: sanitize_inventory_grounding(t, st),
                lambda t, st=st: sanitize_npc_identity_grounding(t, st),
            ):
                cleaned, rejected = fn(text)
                assert not rejected and cleaned == text, (loc_id, text, rejected)
            check = validate_narrative(text, build_evidence(st), channel="summary")
            assert not check.rejections and check.text == text, (loc_id, text, check.rejections)


# --------------------------------------------------------------------------------------------
# Etapa 4: shadow e telemetria (R7-R9)
# --------------------------------------------------------------------------------------------


def test_shadow_chama_llm_e_registra_would_skip(monkeypatch, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        out, llm, _ = _run_archive(monkeypatch, _rest_state(), "shadow")
    assert len(llm.calls) == 1
    assert out["archivist_last_run"] == _TURN  # como hoje
    lines = [r.getMessage() for r in caplog.records if "record_shadow" in r.getMessage()]
    assert lines and '"kind": "rest"' in lines[0] and '"would_skip": true' in lines[0]
    caplog.clear()
    with caplog.at_level(logging.INFO):
        _run_archive(monkeypatch, _rest_state(archive_record=None), "shadow")
    lines = [r.getMessage() for r in caplog.records if "record_shadow" in r.getMessage()]
    assert lines and '"would_skip": false' in lines[0] and "no_rest_mark" in lines[0]


def test_trigger_reasons_lista_fixa():
    from services import archive_record

    talk = {"archive_due": True, "memory_fact_policy": "canonical_only", "archivist_last_run": 3}
    reasons = archive_record.trigger_reasons(talk, _TURN)
    assert {"archive_due", "canonical_only"} <= set(reasons)
    assert "archive_due_low" not in reasons
    low = archive_record.trigger_reasons({**talk, "archive_low": _TURN}, _TURN)
    assert "archive_due_low" in low and "archive_due" not in low
    everything = archive_record.trigger_reasons(
        {
            **talk,
            "conflict_summary": {"a": 1},
            "memory_canonical_facts": ["x"],
            "pending_npc_memory": [{}],
            "pending_memory_facts": [{}],
            "archivist_last_run": 0,
        },
        12,
    )
    assert set(everything) <= set(archive_record.TRIGGER_REASONS)
    assert {"conflict", "canonical_facts", "pending_npc_memory", "vector_retry", "cadence"} <= set(
        everything
    )
    assert "archive_due" in archive_record.trigger_reasons(_rest_state(), _TURN)


def test_bump_archive_deterministic(monkeypatch):
    from observability import latency

    seen: list = []
    monkeypatch.setattr(latency, "bump", lambda key, n=1: seen.append(key))
    _run_archive(monkeypatch, _rest_state(), "on")
    assert seen == ["archive_deterministic"]
    seen.clear()
    _run_archive(monkeypatch, _rest_state(), "off")
    assert seen == []


# --------------------------------------------------------------------------------------------
# Etapa 5: flag registrada, `off` identico e round-trip (I4)
# --------------------------------------------------------------------------------------------


def test_flag_registrada_default_off(monkeypatch):
    import yaml

    from services import latency_flags

    path = Path(__file__).parent.parent / "config" / "flags.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry = cfg.get("RPG_ARCHIVE_RECORD") or cfg["flags"]["RPG_ARCHIVE_RECORD"]
    assert entry["default"] == "off" and entry["kind"] == "release"
    assert str(entry["expires"]) == "2027-02-28" and entry["spec"] == "SPEC-422"
    monkeypatch.delenv("RPG_ARCHIVE_RECORD", raising=False)
    assert latency_flags.archive_record_mode() == "off"
    monkeypatch.setenv("RPG_ARCHIVE_RECORD", "talvez")
    assert latency_flags.archive_record_mode() == "off"


def test_off_identico_ao_head(monkeypatch):
    """Com `off` a marca no estado e inerte (mesmas chamadas, mesmo estado). A prova de I1
    (`off` = hoje, estado/result/trace) e o golden da SPEC-382, sem alteracao."""
    marked, llm_a, _ = _run_archive(monkeypatch, _rest_state(), "off")
    plain, llm_b, _ = _run_archive(monkeypatch, _rest_state(archive_record=None), "off")
    assert marked == plain
    assert len(llm_a.calls) == len(llm_b.calls) == 1
    assert "archive_record" not in marked


def test_round_trip_depois_do_registro_deterministico(monkeypatch):
    """I4: save -> load preserva o ledger e o resumo; `archive_record` nao e salvo."""
    import persistence

    on, llm, _ = _run_archive(monkeypatch, _rest_state(), "on")
    assert llm.calls == []
    state = {**_rest_state(), **on}
    raw = persistence._state_to_save_data({"game_id": "g422-rt", **state}, "g422-rt")
    assert "archive_record" not in raw
    loaded = persistence._raw_to_state(raw)
    for key in ("narrative_summary", "memory_facts", "pending_memory_facts", "chronicle"):
        assert loaded[key] == state.get(key, loaded[key]), key
    assert loaded["archivist_last_run"] == 3
    raw.pop("archivist_last_run", None)  # persistence.py sem diff; `archive_record` nunca e salvo
    assert persistence._raw_to_state(raw) is not None


def test_off_nao_emite_eventos_de_registro(monkeypatch, caplog):
    """R9 (22/11): com `off`, nenhum evento trigger/record/record_shadow (igual a hoje)."""
    import logging

    with caplog.at_level(logging.INFO):
        _run_archive(monkeypatch, _rest_state(), "off")
    text = " ".join(r.getMessage() for r in caplog.records)
    for name in ("trigger", "record_shadow", '"record"'):
        assert name not in text, name


def test_shadow_emite_trigger_com_motivos(monkeypatch, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        _run_archive(monkeypatch, _rest_state(), "shadow")
    lines = [r.getMessage() for r in caplog.records if "trigger" in r.getMessage()]
    assert lines and "archive_due" in lines[0]
