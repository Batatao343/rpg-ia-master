"""SPEC-391: reforço de combate no tabuleiro de cartas ("Chamado do Bando" do líder de matilha).

Etapa 1 (avaliador do gate, congelado): oráculo de equivalência da arena
``docs/spec391/arena_reforco_cartas.py`` contra ``scripts/cards/sim.py::_fight`` com a flag do
reforço ``off``, e o formato da saída por célula.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARENA_PATH = os.path.join(ROOT, "docs", "spec391", "arena_reforco_cartas.py")
LEADERS = ("enemy_soldado_legiao_ferro", "mon_auroque_ruinas")
SEEDS = (0, 1)
LEVEL = 3


@pytest.fixture(scope="module")
def arena():
    name = "arena_reforco_cartas_391"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ARENA_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def deck_flags_off(monkeypatch):
    """As duas pontas com baralho de cartas e baralhos/intenção de inimigo `on`; reforço `off`."""
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "off")


def test_arena_reforco_off_equivale_sim_fight(arena, deck_flags_off):
    """R14/Etapa 1: com a flag `off`, a arena nova devolve o mesmo `(desfecho, rodadas)` de
    `sim._fight` em 20 lutas fixas (5 Posturas × 2 líderes × 2 sementes, L3)."""
    assert set(LEADERS) <= set(arena.A.leader_pool())
    assert len(arena.CLASSES) == 5
    pairs = []
    for cls in arena.CLASSES:
        deck = arena.sim.full_deck(cls, LEVEL)
        for bid in LEADERS:
            for seed in SEEDS:
                counters: dict = {}
                got = arena.fight(bid, 1, cls, LEVEL, seed, deck, "391", counters)
                ref = arena.sim._fight(bid, 1, cls, LEVEL, seed, deck, "391")
                pairs.append((cls, bid, seed, got, ref))
                assert counters == dict.fromkeys(arena.FLOW_COUNTERS, 0)
    assert len(pairs) == 20
    diverge = [p for p in pairs if p[3] != p[4]]
    assert not diverge, diverge
    assert all(p[3][0] in ("win", "death", "timeout") for p in pairs)


def test_arena_reforco_saida_tem_campos(arena, deck_flags_off):
    """Etapa 1: cada célula tem `death/win/timeout/fights/avg_rounds/per_class` e os contadores
    do fluxo `telegraphed/called/fired/cancelled` (também no total)."""
    classes = list(arena.CLASSES[:2])
    res = arena.run(range(1), [LEVEL], classes)
    pool = arena.A.leader_pool()
    assert res["pool"] == pool and res["mode"] == "off"
    assert isinstance(res["card_flow"], bool)
    cell = res["cells"][f"L{LEVEL}|lider_matilha"]
    for block in (cell, res["total"]):
        for key in ("death", "win", "timeout", "fights", "avg_rounds", "per_class"):
            assert key in block, key
        for key in ("telegraphed", "called", "fired", "cancelled"):
            assert isinstance(block[key], int) and block[key] == 0, key
        assert block["fights"] == len(pool) * len(classes)
        assert block["death"] + block["win"] + block["timeout"] == block["fights"]
        assert set(block["per_class"]) == set(classes)
        for pc in block["per_class"].values():
            assert pc["fights"] == len(pool)
            assert {"death", "win", "timeout", "death_rate", "win_rate"} <= set(pc)
        assert isinstance(block["countered"], int) and block["countered"] == 0


@pytest.mark.parametrize(
    ("state", "outcome", "expected"),
    [
        ({}, "win", False),  # sem telegrafo: não é contra-jogo
        ({"telegraphed_round": 2, "fired": True}, "win", False),  # chegou
        ({"telegraphed_round": 2, "cancelled": True}, "death", True),  # motor cancelou
        ({"telegraphed_round": 2, "called_round": 3}, "win", True),  # líder caiu antes da chegada
        ({"telegraphed_round": 2}, "win", True),
        ({"telegraphed_round": 2, "called_round": 3}, "death", False),  # herói morreu antes
        ({"telegraphed_round": 2}, "timeout", False),
    ],
)
def test_arena_reforco_countered(arena, state, outcome, expected):
    """Emenda pré-gate (revisão Sol P3-2): `countered` conta o contra-jogo que a arena encerra
    como `win` antes de `advance_card_flow` rodar; `cancelled` segue só o do motor."""
    counters: dict = {}
    arena._count_flow({"reinforcement": state}, counters, outcome)
    assert counters["countered"] == int(expected)
    assert counters["cancelled"] == int(bool(state.get("cancelled")))


# ==========================================================================
# Etapas 2-3: núcleo determinístico, nó de combate e payload (R1-R16, R20)
# ==========================================================================
import json  # noqa: E402
import random  # noqa: E402

from services import card_effects as fx  # noqa: E402
from services import card_lint, cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import enemy_decks as edk  # noqa: E402
from services import enemy_intent as ei  # noqa: E402
from services import reinforcement_cards as rc  # noqa: E402
from services import reinforcements as rf  # noqa: E402
from tests.spec325_chase_helpers import step  # noqa: E402
from tests.test_spec325_reinforcements import PASS, _api_payload, _leader, _state  # noqa: E402

LID = "enemy_soldado_legiao_ferro_1"


@pytest.fixture
def card_on(monkeypatch):
    for key, val in {
        "RPG_COMBAT_REINFORCEMENTS": "on",
        "RPG_CARD_DECK": "on",
        "RPG_ENEMY_DECKS": "on",
        "RPG_ENEMY_INTENT": "on",
        "RPG_FORCE_MOCK": "1",
    }.items():
        monkeypatch.setenv(key, val)
    edk.reload()
    yield
    edk.reload()


def _run(monkeypatch, rounds=1, **kw):
    """Roda `rounds` rodadas do nó real com o líder a 14/30; devolve `[(merged, out), ...]`."""
    from tests.spec325_helpers import run_node

    state = _state(**kw)
    out = run_node(state, monkeypatch)
    seq = [(state, out)]
    for _ in range(rounds - 1):
        state, out = step(state, out, monkeypatch, "espero", declaration=PASS)
        seq.append((state, out))
    return seq


def _meta(out):
    return out["combat"].get("reinforcement") or {}


def _events(monkeypatch):
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(rc, "_log_event", lambda area, name, **kw: seen.append((name, kw)))
    return seen


# --- R1 ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "flag,deck,decks,expected",
    [
        ("on", "on", "on", True),
        ("shadow", "on", "on", True),
        ("on", "off", "on", False),
        ("on", "on", "off", False),
        ("off", "on", "on", False),
    ],
)
def test_eligibility_matrix(monkeypatch, flag, deck, decks, expected):
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", flag)
    monkeypatch.setenv("RPG_CARD_DECK", deck)
    monkeypatch.setenv("RPG_ENEMY_DECKS", decks)
    assert rc.eligible() is expected


def test_dispatch_legacy_without_card_deck(monkeypatch, card_on):
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    out = _run(monkeypatch)[0][1]
    assert _meta(out).get("via") is None and _meta(out)["warned_round"] == 1  # R16 legado
    assert rc.CALL_CARD not in out["enemies"][0].get("cartas", [])


# --- R3/R4 ---------------------------------------------------------------------------
def test_telegraph_on_half_vitality_records_promise(monkeypatch, card_on):
    state, out = _run(monkeypatch)[0]
    meta = _meta(out)
    assert (meta["via"], meta["stage"], meta["telegraphed_round"], meta["call_round"]) == (
        "carta",
        "telegraphed",
        1,
        2,
    )
    assert "warned_round" not in meta  # telegrafado: sem o espelho do aviso legado
    assert rc.CALL_CARD in out["enemies"][0]["cartas"]
    promise = out["combat"]["scene"]["prenuncios"][LID]
    assert promise["carta"] == rc.CALL_CARD and promise["rnd"] == 2 and promise["tipo"] == "chamado"
    rows = out["combat"]["pressagios_publicos"]
    assert "Capitão Teste" in rows[0]["prenuncio"] and "chamar" in rows[0]["prenuncio"]
    assert len(out["enemies"]) == 1
    payload = _api_payload(state, out)["combat"]
    assert "reinforcement_warning" not in payload
    assert payload["reinforcement"] == {
        "stage": "telegraphed",
        "leader_id": LID,
        "chega_na_rodada": None,
    }


def _signature_leader():
    leader = _leader()
    leader["tactical_profile"] = {
        "assinatura": {"carta": "inf_lider_matilha_uivo_de_reuniao", "a_cada_n": 2, "desvio": 0}
    }
    leader = orch.ensure_combat_sheet(leader)
    leader["cartas"] = [*leader["cartas"], "inf_lider_matilha_uivo_de_reuniao", rc.CALL_CARD]
    scene = {"prenuncios": {LID: {"carta": rc.CALL_CARD, "rnd": 2, "tipo": "chamado"}}}
    return leader, scene


def test_call_overrides_signature_same_round(card_on):
    leader, scene = _signature_leader()
    assert edk.assinatura_of(leader)["carta"] == "inf_lider_matilha_uivo_de_reuniao"
    assert edk._sig_falls_on(leader, edk.assinatura_of(leader), 2)  # cairia em N+1
    assert edk.plan(leader, 2, scene)["assinatura"] == rc.CALL_CARD
    assert edk.plan(leader, 2)["assinatura"] == "inf_lider_matilha_uivo_de_reuniao"
    assert edk.record_promise(scene, leader, 1) is False  # a vaga é do chamado
    assert scene["prenuncios"][LID]["tipo"] == "chamado"
    frozen = {LID: [{"actor_id": LID, "tipo": "defesa", "carta_id": rc.CALL_CARD}]}
    row = ei.public_round(frozen, {LID: leader}, 2)[0]
    assert "chamar" in row["prenuncio"]
    out: dict = {}
    edk.close_promises(scene, {LID: leader}, 3, out)
    assert "pressagios_frustrados" not in out


# --- R5/R6/R7 ------------------------------------------------------------------------
def _pure_world():
    leader = _leader()
    leader["tactical_profile"] = {
        "priorities": [
            {"trigger": "alvo_vulneravel", "tipo": "obrigatorio", "action_key": "attack"}
        ]
    }
    leader = orch.ensure_combat_sheet(leader)
    leader["cartas"] = [*leader["cartas"], rc.CALL_CARD]
    scene = cs.new_scene()
    for aid in ("player", LID):
        cs.place(scene, aid)
    cs.freeze(scene)
    scene["prenuncios"] = {LID: {"carta": rc.CALL_CARD, "rnd": 2, "tipo": "chamado"}}
    from tests.test_enemy_decks import _player

    actors = {"player": _player(), LID: leader}
    sides = {"hero": ["player"], "ally": [], "enemy": [LID]}
    return scene, actors, sides


def _declare(scene, actors, sides, rnd=2):
    return orch.enemy_declaration(
        scene, LID, actors, sides, scene_state={"_rodada_decisao": rnd}, rng=random.Random(1)
    )


def _pick(monkeypatch, trigger, action_key):
    from services import tactical_profile as tp

    monkeypatch.setattr(
        tp, "pick_action", lambda *a, **k: {"trigger": trigger, "action_key": action_key}
    )


def test_leader_plays_call_even_with_vulnerable_target(monkeypatch, card_on):
    scene, actors, sides = _pure_world()
    _pick(monkeypatch, "alvo_vulneravel", "attack")
    decl = _declare(scene, actors, sides)
    assert (decl.acao.kind, decl.acao.card_id) == ("card", rc.CALL_CARD)
    assert decl.acao.target_id == LID  # protecao em si: nada de ataque extra (R5)
    scene["prenuncios"][LID]["rnd"] = 5  # sem chamado pendente: o gatilho do perfil manda
    assert _declare(scene, actors, sides).acao.card_id != rc.CALL_CARD


def test_call_not_played_on_flee_or_forced_attack(monkeypatch, card_on):
    scene, actors, sides = _pure_world()
    _pick(monkeypatch, "muito_ferido", "flee")
    assert _declare(scene, actors, sides).acao.card_id != rc.CALL_CARD
    actors[LID]["_forced_attack"] = True
    _pick(monkeypatch, "sempre", "attack")
    assert _declare(scene, actors, sides).acao.card_id != rc.CALL_CARD


def test_call_card_outside_family_pools_and_lints():
    pools = edk._pools()
    assert all(rc.CALL_CARD not in ids for ids in pools["familias"].values())
    assert all(rc.CALL_CARD not in ids for ids in pools["faccoes"].values())
    card = cards.get_card(rc.CALL_CARD)
    assert card and card["oculta"] is True and card["efeito"]["kind"] == "protecao"
    c = fx.materialize(card)  # mesmo lint das Cartas de família (test_enemy_decks)
    issues = card_lint.check_vocabulary(c) + card_lint.check_budget(c) + card_lint.check_voice(c)
    assert not card_lint.errors(issues), issues


def test_call_consumes_turn_and_sets_called_stage(monkeypatch, card_on):
    events = _events(monkeypatch)
    state, out = _run(monkeypatch, rounds=2)[1]
    meta = _meta(out)
    assert (meta["stage"], meta["called_round"], meta["warned_round"]) == ("called", 2, 2)
    assert [n for n, _ in events].count("reinforcements_warned") == 1
    assert all(kw.get("via") == "carta" for n, kw in events if n.startswith("reinforcements_"))
    assert out["enemies"][0]["enemy_card_usage"][rc.CALL_CARD]["used_this_scene"] == 1
    payload = _api_payload(state, out)["combat"]
    assert payload["reinforcement_warning"] is True
    assert payload["reinforcement"] == {"stage": "called", "leader_id": LID, "chega_na_rodada": 3}
    assert len(out["enemies"]) == 1  # nunca antes do fim de N+2


# --- R8/R9 ---------------------------------------------------------------------------
def _telegraphed_world():
    leader = _leader()
    leader["cartas"] = [rc.CALL_CARD]
    enemies = [leader]
    scene = cs.new_scene()
    cs.place(scene, LID)
    for trig in rf.plan_triggers(enemies, 20, encounter_level=3):
        cs.add_reinforcement_trigger(scene, trig)
    cs.freeze(scene)
    return scene, enemies, {LID: leader}, {"enemy": [LID]}, {}


@pytest.mark.parametrize("flag", ["dead", "fled", "surrendered", "stunned"])
def test_call_frustrated(monkeypatch, card_on, flag):
    events = _events(monkeypatch)
    scene, enemies, actors, sides, meta = _telegraphed_world()
    res = rc.advance_card_flow(scene, enemies, actors, sides, meta, 1)
    assert res["telegraphed"] and meta["reinforcement"]["stage"] == "telegraphed"
    if flag != "stunned":  # atordoado: o líder vive, só não joga a Carta (sem marca na cena)
        enemies[0][flag] = True
    res = rc.advance_card_flow(scene, enemies, actors, sides, meta, 2)
    assert meta["reinforcement"]["cancelled"] and meta["reinforcement"]["cause"] == "frustrado"
    assert "chamar o bando" in res["logs"][0] and len(enemies) == 1
    assert scene.get("prenuncios", {}).get(LID) is None
    cancelled = [kw for n, kw in events if n == "reinforcements_cancelled"]
    assert cancelled == [{"level": "info", "via": "carta", "cause": "frustrado"}]


def test_arrival_end_of_n2_never_before_and_leader_down_cancels(card_on):
    scene, enemies, actors, sides, meta = _telegraphed_world()
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 1)
    rc.on_declaration(scene, LID, rc.CALL_CARD, 2)
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 2)
    assert meta["reinforcement"]["stage"] == "called" and len(enemies) == 1
    snap = json.loads(json.dumps({"m": meta, "s": scene, "e": enemies}))
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 3)
    assert meta["reinforcement"]["fired"] and enemies[-1]["id"].endswith("_r1")
    # o mesmo estado, líder caído em N+2 -> cancela sem chegada
    e2 = snap["e"]
    e2[0]["dead"] = True
    rc.advance_card_flow(snap["s"], e2, {LID: e2[0]}, {"enemy": [LID]}, snap["m"], 3)
    assert snap["m"]["reinforcement"]["cause"] == "lider_caido" and len(e2) == 1


def test_budget_cancels(card_on):
    scene, enemies, actors, sides, meta = _telegraphed_world()
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 1)
    rc.on_declaration(scene, LID, rc.CALL_CARD, 2)
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 2)
    scene["reinforcement_triggers"][0]["budget"] = 0
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 3)
    assert meta["reinforcement"]["cause"] == "budget" and len(enemies) == 1


# --- R12/R13 -------------------------------------------------------------------------
def test_reinforcement_inherits_deck_seed_and_forecast(monkeypatch, card_on):
    import tests.test_spec325_reinforcements as t325

    def last(seed):
        monkeypatch.setattr(
            t325, "_leader", lambda vit=14, **over: _leader_with_seed(vit, seed, **over)
        )
        return _run(monkeypatch, rounds=3)[-1][1]

    base_leader = _leader

    def _leader_with_seed(vit, seed, **over):
        return base_leader(vit, deck_seed=seed, **over)

    out = last(7)
    new = out["enemies"][1]
    assert new["id"].endswith("_r1") and new["deck_seed"] == 7 and new.get("_deck332")
    assert new["chegou_na_rodada"] == 3
    assert new["id"] in [r["actor_id"] for r in out["combat"]["pressagios_publicos"]]
    assert last(7)["enemies"][1]["cartas"] == new["cartas"]  # determinístico


def test_card_flow_pure_and_zero_llm(monkeypatch, card_on):
    import llm_setup

    def boom(*a, **k):
        raise AssertionError("LLM chamado no fluxo do Chamado")

    monkeypatch.setattr(llm_setup, "get_llm", boom)
    a = _run(monkeypatch, rounds=3)[-1][1]
    b = _run(monkeypatch, rounds=3)[-1][1]
    assert json.dumps(_meta(a), sort_keys=True) == json.dumps(_meta(b), sort_keys=True)
    assert _meta(a)["fired"] is True


# --- R14/R15/R16 ---------------------------------------------------------------------
def test_off_byte_identical_combat_meta(monkeypatch, card_on):
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "off")
    state, out = _run(monkeypatch, rounds=2)[-1]
    assert "reinforcement" not in out["combat"]
    scene = out["combat"]["scene"]
    assert "chamado_jogado" not in scene
    assert not any(p.get("tipo") == "chamado" for p in (scene.get("prenuncios") or {}).values())
    assert rc.CALL_CARD not in out["enemies"][0]["cartas"]
    assert "reinforcement" not in _api_payload(state, out)["combat"]


def _carry(state, out):
    combat = json.loads(json.dumps(out["combat"], default=str))  # save -> load
    return {**state, **{k: v for k, v in out.items() if k != "next"}, "combat": combat}


@pytest.mark.parametrize("rounds", [1, 2])
def test_save_load_telegraphed_and_called(monkeypatch, card_on, rounds):
    state, out = _run(monkeypatch, rounds=rounds)[-1]
    state = _carry(state, out)
    state, nxt = step(state, {}, monkeypatch, "espero", declaration=PASS)
    if rounds == 1:  # telegrafado -> chamado -> chegada
        assert _meta(nxt)["stage"] == "called"
        state, nxt = step(_carry(state, nxt), {}, monkeypatch, "espero", declaration=PASS)
    assert _meta(nxt)["fired"] is True
    assert len(nxt["enemies"]) == 2 and nxt["enemies"][0]["cartas"].count(rc.CALL_CARD) == 1


def test_old_r16_save_continues_legacy(monkeypatch, card_on):
    state, out = _run(monkeypatch)[0]
    state = _carry(state, out)
    state["combat"]["reinforcement"] = {
        "trigger_id": f"reinf_{LID}",
        "leader_id": LID,
        "warned_round": 1,
        "fired": False,
    }
    state["combat"]["scene"].pop("prenuncios", None)
    state["enemies"][0]["cartas"].remove(rc.CALL_CARD)
    _, nxt = step(state, {}, monkeypatch, "espero", declaration=PASS)
    assert _meta(nxt)["fired"] is True and "via" not in _meta(nxt)  # fluxo legado, sem Carta


def test_events_registered_with_via():
    from observability.events import EVENTS

    assert "via" in EVENTS["combat.reinforcements_telegraphed"]
    for name in ("warned", "fired", "cancelled"):
        assert "via" in EVENTS[f"combat.reinforcements_{name}"]


# --- R20 ------------------------------------------------------------------------------
def test_family_pools_still_never_call_and_only_chamados_does():
    for fam, ids in edk._pools()["familias"].items():
        for cid in ids:
            blob = json.dumps(cards.get_card(cid), ensure_ascii=False).lower()
            assert "reforco" not in blob and "reforço" not in blob, (fam, cid)
    data = json.loads((edk._DIR / "chamados.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cards"]] == [rc.CALL_CARD]
    assert rc.CALL_CARD not in sum(edk._pools()["familias"].values(), [])


# --- Etapa 3: nó real de ponta a ponta e payload ---------------------------------------
def test_node_card_flow_end_to_end(monkeypatch, card_on):
    """Telegrafo -> chamado -> chegada `_r1` -> `joined` no manifesto -> XP do `_r1` ao morrer."""
    from agents import combat as cbt
    from services import encounter_manifest as em

    seq = _run(monkeypatch, rounds=3)
    state, out = seq[-1]
    new = next(e for e in out["enemies"] if e["id"].endswith("_r1"))
    manifest = out["combat"]["encounter"]
    assert em.is_valid_manifest(manifest)
    assert any(
        ev["kind"] == "joined" and ev["participant_id"] == new["id"] for ev in manifest["events"]
    )
    new["vitalidade"] = 1
    xp_before = out["player"].get("xp", 0)
    merged = _carry(state, out)
    merged["combat_declaration"] = {
        "actor_id": "player",
        "acao": {"kind": "attack", "target_id": new["id"]},
    }
    merged["player"] = {**merged["player"], "virtudes": {"forca": 9, "agilidade": 9, "corpo": 9}}
    random.seed(1)
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")
    out2 = cbt.combat_node(merged)
    dead = next(e for e in out2["enemies"] if e["id"] == new["id"])
    assert (dead.get("dead") or dead.get("status") == "morto") and dead["xp_awarded"] is True
    assert out2["player"].get("xp", 0) > xp_before


def test_payload_reinforcement_stages(monkeypatch, card_on):
    seq = _run(monkeypatch, rounds=3)
    views = [_api_payload(s, o)["combat"] for s, o in seq]
    assert views[0]["reinforcement"]["stage"] == "telegraphed"
    assert "reinforcement_warning" not in views[0]
    assert views[1]["reinforcement"]["stage"] == "called" and views[1]["reinforcement_warning"]
    assert "reinforcement" not in views[2] and "reinforcement_warning" not in views[2]  # chegou


def test_payload_never_leaks_template(monkeypatch, card_on):
    for state, out in _run(monkeypatch, rounds=2):  # telegrafo e chamado: o reforço não existe
        blob = json.dumps(_api_payload(state, out)["combat"], default=str).lower()
        assert "capanga" not in blob and "_r1" not in blob and rf.GENERIC_ID not in blob
        assert set(_api_payload(state, out)["combat"]["reinforcement"]) == {
            "stage",
            "leader_id",
            "chega_na_rodada",
        }


# --- R17: playtest -----------------------------------------------------------------------
def test_playtest_scenario_card_flow_ends_without_violations(monkeypatch, card_on):
    """O cenário `combate_reforco` com o baralho `on` termina em chamado + chegada, sem violação."""
    from playtest import scenarios
    from playtest.runner import run_campaign

    result = run_campaign(
        scenarios.profile_for("combate_reforco"), turns=8, seed=0, scenario="combate_reforco"
    )
    errors = [v for v in result.violations if v.get("severity") == "error"]
    assert not errors and not result.errors, (errors, result.errors)
    assert result.capability_counts["reinforcements"] >= 1
    reinf = (result.final_state.get("combat") or {}).get("reinforcement") or {}
    assert reinf.get("via") == "carta" and reinf.get("fired") is True


# --- Revisão Sol (P2-1, P3-4) ----------------------------------------------------------
def test_frustrated_call_drops_card_and_never_returns(monkeypatch, card_on):
    from services import conflict_orchestrator as orch2

    scene, enemies, actors, sides, meta = _telegraphed_world()
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 1)
    assert rc.CALL_CARD in enemies[0]["cartas"]
    rc.advance_card_flow(scene, enemies, actors, sides, meta, 2)  # não jogou: frustrado
    assert meta["reinforcement"]["cause"] == "frustrado"
    assert rc.CALL_CARD not in enemies[0]["cartas"]
    w_scene, w_actors, w_sides = _pure_world()
    w_actors[LID]["cartas"] = [c for c in w_actors[LID]["cartas"] if c != rc.CALL_CARD]
    w_scene["prenuncios"] = {}
    for kind in ("support", "protect", "attack"):
        _pick(monkeypatch, "sempre", kind)
        for rnd in range(3, 7):
            decl = orch2.enemy_declaration(
                w_scene,
                LID,
                w_actors,
                w_sides,
                scene_state={"_rodada_decisao": rnd},
                rng=random.Random(rnd),
            )
            assert decl.acao.card_id != rc.CALL_CARD


def test_flag_off_with_pending_call_does_not_play_it(monkeypatch, card_on):
    scene, actors, sides = _pure_world()
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "off")
    _pick(monkeypatch, "alvo_vulneravel", "attack")
    assert rc.pending_call(scene, actors[LID], 2) is None
    assert edk.plan(actors[LID], 2, scene)["assinatura"] != rc.CALL_CARD
    assert _declare(scene, actors, sides).acao.card_id != rc.CALL_CARD
    assert rc.payload_fields({"reinforcement": {"via": "carta", "stage": "called"}}) == {}


def test_node_frustration_in_payload_and_round_log(monkeypatch, card_on):
    state, out = _run(monkeypatch)[0]
    state = _carry(state, out)
    state["enemies"][0]["cartas"].remove(rc.CALL_CARD)  # o líder não consegue jogar o Chamado
    state, nxt = step(state, {}, monkeypatch, "espero", declaration=PASS)
    assert _meta(nxt)["cancelled"] is True and _meta(nxt)["cause"] == "frustrado"
    payload = _api_payload(state, nxt)["combat"]
    assert "reinforcement" not in payload and "reinforcement_warning" not in payload
    assert len(nxt["enemies"]) == 1
    board = json.dumps(payload.get("registro_rodada") or payload, ensure_ascii=False)
    assert "Presságio frustrado" in board or "frustrado" in board


@pytest.mark.parametrize("rounds", [1, 2])
def test_save_load_real_persistence(monkeypatch, tmp_path, card_on, rounds):
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    state, out = _run(monkeypatch, rounds=rounds)[-1]
    saved = {k: v for k, v in _carry(state, out).items() if k != "messages"}
    saved["game_id"] = f"spec391-{rounds}"
    assert persistence.save_game_state({**state, **saved})
    loaded = persistence.load_game_state(str(tmp_path / f"spec391-{rounds}.json"))
    assert loaded["combat"]["reinforcement"] == out["combat"]["reinforcement"]
    assert loaded["combat"]["scene"].get("prenuncios") == out["combat"]["scene"].get("prenuncios")
    cont = {**state, **loaded, "messages": state["messages"]}
    _, nxt = step(cont, {}, monkeypatch, "espero", declaration=PASS)
    assert _meta(nxt)["stage"] == "called" or _meta(nxt)["fired"]
    assert nxt["enemies"][0]["cartas"].count(rc.CALL_CARD) == 1
