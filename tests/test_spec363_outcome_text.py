"""SPEC-363 R6-R10, R13, R14, R15, R17, R18: texto de morte e resumo final."""

from __future__ import annotations

import pytest

from services import conflict_summary as cs
from services import round_log
from tests.fixtures import spec363_smoke as fx

SUMMARY = {
    "participantes": ["Smoke3A", "Goblin", "Minotauro Esqueleto"],
    "mortos": ["Goblin"],
    "caidos": ["Smoke3A"],
    "inconscientes": ["Smoke3A"],
}
LAST_OUT = {
    "final_blows": [{"target_id": "player", "kind": "ataque", "by_actor_id": "enemy_mino"}],
    "terminal": ["player"],
}
NAMES = {"enemy_mino": "Minotauro Esqueleto", "enemy_goblin": "Goblin"}


def test_no_digits_keeps_names():
    assert round_log._no_digits("Smoke3A cai. Bandido 2 foge com 3 de dano.", ["Smoke3A", "Bandido 2"]) == (
        "Smoke3A cai. Bandido 2 foge com de dano."
    )
    assert round_log._no_digits("Smoke3A tem 3 pontos", None) == "SmokeA tem pontos"


def test_fallback_never_names_hero_and_keeps_digit_names():
    text = round_log.deterministic_outcome_text(
        "death", SUMMARY, fx.PLAYER, last_out=LAST_OUT, names=NAMES
    )
    assert "Smoke3A" not in text and "SmokeA" not in text
    assert text.startswith("Você tomba diante de Minotauro Esqueleto.")
    assert text.count("Você tomba") == 1


def test_old_falls_in_past_tense():
    text = round_log.deterministic_outcome_text(
        "death", SUMMARY, fx.PLAYER, last_out=LAST_OUT, names=NAMES
    )
    assert "Antes, Goblin já tinha tombado." in text
    assert "Goblin tomba" not in text
    assert text.index("Antes") < text.index("Você carrega")


def test_player_summary_one_category_per_name():
    body = cs.player_summary_text({"mortos": ["A"], "caidos": ["A", "B"], "inconscientes": ["A", "B", "C"]})
    assert body.count("A ") + body.count("A.") >= 1
    assert body == "A tomba. B cai. C perde os sentidos."
    canon = cs.canonical_summary_text({"caidos": ["B"], "inconscientes": ["B"]})
    assert canon.count("B") == 1


def test_summary_data_untouched():
    s = {"caidos": ["B"], "inconscientes": ["B"]}
    cs.player_summary_text(s)
    assert s == {"caidos": ["B"], "inconscientes": ["B"]}


def test_wound_has_bearer_in_facts():
    atk = {"acerto": True, "resultado": "acerto", "target_id": "enemy_mimic", "ferimento": {"categoria": "leve", "regiao": "braco"}}
    assert round_log._event_result(atk, "Mímico") == "acertou, ferimento leve no braço do Mímico"
    hero = {**atk, "target_id": "player"}
    assert round_log._event_result(hero, "Você") == "acertou, ferimento leve no seu braço"
    assert "na sua perna" in round_log._owned_region("perna", "player", "Você")


def _auth(player):
    return round_log.authorship({}, {"player": "Você"}, player)


def test_v4_rejects_mimic_text_and_accepts_correct():
    auth = _auth(fx.HERO_UNHURT)
    assert "V4" in cs.validate_attribution(fx.MIMIC_BAD, auth)
    assert "V4" not in cs.validate_attribution(fx.MIMIC_GOOD, auth)
    # com ferimento real no braço do herói, a mesma frase passa
    hurt = {**fx.HERO_UNHURT, "vitalidade": 10, "ferimentos": {"leve": [{"regiao": "braco_esquerdo"}]}}
    assert "V4" not in cs.validate_attribution("O sangue escorre pelo seu braço.", _auth(hurt))


def test_v5_rejects_ilsa_text():
    assert "V5" in cs.validate_attribution(fx.ILSA_BAD, {})
    assert "V5" not in cs.validate_attribution(fx.ILSA_GOOD, {})


def test_v4_v5_ignore_when_no_hero_info():
    assert cs.validate_attribution(fx.MIMIC_BAD, {}) == []


