"""Critérios executáveis da spec conflito-17 (volume do mundo vivo)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from services.codex_loader import parse_codex_file
from services.content_validator import (
    creature_signature,
    effect_signature,
    validate_all,
)


ROOT = Path(__file__).resolve().parents[1]
CLASS_FILES = ("devoto", "sangromante", "corruptor", "arcanista", "medico")
HUB_REGIONS = {
    "nova_arcadia", "pantano_melancolia", "deserto_zhur",
    "floresta_sussurros", "selva_xylos", "skallgard", "aethelgard",
    "ophidia", "costa_negra", "montanhas_afiadas", "pradaria_ruinas",
    "brekmar",
}


def _cards(slug: str) -> list[dict]:
    data = json.loads((ROOT / "data" / "cards" / f"{slug}.json").read_text("utf-8"))
    return data["cards"]


def _bestiary() -> dict[str, dict]:
    return json.loads((ROOT / "data" / "bestiary.json").read_text("utf-8"))


def _volume_npcs() -> list[tuple[Path, dict, str]]:
    found = []
    for path in (ROOT / "data" / "codex" / "npcs" / "mundo_vivo").glob("*.md"):
        fm, body = parse_codex_file(str(path))
        found.append((path, fm, body))
    return found


def test_relatorio_de_cobertura_roda(capsys):
    from scripts.content_report import main

    assert main() == 0
    out = capsys.readouterr().out
    assert "CARTAS POR CLASSE/SUBCLASSE/PATAMAR" in out
    assert "CRIATURAS POR REGIÃO/CATEGORIA/ARQUÉTIPO" in out
    assert "NPCS POR REGIÃO" in out


def test_cartas_em_escala_por_combo_tipo_e_total():
    all_cards = [card for slug in CLASS_FILES for card in _cards(slug)]
    assert len(all_cards) >= 150

    classes = {c["classe"] for c in all_cards}
    for classe in classes:
        class_cards = [c for c in all_cards if c["classe"] == classe]
        subclasses = {c["subclasse"] for c in class_cards if c.get("subclasse")}
        assert len(subclasses) == 3
        for subclass in subclasses:
            own = [c for c in class_cards if c.get("subclasse") == subclass]
            assert len(own) >= 5, (classe, subclass, len(own))
            assert any(c.get("patamar") == "superior" for c in own), (classe, subclass)

        added = [c for c in class_cards if c.get("origem") == "conflito-17"]
        types = Counter(c.get("tipo") for c in added)
        assert types["reacao"] >= 2, classe
        assert types["utilitaria"] >= 2, classe


def test_cartas_inimigas_e_variedade_sem_duplicata_pura():
    enemy = _cards("bestiario")
    assert len(enemy) >= 40

    for slug in (*CLASS_FILES, "bestiario"):
        seen: dict[tuple, str] = {}
        for card in _cards(slug):
            if card.get("tipo") != "ativa":
                continue
            sig = effect_signature(card)
            previous = seen.get(sig)
            assert previous is None, (slug, previous, card["id"], sig)
            seen[sig] = card["id"]


def test_bestiario_em_escala_cobertura_e_variedade():
    best = _bestiary()
    assert len(best) >= 120
    added = {cid: c for cid, c in best.items() if c.get("origem") == "conflito-17"}
    assert len(added) >= 40

    by_region: dict[str, list[dict]] = defaultdict(list)
    for creature in best.values():
        for region in creature.get("regions") or []:
            by_region[region].append(creature)
    for region in HUB_REGIONS:
        creatures = by_region[region]
        categories = {c.get("categoria") for c in creatures}
        assert len(creatures) >= 6, (region, len(creatures))
        assert "lacaio" in categories, region
        assert categories & {"elite", "chefe"}, region

    signatures: dict[tuple, str] = {}
    for cid, creature in added.items():
        assert set(creature.get("regions") or []) <= HUB_REGIONS
        assert creature.get("description") and creature.get("cartas")
        sig = creature_signature(creature)
        previous = signatures.get(sig)
        assert previous is None, (previous, cid, sig)
        signatures[sig] = cid


def test_npcs_nomeados_por_regiao_e_lint_global():
    npcs = _volume_npcs()
    assert len(npcs) >= 30
    by_region = Counter(fm.get("home_location_id") for _p, fm, _b in npcs)
    for region in HUB_REGIONS:
        assert by_region[region] >= 3, (region, by_region[region])
    for _path, fm, body in npcs:
        assert fm.get("curated") is True
        assert fm.get("role") and fm.get("faction")
        assert "Gancho:" in body
    errors = [f for f in validate_all() if f.severity == "error"]
    assert errors == []
