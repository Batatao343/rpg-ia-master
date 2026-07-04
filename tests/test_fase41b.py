"""
Fase 4.1b — Árvores de Valoria: validação de CONTEÚDO (autoria Fable).
Schema básico é coberto por test_fase41.py; aqui valida estrutura das árvores.
"""
import json
import os
import re

import pytest

from gamedata import ABILITIES, CLASSES

GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "graph", "entities.json")

with open(GRAPH_PATH, encoding="utf-8") as f:
    _ENTITIES = json.load(f)


def _branch_abilities(cname: str, branch_id: str):
    return [aid for aid, a in ABILITIES.items()
            if a.get("branch") == branch_id and cname in (a.get("classes") or [])]


def _trunk_abilities(cname: str):
    return [aid for aid, a in ABILITIES.items()
            if a.get("branch") is None and cname in (a.get("classes") or [])]


def test_toda_classe_tem_2_ramos():
    for cname, c in CLASSES.items():
        branches = c.get("branches") or {}
        assert len(branches) == 2, f"{cname}: {len(branches)} ramos (esperado 2)"


def test_ramo_tem_theme():
    for cname, c in CLASSES.items():
        for bid, b in (c.get("branches") or {}).items():
            assert str(b.get("theme", "")).strip(), f"{cname}/{bid}: theme vazio"
            assert str(b.get("name", "")).strip(), f"{cname}/{bid}: name vazio"
            assert str(b.get("identity", "")).strip(), f"{cname}/{bid}: identity vazia"


def test_lore_ref_quando_presente_resolve_no_grafo():
    for cname, c in CLASSES.items():
        for bid, b in (c.get("branches") or {}).items():
            ref = b.get("lore_ref")
            if ref:
                assert ref in _ENTITIES, f"{cname}/{bid}: lore_ref {ref!r} não resolve"


def test_ramo_tem_4_mais_habilidades():
    for cname, c in CLASSES.items():
        for bid in (c.get("branches") or {}):
            abl = _branch_abilities(cname, bid)
            assert len(abl) >= 4, f"{cname}/{bid}: só {len(abl)} habilidades"


def test_tronco_tem_3_mais_habilidades():
    for cname in CLASSES:
        trunk = [a for a in _trunk_abilities(cname)
                 if "all" not in (ABILITIES[a].get("classes") or [])]
        assert len(trunk) >= 3, f"{cname}: tronco com {len(trunk)}"


def test_sem_habilidade_so_texto():
    """R4: toda habilidade tem efeito que o motor resolve OU effects tipado."""
    for aid, a in ABILITIES.items():
        formula = str(a.get("damage_formula", "0")).strip()
        has_damage = formula not in ("", "0")
        has_cond = bool(a.get("conditions"))
        has_effects = bool(a.get("effects"))
        is_heal = str(a.get("damage_type", "")).lower() in ("cura", "heal")
        assert has_damage or has_cond or has_effects or is_heal, \
            f"{aid}: habilidade só-texto (sem dano/condição/effects/cura)"


def test_requires_dentro_do_mesmo_ramo_ou_tronco():
    for aid, a in ABILITIES.items():
        for r in a.get("requires") or []:
            req = ABILITIES[r]
            rb, ab = req.get("branch"), a.get("branch")
            assert rb is None or rb == ab, \
                f"{aid} ({ab}) requer {r} de ramo diferente ({rb})"


def test_cadeia_de_tiers_no_ramo():
    """Tier 3 de ramo sempre exige algo do ramo (assinatura no fim da cadeia)."""
    for aid, a in ABILITIES.items():
        if a.get("branch") and a.get("tier") == 3:
            assert a.get("requires"), f"{aid}: tier 3 de ramo sem requires"


def test_distribuicao_minima_por_ramo():
    """Guard-rail anti-monotonia: dano com escala, save_stat e effects por ramo."""
    for cname, c in CLASSES.items():
        for bid in (c.get("branches") or {}):
            abl = [ABILITIES[a] for a in _branch_abilities(cname, bid)]
            has_scaling = any(str(x.get("scaling_formula", "0")) not in ("", "0")
                              and re.search(r"\dd\d", str(x.get("damage_formula", "")))
                              for x in abl)
            has_save = any(x.get("save_stat") for x in abl)
            has_effects = any(x.get("effects") for x in abl)
            assert has_scaling, f"{cname}/{bid}: sem dano com escala"
            assert has_save, f"{cname}/{bid}: sem habilidade com save"
            assert has_effects, f"{cname}/{bid}: sem buff/controle tipado"


def test_starting_abilities_pertencem_a_classe():
    """Pós-4.1b: starting deixou de ser ['all'] provisório — pertence à classe."""
    for cname, c in CLASSES.items():
        for aid in c.get("starting_abilities") or []:
            classes = ABILITIES[aid].get("classes") or []
            assert cname in classes or "all" in classes, \
                f"{cname}: starting {aid} não pertence à classe"


def test_universais_continuam_all():
    for aid in ("ataque_basico", "improvisado"):
        if aid in ABILITIES:
            assert ABILITIES[aid].get("classes") == ["all"], f"{aid} deve ser all"