def test_death_fixture_bad_and_good():
    # o texto ruim do staging tem o nome do herói mutilado e Goblin no mesmo instante
    assert "SmokeA" in fx.DEATH_BAD and "Goblin tomba" in fx.DEATH_BAD
    produced = round_log.deterministic_outcome_text("death", SUMMARY, fx.PLAYER, last_out=LAST_OUT, names=NAMES)
    assert produced == fx.DEATH_GOOD


def test_weapon_name_from_catalog():
    from gamedata import ARTIFACTS_DB

    some = next(iter(ARTIFACTS_DB))
    assert round_log._weapon_name({"equipment": {"weapon": some}}) == ARTIFACTS_DB[some].get("name", some)
    assert round_log._weapon_name({"equipment": {"weapon": "arma_que_nao_existe"}}) == "a arma"
    assert round_log._weapon_name({"equipment": {"weapon": "Espada Velha"}}) == "Espada Velha"


def test_fall_after_cause_last_stand():
    out = {
        "deaths": ["g1"],
        "attacks": [
            {"actor_id": "player", "target_id": "g1", "label": "Última Ação", "acerto": True, "resultado": "acerto"}
        ],
    }
    lines = round_log.round_registry(out, {"player": {"is_player": True, "name": "H"}, "g1": {"name": "Goblin"}}, [])
    joined = "\n".join(lines)
    assert joined.index("Última Ação") < joined.index("Goblin morre.")


def test_currency_loot_becomes_gold():
    import random

    from services import economy

    for seed in range(300):
        for danger in (1, 3, 5):
            roll = economy.roll_loot("default", danger, random.Random(seed))
            if roll["item_id"]:
                kind = str(economy.ARTIFACTS_DB[roll["item_id"]].get("type", "")).lower()
                assert kind != "currency"


# --- R13/R14: rastro da rejeição e matador = golpe final --------------------------------------
def _run_outcome(monkeypatch, text, player, summary=None, last_out=None):
    import agents.combat as combat
    from tests.test_spec346_outcome import _install

    _install(monkeypatch, text=text)
    events: list = []
    monkeypatch.setattr(combat, "_log_event", lambda *a, **k: events.append((a, k)))
    sink: dict = {}
    out = combat._narrate_outcome(
        "victory", summary or {"mortos": ["Mímico"]}, player, [], last_out or {}, "ataco", "",
        manifest=None, source_sink=sink,
    )
    return out, sink, events


def test_narrative_rejection_emits_event_and_source(monkeypatch):
    # contradição explícita com o motor: o Mímico "sobrevive" mas morreu
    out, sink, events = _run_outcome(
        monkeypatch, "O Mímico sobrevive e foge pelo corredor escuro, ileso.", fx.HERO_UNHURT
    )
    assert sink["last_outcome_source"] == "fallback_narrative"
    assert any(a[1] == "outcome_narrative_rejected" for a, _ in events)
    assert "sobrevive" not in out


def test_attribution_rejection_sets_source(monkeypatch):
    out, sink, events = _run_outcome(
        monkeypatch, fx.ILSA_BAD, fx.HERO_UNHURT, summary={"mortos": ["Mímico"]}
    )
    assert sink["last_outcome_source"] == "fallback_attribution"
    assert any(a[1] == "outcome_attribution_rejected" for a, _ in events)
    assert "cajado" not in out


def test_good_text_sets_llm_source(monkeypatch):
    out, sink, _ = _run_outcome(monkeypatch, fx.ILSA_GOOD, fx.HERO_UNHURT)
    assert sink["last_outcome_source"] == "llm" and out == fx.ILSA_GOOD


@pytest.mark.parametrize(
    "blow,expected",
    [
        ({"target_id": "player", "kind": "ataque", "by_actor_id": "e2"}, "Minotauro"),
        ({"target_id": "player", "kind": "dano_continuo", "by_actor_id": None, "condition": "Sangramento"}, "Sangramento"),
        ({"target_id": "player", "kind": "auto_dano", "by_actor_id": None}, "o preço da própria Carta"),
    ],
)
def test_killer_from_final_blows(blow, expected):
    import agents.combat as combat

    e1 = {"id": "e1", "name": "Goblin"}
    e2 = {"id": "e2", "name": "Minotauro Esqueleto"}
    killer = combat._killer_identity([e1, e2], {"final_blows": [blow]}, [e1, e2])[0]
    assert expected in killer
    # sem final_blows (save antigo): regra de antes (primeiro ativo)
    old = combat._killer_identity([e1, e2], {}, [e1, e2])[0]
    assert "Minotauro" not in old


