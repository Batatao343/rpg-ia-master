"""SPEC-387 R21-R25: seeds determinísticas dos "não verificado" — save -> load -> /game/state e uma
rodada do motor (MockLLM) com o resultado prometido em 50/50 sementes de `random`."""

from __future__ import annotations

import pytest

import agents.combat as combat
import persistence
from services import round_log
from tests.fixtures import spec368_seed as sd
from tests.fixtures.spec387_rounds import load, play, step_card

SEEDS = range(50)
G = "bas_san_golpe"

NEW_VARIANTS = [
    (2, "frustrar"),
    (3, "eco"),
    (3, "inelegivel"),
    (3, "rachadura"),
    (5, "chefe_fase"),
    (13, "voto"),
    (13, "reacao"),
    (13, "armadura"),
    (13, "condicao_carta"),
    (14, "entrega"),
    (15, "vg_ouro"),
]


@pytest.fixture(scope="module")
def saves(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spec387_saves"))


@pytest.fixture(scope="module")
def seeded(saves):
    """(item, variante) -> (game_id, estado carregado); cada save é gravado 1× por módulo."""
    cache: dict = {}

    def get(item: int, variant: str = ""):
        if (item, variant) not in cache:
            cache[(item, variant)] = load(item, variant, saves)
        return cache[(item, variant)]

    return get


def _all_seeds(saves, state, steps, check, **kw):
    with sd._legacy(saves):
        for seed in SEEDS:
            out, text, raw = play(state, steps, seed, **kw)
            check(out, text, raw, seed)


def _enemy(state):
    return state["enemies"][0]["id"]


@pytest.mark.parametrize(("item", "variant"), NEW_VARIANTS)
def test_save_load_state_shows_the_scene(saves, seeded, item, variant):
    gid, st = seeded(item, variant)
    if item in (14, 15):
        assert not (st.get("combat") or {}).get("active")
        return
    v = sd.view(gid, saves)
    assert v["combat"]["active"] and v["combat"]["pilhas"]["mao"]
    assert v["combat"]["enemies"]


def test_frustrar_shows_the_frustrated_omen(saves, seeded):
    _, st = seeded(2, "frustrar")
    steps = [step_card("arc1_des_estouro_contido", _enemy(st))]

    def check(out, text, raw, seed):
        frustrated = raw.get("pressagios_frustrados") or []
        assert frustrated and frustrated[0]["actor_id"] == _enemy(st), seed

    _all_seeds(saves, st, steps, check)


def test_eco_hits_and_the_enemy_survives(saves, seeded):
    _, st = seeded(3, "eco")
    steps = [step_card(G, _enemy(st)), step_card("san1_exp_segundo_ato", _enemy(st))]

    def check(out, text, raw, seed):
        line = next(ln for ln in text.splitlines() if "Segundo Ato" in ln)
        assert "Acerta" in line or "Acerto" in line, (seed, line)
        assert not out["enemies"][0].get("dead"), seed

    _all_seeds(saves, st, steps, check)


def test_rachadura_applies_the_condition(saves, seeded):
    _, st = seeded(3, "rachadura")
    steps = [
        step_card("cor1_ino_junta_emperrada", _enemy(st)),
        step_card("bas_cor_golpe", _enemy(st)),
    ]

    def check(out, text, raw, seed):
        assert "Rachadura" in text and "Acerta" in text, seed

    _all_seeds(saves, st, steps, check)


def test_inelegivel_is_refused_without_cost(saves, seeded):
    _, st = seeded(3, "inelegivel")
    steps = [step_card("san1_exp_segundo_ato", _enemy(st))]

    def check(out, text, raw, seed):
        assert "não está no seu baralho." in text, seed
        assert "san1_exp_segundo_ato" in out["combat"]["pilhas"]["mao"], seed  # mão intacta
        assert out["combat"]["pilhas"]["folego"] == st["combat"]["pilhas"]["folego"], seed

    _all_seeds(saves, st, steps, check)


def test_escort_is_an_actor_and_does_not_fail_in_round_one(saves, seeded):
    _, st = seeded(4)
    assert st["party"][0]["id"] == "escoltado"
    assert (st["combat"]["scene"]["objetivo"] or {}) == {"tipo": "proteger", "alvo": "escoltado"}

    def check(out, text, raw, seed):
        assert not raw.get("objetivo"), seed
        assert out["combat"]["active"], seed

    _all_seeds(saves, st, [], check)


def test_escort_downed_fails_with_the_cause_and_the_hero_standing(saves, seeded, monkeypatch):
    _, st = seeded(4)
    st = {**st, "party": [{**st["party"][0], "dead": True, "status": "morto", "vitalidade": 0}]}
    monkeypatch.setattr(combat, "_fast_text", lambda *a, **k: "")  # cai no texto determinístico
    with sd._legacy(saves):
        out, text, raw = play(st, [], 3)
    assert raw["objetivo"]["resultado"] == "falhou"
    assert "O objetivo se perdeu: Escoltado não resistiu." in text
    assert "perde os sentidos" not in text and "Você tomba" not in text and "apaga" not in text


def test_boss_phase_line_shows_up(saves, seeded):
    _, st = seeded(5, "chefe_fase")
    steps = [step_card("bas_dev_golpe", _enemy(st))]

    def check(out, text, raw, seed):
        assert raw.get("fases"), seed

    _all_seeds(saves, st, steps, check)


def test_voto_redirects_or_resists(saves, seeded):
    _, st = seeded(13, "voto")
    assert st["combat"]["pressagios_publicos"][0]["alvo_id"] == "ketil"
    steps = [step_card("bas_dev_voto", _enemy(st))]

    def check(out, text, raw, seed):
        logs = " ".join(raw["logs"])
        assert "muda de alvo" in logs or "resiste" in logs, (seed, logs)

    _all_seeds(saves, st, steps, check)


def test_reacao_kills_and_the_summary_cites_the_author(saves, seeded):
    _, st = seeded(13, "reacao")
    guard = {"kind": "maneuver", "maneuver": "guardar", "target_id": None}

    def check(out, text, raw, seed):
        blows = [b for b in raw.get("final_blows") or [] if b.get("kind") == "reacao"]
        assert blows and blows[0]["by_actor_id"] == "player", seed
        sentence = round_log.final_blow_sentence(raw, {"player": "Você", _enemy(st): "Goblin"})
        assert "reação" in sentence and "Goblin" in sentence, (seed, sentence)

    _all_seeds(saves, st, [guard], check, reaction="dev_encaixe")


def test_armadura_comprometida_has_a_readable_name(saves, seeded):
    _, st = seeded(13, "armadura")
    assert st["enemies"][0]["id"].startswith("enemy_soldado_legiao_ferro")
    step = step_card("cor_ino_fadiga", _enemy(st))
    step["params"]["ruptura"] = True

    def check(out, text, raw, seed):
        assert "ganha a condição Armadura Comprometida." in text, (seed, text)
        assert "armadura_comprometida" not in text.lower(), seed

    _all_seeds(saves, st, [step], check)


def test_condicao_carta_is_applied_to_the_enemy(saves, seeded):
    _, st = seeded(13, "condicao_carta")
    steps = [step_card("neu1_er_lanca_de_gancho", _enemy(st))]

    def check(out, text, raw, seed):
        assert "ganha a condição Enredado." in text, seed

    _all_seeds(saves, st, steps, check)


def test_entrega_completes_the_quest_and_grants_the_card(seeded, monkeypatch):
    from services.event_processor import process_pending_events

    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    _, st = seeded(14, "entrega")
    assert st["world"]["current_location_id"] == "brekmar" and "Contratante" in st["npcs"]
    quest = next(q for q in st["quests"] if q["id"] == "q368")
    ev = {
        "type": "quest_completed",
        "actor_id": "player",
        "target_id": quest["id"],
        "payload": {"quest_id": quest["id"]},
        "source": "storyteller",
    }
    state = {**st, "pending_world_events": [ev]}
    state["player"] = {**st["player"], "level": 6}
    state["world"] = {**st["world"], "turn_count": 5}  # a quest do save nasce no turno 1
    out = process_pending_events(state)
    assert [c for c in out["player"]["known_cards"] if c.startswith("neu1_")]
    assert next(q for q in out["quests"] if q["id"] == "q368")["reward_card"]


def test_vg_ouro_leaves_a_final_balance_of_30(seeded):
    from services import card_shop

    _, st = seeded(15, "vg_ouro")
    mid, ids = card_shop.shelf(st)
    price = min(card_shop.card_price(st, c, card_shop.economy.MERCHANTS[mid]) for c in ids)
    assert st["player"]["gold"] - price == 30


def test_espolio_has_forja_and_esquecer_visible(saves):
    gid = sd.seed_save(6, variant="espolio", saves_dir=saves)
    with sd._legacy(saves):
        st = persistence.load_game_state(persistence.save_path(gid))
    assert st["player"]["forja_esquecer"] == 1 and st["player"].get("deck")
