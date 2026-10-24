"""SPEC-299 — correções da revisão Sol (P1-1..P1-3, P2-1..P2-6)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from agents import router, storyteller
from services import law
from tests.spec299_helpers import base_state, clock_where, with_clock
from tests.test_spec299_confrontation import _apply, _confronted, _crime, _route


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    monkeypatch.delenv("RPG_NPC_KNOWLEDGE", raising=False)


def _jailed():
    base = _confronted([_crime("a", "homicidio", severity=70)])
    return _apply(base, _route(base, "me entrego"))


# ------------------------------- P1-1: prisão ------------------------------- #
def test_jailed_travel_intent_is_escape_attempt_not_free_travel(monkeypatch):
    jailed = _jailed()
    assert jailed["world"]["current_location_id"] == "na_anel_ferro"
    monkeypatch.setattr(
        "services.conflict_resolution.roll_kept",
        lambda adv, rng: {"rolled": [1, 1], "kept": [1, 1]},
    )
    failed = _route(jailed, "vou para o Anel de Lama")
    assert failed["next"] == "storyteller" and failed["law_gate_consumed"] is True
    assert "world" not in failed or failed["world"]["current_location_id"] == "na_anel_ferro"
    assert failed["law_state"]["confrontation"]["reason"] == "imprisoned"
    # o storyteller não reaplica a viagem neste turno
    state = _apply(jailed, failed)
    state["messages"] = [HumanMessage(content="vou para o Anel de Lama")]
    out = storyteller.storyteller_node(state)
    assert (out.get("world") or state["world"])["current_location_id"] == "na_anel_ferro"


def test_jailed_escape_success_moves_once_and_adds_evasao(monkeypatch):
    jailed = _jailed()
    monkeypatch.setattr(
        "services.conflict_resolution.roll_kept",
        lambda adv, rng: {"rolled": [10, 10], "kept": [10, 10]},
    )
    ok = _route(jailed, "fujo para o Anel de Lama")
    assert ok["world"]["current_location_id"] == "na_anel_lama"
    assert ok["law_state"]["confrontation"] is None
    assert any(c["crime_type"] == "evasao" for c in ok["law_state"]["crimes"])
    state = _apply(jailed, ok)
    state["messages"] = [HumanMessage(content="fujo para o Anel de Lama")]
    out = storyteller.storyteller_node(state)
    assert (out.get("world") or state["world"])["current_location_id"] == "na_anel_lama"


def test_jailed_rest_does_not_skip_time_via_storyteller():
    jailed = _jailed()
    state = _apply(jailed, _route(jailed, "descanso"))
    assert state["law_state"]["confrontation"]["reason"] == "imprisoned"
    before = law.clock_of(state)
    state["messages"] = [HumanMessage(content="descanso")]
    state["law_gate_consumed"] = True
    out = storyteller.storyteller_node(state)
    assert law.clock_of({**state, **out}) == before


def test_imprisoned_confrontation_does_not_persist_outside_prison():
    jailed = _jailed()
    outside = {**jailed, "world": {**jailed["world"], "current_location_id": "na_anel_lama"}}
    out = law.turn_updates(outside)
    assert out["law_state"]["confrontation"] is None


def test_gate_consumed_flag_is_cleared_by_finalizer():
    from agents.turn_finalizer import turn_finalizer_node  # noqa: F401  (import real)

    jailed = _jailed()
    payload = _route(jailed, "descanso")
    assert payload["law_gate_consumed"] is True
    plain = router._base_route_payload(router.RouteType.STORY, {})
    assert "law_gate_consumed" not in plain  # rotas normais não carregam a flag


# --------------------------- P1-2: negação no gate -------------------------- #
@pytest.mark.parametrize(
    "text, expect_next, expect_gold_spent",
    [
        ("Não me rendo! Saco a espada.", "combat_agent", False),
        ("Jamais me entrego a vocês", "npc_actor", False),
        ("não vou pagar nada", "npc_actor", False),
        ("eu me recuso a pagar, ataco o guarda", "combat_agent", False),
        ("não fujo, explico que foi legítima defesa", "npc_actor", False),
        ("não vou para lugar nenhum", "npc_actor", False),
    ],
)
def test_gate_understands_negation(text, expect_next, expect_gold_spent):
    base = _confronted([_crime("a", "agressao", severity=30)])
    out = _route(base, text)
    assert out["next"] == expect_next, text
    assert ("player" in out) is expect_gold_spent
    conf = out["law_state"]["confrontation"]
    assert out["law_state"]["served"] == [] or conf is None and out["next"] == "combat_agent"
    if expect_next == "npc_actor":
        assert conf is not None  # nada foi escolhido: o confronto segue
        assert all(c["status"] == "reported" for c in out["law_state"]["crimes"])


def test_affirmed_helper_clause_scope():
    import re

    pat = re.compile(r"\brendo\b")
    assert law._affirmed(pat, "eu rendo")
    assert not law._affirmed(pat, "nao rendo")
    assert law._affirmed(pat, "nao quero briga, mas rendo")  # outra oração
    assert not law._affirmed(pat, "jamais me rendo")


# ----------------------- P1-3: cena do destino na viagem -------------------- #
def test_travel_turn_uses_destination_scene(monkeypatch):
    s = base_state("nova_arcadia")
    s = with_clock(s, clock_where(s, "nova_arcadia", patrol=True))
    seen = []
    orig = law.scene_block

    def spy(state, **kw):
        out = orig(state, **kw)
        seen.append((state["world"]["current_location_id"], out[0]))
        return out

    monkeypatch.setattr(law, "scene_block", spy)
    s["messages"] = [HumanMessage(content="viajo para o Pântano da Melancolia")]
    out = storyteller.storyteller_node(s)
    dest = (out.get("world") or {}).get("current_location_id")
    assert dest == "pantano_melancolia"
    assert seen and seen[0][0] == dest and seen[0][1] == ""  # sem lei no destino: bloco vazio


def test_origin_signals_not_marked_shown_on_travel():
    wanted = {
        "jurisdiction_id": "codigo_de_ferro",
        "heat": 90,
        "bounty": 400,
        "capital": True,
        "last_crime_clock": 20,
        "known_at": {"nova_arcadia": 0},
        "signals_shown": [],
        "hunters_last_clock": -1,
    }
    s = with_clock(base_state("nova_arcadia"), 50)
    s["law_state"] = {"wanted": {"codigo_de_ferro": wanted}}
    s["messages"] = [HumanMessage(content="viajo para o Pântano da Melancolia")]
    out = storyteller.storyteller_node(s)
    shown = ((out.get("law_state") or s["law_state"])["wanted"]["codigo_de_ferro"])["signals_shown"]
    assert "perguntaram_por_voce" not in shown


# ------------------------------ P2-1: léxico -------------------------------- #
@pytest.mark.parametrize(
    "ctype, text",
    [
        ("furto", "me aproximo furtivamente da porta"),
        ("magia_ilegal", "fico encantado com a vista"),
        ("magia_ilegal", "pergunto sobre magia antiga"),
        ("agressao", "observo o golpe de sorte do mercador"),
        ("agressao", "grito socorro"),
        ("dano_propriedade", "olho a queimadura na parede"),
    ],
)
def test_lexicon_negatives(ctype, text):
    assert not law.supports(ctype, text)


@pytest.mark.parametrize(
    "ctype, text",
    [
        ("furto", "roubo a bolsa do mercador"),
        ("agressao", "esfaqueio o mercador"),
        ("agressao", "dou um soco no guarda"),
        ("homicidio", "mato o guarda"),
        ("dano_propriedade", "quebro a vitrine"),
        ("magia_ilegal", "lanço um feitiço de éter"),
        ("magia_ilegal", "uso o Éter para acender a tocha"),
    ],
)
def test_lexicon_positives(ctype, text):
    assert law.supports(ctype, text)


# ------------------------- P2-2: lei branda (multa) ------------------------- #
def _clan_confronted(gold):
    crime = _crime("a", "agressao", severity=20, loc="skallgard")
    crime["jurisdiction_id"] = "lei_dos_clas"
    state = _confronted([crime], loc="skallgard", gold=gold)
    wanted = state["law_state"]["wanted"]["codigo_de_ferro"]
    state["law_state"]["wanted"] = {"lei_dos_clas": {**wanted, "jurisdiction_id": "lei_dos_clas"}}
    state["law_state"]["confrontation"]["jurisdiction_id"] = "lei_dos_clas"
    return state


def test_clan_surrender_pays_fine_with_gold():
    out = _route(_clan_confronted(500), "me rendo")
    assert out["player"]["gold"] == 500 - 60
    assert out["law_state"]["wanted"]["lei_dos_clas"]["heat"] == 0


def test_clan_surrender_without_gold_expels_without_hunting_level():
    state = _clan_confronted(0)
    out = _route(state, "me rendo")
    wanted = out["law_state"]["wanted"]["lei_dos_clas"]
    assert law.level(wanted, law.clock_of(state)) != "cacado" and wanted["heat"] <= 30


# ----------------------------- P2-3: shadow --------------------------------- #
def test_shadow_does_not_write_fame_or_emit_events(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "shadow")
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st = {**state, **law.register_crime(state, _cand(state))[0]}
    out = law.turn_updates(st)
    assert out["law_state"]["wanted"]["codigo_de_ferro"]["heat"] > 0
    assert "location_fame" not in out and "pending_world_events" not in out


def _cand(state):
    return {
        "crime_type": "furto",
        "victim_ref": "local",
        "source": "engine",
        "location_id": state["world"]["current_location_id"],
        "turn": state["world"]["turn_count"],
    }


# --------------------------- P2-4: licença no jogo -------------------------- #
def test_license_request_routes_through_router_and_charges():
    state = with_clock(base_state(), 40)
    state["messages"] = [HumanMessage(content="Peço o registro do meu Éter ao escrivão da Legião")]
    out = router.dm_router_node(state)
    assert out["next"] == "storyteller" and out["law_gate_consumed"] is True
    assert out["player"]["gold"] == 250
    assert out["law_state"]["licenses"] == ["codigo_de_ferro"]
    assert "registra" in out["law_state"]["notice"]["text"]
    # depois de licenciado, magia em público não é crime
    licensed = {**state, **out}
    why = law.register_crime(
        licensed, {"crime_type": "magia_ilegal", "victim_ref": "", "source": "engine"}
    )[2]
    assert why == "licenciado"


def test_license_request_without_gold_or_outside_jurisdiction():
    poor = with_clock(base_state(player={"gold": 5}), 40)
    poor["messages"] = [HumanMessage(content="compro a licença de magia")]
    out = router.dm_router_node(poor)
    assert "player" not in out and "falta ouro" in out["law_state"]["notice"]["text"]
    lawless = with_clock(base_state("brekmar"), 40)
    lawless["messages"] = [HumanMessage(content="compro a licença de magia")]
    assert router._law_gate(lawless, lawless["world"], lawless["messages"]) is None


def test_first_witnessed_magic_shows_registry_signal():
    state = with_clock(base_state(), 40)
    state["law_state"] = {
        "crimes": [
            {
                "crime_id": "m1",
                "crime_type": "magia_ilegal",
                "jurisdiction_id": "codigo_de_ferro",
                "status": "reported",
            }
        ],
        "wanted": {
            "codigo_de_ferro": {
                "jurisdiction_id": "codigo_de_ferro",
                "heat": 40,
                "bounty": 10,
                "capital": False,
                "last_crime_clock": 40,
                "known_at": {"nova_arcadia": 0},
                "signals_shown": [],
                "hunters_last_clock": -1,
            }
        },
    }
    assert any("registro" in s for s in law.signals_for(state))


# ----------------------------- P2-6: concordância --------------------------- #
def test_authority_agreement():
    text, _ = law.scene_block(_patrolled_state())
    assert "Soldados da Legião de Ferro" in text and "de A Legião" not in text


def _patrolled_state():
    s = base_state()
    return with_clock(s, clock_where(s, "nova_arcadia", patrol=True))
