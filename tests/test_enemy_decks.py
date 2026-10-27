"""SPEC-332: baralhos de inimigo por família + padrão de intenção + assinatura telegrafada."""

from __future__ import annotations

import collections
import json
import random

import pytest

from services import card_effects as fx
from services import card_lint, cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import enemy_decks as edk
from services import enemy_intent as ei


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_DECKS", raising=False)
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
    edk.reload()
    yield
    edk.reload()


def _player():
    return orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
            "entropy": 10,
            "max_entropy": 10,
            "abyss_charge": 0,
        },
        is_player=True,
    )


def _enemy(eid="lobo_1", **kw):
    e = {
        "id": eid,
        "name": "Lobo Cinzento",
        "type": "Minion",
        "arquetipo": "predador",
        "max_vitalidade": 30,
        "vitalidade": 30,
        "entropy": 10,
        "max_entropy": 10,
        "cartas": [],
        "tactical_profile": {
            "priorities": [
                {"trigger": "muito_ferido", "tipo": "obrigatorio", "action_key": "flee"},
                {"trigger": "sempre", "tipo": "obrigatorio", "action_key": "attack"},
            ]
        },
    }
    e.update(kw)
    return orch.ensure_combat_sheet(e)


def _world(enemy):
    scene = cs.new_scene()
    for i in ("player", enemy["id"]):
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": _player(), enemy["id"]: enemy}
    sides = {"hero": ["player"], "ally": [], "enemy": [enemy["id"]]}
    return scene, actors, sides


def _decl(scene, actors, sides, eid, rnd):
    return orch.enemy_declaration(
        scene, eid, actors, sides, scene_state={"_rodada_decisao": rnd}, rng=random.Random(1)
    )


def _kind(card_id):
    return str(((cards.get_card(card_id) or {}).get("efeito") or {}).get("kind") or "")


# --- flag ---------------------------------------------------------------------
def test_flag_default_off_and_invalid(monkeypatch):
    assert edk.mode() == "off"
    monkeypatch.setenv("RPG_ENEMY_DECKS", "talvez")
    assert edk.mode() == "off"
    monkeypatch.setenv("RPG_ENEMY_DECKS", "ON")
    assert edk.active()


def test_off_leaves_cards_untouched():
    e = _enemy(cartas=["bst_bote_certeiro"])
    assert e["cartas"] == ["bst_bote_certeiro", "bst_defesa_instintiva"]
    assert "_deck332" not in e and "_deck_shadow" not in e


def test_off_declaration_is_first_usable_attack_card():
    e = _enemy(cartas=["bst_bote_certeiro"])
    scene, actors, sides = _world(e)
    d = _decl(scene, actors, sides, "lobo_1", 3)
    assert d.acao.card_id == "bst_bote_certeiro"


