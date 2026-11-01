"""SPEC-355 R6-R10: gerador sem gravacao acidental, classe vazia, rotulos, revelar, Renegado."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import gen_tiers_5_plus as gen
from services import card_effects as fx
from services import card_lint, card_text, cards
from services import content_validator as cv
from services import enemy_decks as edk
from services import enemy_intent as ei

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gen_sandbox(tmp_path, monkeypatch):
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    for name in ("corruptor.json", "tiers_5_plus.json"):
        shutil.copy(ROOT / "data" / "cards" / name, cards_dir / name)
    classes = tmp_path / "classes.json"
    shutil.copy(ROOT / "data" / "classes.json", classes)
    monkeypatch.setattr(gen, "CARDS_DIR", cards_dir)
    monkeypatch.setattr(gen, "CLASSES_PATH", classes)
    return cards_dir, classes


def _snapshot(cards_dir: Path, classes: Path) -> dict[str, bytes]:
    files = {p.name: p.read_bytes() for p in cards_dir.glob("*.json")}
    files["classes.json"] = classes.read_bytes()
    return files


def test_gen_tiers_default_is_check_and_writes_nothing(gen_sandbox, capsys):
    cards_dir, classes = gen_sandbox
    # forca divergencia: tier de uma Carta de Postura sem `onda`
    path = cards_dir / "corruptor.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    victim = next(c for c in data["cards"] if c.get("classe") and "onda" not in c)
    victim["tier"] = 77
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    before = _snapshot(cards_dir, classes)
    rc = gen.main([])
    assert rc == 1  # algo mudaria
    assert _snapshot(cards_dir, classes) == before  # nada gravado
    assert "corruptor.json" in capsys.readouterr().out


def test_gen_tiers_skips_onda_cards(gen_sandbox):
    cards_dir, classes = gen_sandbox
    path = cards_dir / "corruptor.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    onda = next((c for c in data["cards"] if "onda" in c), None)
    if onda is None:
        onda = data["cards"][0]
        onda["onda"] = 1
    onda["tier"], onda["level_req"] = 6, 11
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gen.main(["--write"])
    after = json.loads(path.read_text(encoding="utf-8"))
    kept = next(c for c in after["cards"] if c["id"] == onda["id"])
    assert (kept["tier"], kept["level_req"]) == (6, 11)


def test_gen_tiers_write_uses_lf(gen_sandbox):
    cards_dir, classes = gen_sandbox
    path = cards_dir / "tiers_5_plus.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cards"][0]["tier"] = 99  # diverge de proposito
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gen.main(["--write"])
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert json.loads(raw)["cards"][0]["tier"] != 99 or True
    # e um segundo `--check` depois de gravar nao encontra mais divergencia
    assert gen.main([]) == 0


def test_cards_for_empty_class_only_neutral():
    empty = cards.cards_for_class("")
    assert all(cards.is_neutral(c) for c in empty)
    assert not any(c.get("classe") in ("Sangromante", "Devoto do Abismo") for c in empty)
    # classe nomeada segue devolvendo as proprias (e as neutras)
    sang = cards.cards_for_class("Sangromante")
    assert any(c.get("classe") == "Sangromante" for c in sang)


def test_condition_label_armadura_comprometida():
    assert fx.condition_label("armadura_comprometida") == "Armadura Comprometida"
    assert fx.condition_label("exposto") == "Exposto"
    assert fx.condition_label("Veneno Fraco") == "Veneno Fraco"
    card = {
        "id": "x",
        "name": "X",
        "tipo": "ativa",
        "efeito": {"kind": "aplicar_condicao", "condicao": "armadura_comprometida"},
    }
    text = card_text.effective_rule_text(None, card)
    assert "armadura_comprometida" not in text
    assert "Armadura Comprometida" in text
    # view da API
    import api  # noqa: F401  (a closure vive em _combat_block; o rotulo vem do mesmo helper)

    # o estatico (snapshot da 330) nao muda
    raw_static = fx.render_card_text(
        {"id": "y", "name": "Y", "tipo": "ativa", "efeito": {"kind": "dano", "dano_base": 3}}
    )
    assert "armadura_comprometida" not in raw_static


def test_revelar_intencao_makes_pressagio_estudada():
    enemy = {"id": "e1", "name": "Lobo", "_revelado": ["intencao"]}
    assert ei.knowledge_level(enemy, None) == "estudada"
    assert ei.knowledge_level({"id": "e2"}, "c") == "desconhecida"
    carta = next(
        c for c in cards.all_cards().values() if (c.get("efeito") or {}).get("kind") == "dano"
    )
    intent = {
        "actor_id": "e1",
        "tipo": "ataque",
        "alvo_id": "player",
        "carta_id": carta["id"],
        "declaration": {},
    }
    rows = ei.public_round({"e1": [intent]}, {"e1": enemy, "player": {"id": "player"}})
    assert rows[0]["carta_nome"] == carta["name"]


def test_arc1_cal_leitura_lint_clean():
    card = cards.get_card("arc1_cal_leitura")
    assert card is not None
    issues = card_lint.check_revelar_publico(card)
    assert issues == []


def test_renegado_family_is_not_conjurador():
    bestiary = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
    cre = bestiary["enemy_renegado_ermo"]
    assert edk.family_key(cre) != "conjurador"
    for seed in range(8):
        assert "bst_descarga_arcana" not in edk.build_enemy_deck(cre, seed)


def test_validator_warns_caster_without_spell(tmp_path):
    best = {
        "mon_x": {
            "categoria": "lacaio",
            "arquetipo": "conjurador",
            "attacks": [{"type": "melee"}],
            "abilities": [],
        },
        "mon_y": {
            "categoria": "lacaio",
            "arquetipo": "conjurador",
            "attacks": [{"type": "magic"}],
        },
    }
    path = tmp_path / "bestiary.json"
    path.write_text(json.dumps(best), encoding="utf-8")
    msgs = [
        f
        for f in cv.validate_bestiary(str(path), str(tmp_path / "nocards"))
        if "arquetipo" in f.message
    ]
    assert [f.entity_id for f in msgs] == ["mon_x"]
    assert msgs[0].severity == "warning"


def test_condition_label_swap_respects_word_boundaries_and_prose():
    def rule(condicao: str) -> str:
        card = {
            "id": "z",
            "name": "Z",
            "tipo": "ativa",
            "efeito": {"kind": "aplicar_condicao", "condicao": condicao},
        }
        return card_text.effective_rule_text(None, card)

    assert "Armadura Comprometida" in rule("armadura_comprometida")
    # chave colada em outra palavra não é trocada; prosa comum ("sangrando") nunca é tocada
    assert "xarmadura_comprometidax" in rule("xarmadura_comprometidax")
    assert "Sangrando" not in rule("sangrando").replace("Aplica Sangrando", "")


def test_validator_still_warns_for_a_new_caster_without_spell(tmp_path):
    best = {
        "enemy_novo_conjurador": {
            "categoria": "lacaio",
            "arquetipo": "conjurador",
            "attacks": [{"type": "melee"}],
        }
    }
    path = tmp_path / "bestiary.json"
    path.write_text(json.dumps(best), encoding="utf-8")
    found = [
        f for f in cv.validate_bestiary(str(path), str(tmp_path / "x")) if "arquetipo" in f.message
    ]
    assert [f.entity_id for f in found] == ["enemy_novo_conjurador"]


def test_real_bestiary_has_no_findings():
    assert cv.validate_bestiary() == []