# --- revisão Sol: P1-1 (V4 sem falso positivo), P2-1 (condição sem id/artigo), P3-1/P3-3 --------------
BENIGN = [
    "Você ergue seu braço e a lâmina desce sobre o Mímico.",
    "Com o peso do seu ombro, você empurra o Goblin contra a parede.",
    "Você firma sua perna no chão e respira fundo.",
    "O coração bate forte no seu peito enquanto o Mímico recua.",
    "Você cerra o punho, a sua cabeça erguida diante do baú.",
    "Seu braço firme segura o escudo e o Mímico foge.",
    "Você gira o seu corpo e golpeia o Goblin, que tomba.",
    "Sua perna não treme; você avança sobre o Mímico.",
    "O sangue do Mímico mancha o chão, e você segue ileso.",
    "Você sente o seu peito encher de ar quando o silêncio volta.",
    "Seu ombro relaxa: a luta acabou.",
    "Seu braço acerta o Goblin em cheio e ele recua.",
    "O sangue do Goblin respinga no seu braço, mas você segue ileso.",
    "A lâmina rasga o ar onde estava sua cabeça um instante antes.",
    "O Mímico fere o ar vazio, e você desvia com a sua perna esquerda firme.",
]


@pytest.mark.parametrize("text", BENIGN)
def test_v4_never_fires_on_benign_prose(text):
    auth = round_log.authorship({}, {"player": "Você"}, fx.HERO_UNHURT)
    assert "V4" not in cs.validate_attribution(text, auth), text


def test_v4_still_rejects_mimic_bad_and_wound_without_fact():
    auth = round_log.authorship({}, {"player": "Você"}, fx.HERO_UNHURT)
    assert "V4" in cs.validate_attribution(fx.MIMIC_BAD, auth)
    assert "V4" in cs.validate_attribution("A lâmina rasga o seu braço.", auth)


def test_dot_killer_uses_label_without_gender_article():
    import agents.combat as combat

    for raw in ("veneno_fraco", "queimadura"):
        blow = {"target_id": "player", "kind": "dano_continuo", "by_actor_id": None, "condition": raw}
        killer = combat._killer_identity([], {"final_blows": [blow]}, [])[0]
        assert "_" not in killer and not killer.startswith("o "), killer
        text = round_log.deterministic_outcome_text(
            "death", {}, {"name": "H"}, last_out={"final_blows": [blow]}, names={}
        )
        assert "_" not in text and "pelo " not in text and "consumido por " in text, text
        assert "_" not in combat._narrate_fall({"name": "H"}, [], killer)


def test_source_always_set_and_fresh(monkeypatch):
    import agents.combat as combat
    from tests.test_spec346_outcome import _install

    _install(monkeypatch, text="qualquer prosa")
    from services import prose_guard

    monkeypatch.setattr(prose_guard, "strip_mechanic_numbers", lambda t: ("", 3))  # o filtro esvazia o texto
    sink = {"last_outcome_source": "llm"}  # valor velho de conflito anterior
    combat._narrate_outcome(
        "victory", {"mortos": ["Mímico"]}, fx.HERO_UNHURT, [], {}, "ataco", "", manifest=None, source_sink=sink
    )
    assert sink["last_outcome_source"] == "fallback_narrative"


def test_rejection_event_logs_codes_not_sentences(monkeypatch):
    _out, _sink, events = _run_outcome(
        monkeypatch, "O Mímico sobrevive e foge pelo corredor escuro, ileso.", fx.HERO_UNHURT
    )
    ev = next(k for a, k in events if a[1] == "outcome_narrative_rejected")
    assert ev["codes"] == "dead_alive" and "Mímico" not in ev["codes"]


def test_dot_sentence_capitalized_without_condition():
    last = {"final_blows": [{"target_id": "e1", "kind": "dano_continuo", "by_actor_id": None, "condition": None}]}
    sentence = round_log.final_blow_sentence(last, {"player": "Você", "e1": "Goblin"})
    assert sentence[0].isupper() and sentence.startswith("Dano contínuo termina o serviço"), sentence
    with_cond = round_log.final_blow_sentence(
        {"final_blows": [{**last["final_blows"][0], "condition": "sangramento"}]}, {"e1": "Goblin"}
    )
    assert with_cond[0].isupper(), with_cond