# --- R3: montagem determinística -------------------------------------------------
def test_deck_is_deterministic_and_keeps_own_cards_first(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    a = _enemy("lobo_1", cartas=["bst_bote_certeiro"])
    b = _enemy("lobo_1", cartas=["bst_bote_certeiro"])
    assert a["cartas"] == b["cartas"]
    assert a["cartas"][:2] == ["bst_bote_certeiro", "bst_defesa_instintiva"]
    fam = [c for c in a["cartas"] if c.startswith("inf_predador_")]
    assert 3 <= len(fam) <= 5
    assert len(set(a["cartas"])) == len(a["cartas"])
    sig = edk.family_signature(a)
    assert sig["carta"] in a["cartas"]


def test_deck_varies_by_id_and_seed(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    decks = {tuple(_enemy(f"lobo_{i}")["cartas"]) for i in range(1, 9)}
    assert len(decks) > 1
    base = {"id": "lobo_1", "arquetipo": "predador", "cartas": []}
    assert any(
        edk.build_enemy_deck(base, 0) != edk.build_enemy_deck(base, sd) for sd in range(1, 20)
    )
    assert edk.build_enemy_deck(base, 5) == edk.build_enemy_deck(base, 5)


def test_shadow_computes_without_using(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "shadow")
    e = _enemy(cartas=["bst_bote_certeiro"])
    assert e["cartas"] == ["bst_bote_certeiro", "bst_defesa_instintiva"]
    assert len(e["_deck_shadow"]) > len(e["cartas"])
    summ = edk.shadow_summary({"lobo_1": e}, {"enemy": ["lobo_1"]})
    assert summ["inimigos"] == 1 and summ["cartas_novas"] >= 3


def test_faction_pool_adds_zero_to_three(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    ids = [f"inf_predador_{s}" for s in ("rasgo_aberto", "fome_cega")]
    fake = {"familias": edk._pools()["familias"], "faccoes": {"legiao_ferro": ids}}
    monkeypatch.setattr(edk, "_pools", lambda: fake)
    got = edk.build_enemy_deck({"id": "x", "arquetipo": "guardiao", "faction": "legiao_ferro"}, 0)
    assert sum(1 for c in got if c in ids) <= 3
    assert len(got) == len(set(got))


# --- R4: padrão, precedência do perfil e assinatura ---------------------------------
def _custom(monkeypatch, padrao, assinatura=None, **kw):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    prof = {
        "priorities": [
            {"trigger": "muito_ferido", "tipo": "obrigatorio", "action_key": "flee"},
            {"trigger": "sempre", "tipo": "obrigatorio", "action_key": "attack"},
        ],
        "padrao": padrao,
    }
    if assinatura:
        prof["assinatura"] = assinatura
    e = _enemy(
        cartas=[
            "bst_bote_certeiro",
            "bst_teia",
            "bst_golpe_sombras",
            "bst_sangrar_alcateia",
        ],
        tactical_profile=prof,
        **kw,
    )
    return e, *_world(e)


def test_pattern_slots_choose_card_kinds_inside_the_deck(monkeypatch):
    e, scene, actors, sides = _custom(monkeypatch, ["ataque", "enfraquecer"])
    for rnd, want in ((1, "ataque"), (2, "enfraquecer"), (3, "ataque"), (4, "enfraquecer")):
        d = _decl(scene, actors, sides, "lobo_1", rnd)
        assert d.acao.kind == "card"
        kind = _kind(d.acao.card_id)
        assert (kind in edk._DAMAGE_KINDS) == (want == "ataque"), (rnd, d.acao.card_id)
        assert d.acao.card_id in cards.enemy_card_ids(e)


def test_pattern_attack_without_cards_is_basic_attack(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    e = _enemy(
        cartas=[],
        tactical_profile={
            "priorities": [{"trigger": "sempre", "action_key": "attack"}],
            "padrao": ["ataque"],
        },
        arquetipo="x_sem_familia",
    )
    scene, actors, sides = _world(e)
    assert _decl(scene, actors, sides, "lobo_1", 1).acao.kind == "attack"


def test_profile_trigger_takes_precedence_over_pattern(monkeypatch):
    e, scene, actors, sides = _custom(monkeypatch, ["enfraquecer"])
    e["vitalidade"] = 2  # muito_ferido -> o perfil manda fugir, nada de carta do padrão
    d = _decl(scene, actors, sides, "lobo_1", 2)
    assert d.acao.kind == "tactic" and d.acao.maneuver == "flee"


def test_signature_every_n_rounds_and_telegraph_one_round_before(monkeypatch):
    e, scene, actors, sides = _custom(
        monkeypatch,
        ["ataque"],
        {
            "carta": "bst_golpe_mestre",
            "a_cada_n": 3,
            "desvio": 0,
            "telegrafo": "{nome} range os dentes.",
        },
    )
    e["cartas"].append("bst_golpe_mestre")
    e["entropy"] = 10
    seen = {r: _decl(scene, actors, sides, "lobo_1", r).acao.card_id for r in range(1, 7)}
    assert seen[3] == "bst_golpe_mestre" and seen[6] == "bst_golpe_mestre"
    assert all(seen[r] != "bst_golpe_mestre" for r in (1, 2, 4, 5))
    assert edk.prenuncio(e, 2) == "Lobo Cinzento range os dentes."
    assert edk.prenuncio(e, 3) is None and edk.prenuncio(e, 1) is None
    frozen = ei.forecast_round(scene, actors, sides, random.Random(1))
    pub = ei.public_round(frozen, actors, 2)
    assert pub[0]["prenuncio"] == "Lobo Cinzento range os dentes."
    assert "prenuncio" not in ei.public_round(frozen, actors, 3)[0]


def test_public_round_is_unchanged_when_flag_off():
    e = _enemy(cartas=["bst_bote_certeiro"])
    scene, actors, sides = _world(e)
    frozen = ei.forecast_round(scene, actors, sides, random.Random(1))
    assert all("prenuncio" not in row for row in ei.public_round(frozen, actors, 2))


# --- R6: conhecimento ---------------------------------------------------------------
def test_known_pattern_only_after_family_was_seen(monkeypatch):
    e, *_ = _custom(monkeypatch, ["ataque", "ataque", "reforco_proprio"])
    from services import bestiary_knowledge as bk

    assert edk.padrao_publico(e) is None
    assert "costuma" not in bk.public_panel(e)
    e["revealed_cards"] = ["bst_bote_certeiro"]
    assert edk.padrao_publico(e).startswith("costuma: ataque, ataque, reforço")
    assert bk.public_panel(e)["costuma"].startswith("costuma:")


def test_known_pattern_hidden_when_flag_off():
    e = _enemy()
    e["revealed_cards"] = ["bst_bote_certeiro"]
    assert edk.padrao_publico(e) is None


# --- R1/R7: conteúdo ------------------------------------------------------------------
def _family_cards():
    out = {}
    for fam, ids in edk._pools()["familias"].items():
        out[fam] = [fx.materialize(cards.get_card(i)) for i in ids]
    return out


def test_eleven_families_with_8_to_12_cards_each():
    fams = _family_cards()
    assert set(fams) == set(edk.FAMILIAS)
    for fam, lst in fams.items():
        assert 8 <= len(lst) <= 12, fam


def test_new_enemy_cards_pass_vocabulary_budget_and_voice():
    bad = {}
    for lst in _family_cards().values():
        for c in lst:
            issues = card_lint.errors(
                card_lint.check_vocabulary(c) + card_lint.check_budget(c) + card_lint.check_voice(c)
            )
            if issues:
                bad[c["id"]] = [str(i) for i in issues]
    assert not bad, bad


def test_every_family_has_a_card_no_other_family_has_and_valid_signatures():
    by_id = collections.Counter()
    for lst in _family_cards().values():
        by_id.update(c["id"] for c in lst)
    assert all(n == 1 for n in by_id.values())
    meta = edk._meta()["familias"]
    for fam in edk.FAMILIAS:
        sigs = meta[fam]["assinaturas"]
        assert len(sigs) >= 2 and meta[fam]["padrao"]
        for s in sigs:
            assert s["carta"] in edk._pools()["familias"][fam]
            assert s["a_cada_n"] >= 2 and "{nome}" in s["telegrafo"]


def test_no_new_card_used_by_more_than_15_bestiary_creatures(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    from agents.bestiary import load_bestiary

    use = collections.Counter()
    for bid, entry in load_bestiary().items():
        deck = edk.build_enemy_deck({**entry, "id": bid}, 0)
        use.update(c for c in deck if c.startswith("inf_"))
    assert use and max(use.values()) <= 15, use.most_common(3)


def test_enemy_cards_never_call_reinforcements():
    # o dono descartou reforços (SPEC-325 D): nenhuma carta/fase invoca aliados
    for lst in _family_cards().values():
        for c in lst:
            blob = json.dumps(c, ensure_ascii=False).lower()
            assert "reforco" not in blob and "reforço" not in blob


def test_support_profile_keeps_character_only_signature_overrides(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    e = _enemy(
        cartas=["bst_bote_certeiro", "bst_golpe_mestre"],
        entropy=10,
        tactical_profile={
            "priorities": [{"trigger": "sempre", "tipo": "obrigatorio", "action_key": "support"}],
            "padrao": ["ataque"],
            "assinatura": {"carta": "bst_golpe_mestre", "a_cada_n": 3, "desvio": 0},
        },
    )
    scene, actors, sides = _world(e)
    # sem aliado para apoiar o perfil cai em ataque basico/carta; so a assinatura e imposta
    assert _decl(scene, actors, sides, "lobo_1", 3).acao.card_id == "bst_golpe_mestre"
    assert _decl(scene, actors, sides, "lobo_1", 4).acao.card_id != "bst_golpe_mestre"
