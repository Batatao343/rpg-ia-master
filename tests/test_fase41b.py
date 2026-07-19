"""
Árvores das 5 Posturas — validação ESTRUTURAL da árvore MÍNIMA jogável
(spec refatoracao-sistema-classes, etapa 5). A árvore RICA (passivas/utilitárias,
~100 habilidades) é a spec #2 `arvores-habilidade-classes`, autorada em Fable —
quando ela chegar, esta suíte volta a exigir ramos densos.
"""
from gamedata import ABILITIES, CLASSES


def _branch_abilities(cname: str, branch_id: str):
    return [aid for aid, a in ABILITIES.items()
            if a.get("branch") == branch_id and cname in (a.get("classes") or [])]


def _trunk_abilities(cname: str):
    return [aid for aid, a in ABILITIES.items()
            if a.get("branch") is None and cname in (a.get("classes") or [])]


def test_cada_classe_tem_3_ramos():
    for cname, c in CLASSES.items():
        branches = c.get("branches") or {}
        assert len(branches) == 3, f"{cname}: {len(branches)} ramos (esperado 3)"


def test_ramo_tem_nome_e_identity():
    for cname, c in CLASSES.items():
        for bid, b in (c.get("branches") or {}).items():
            assert str(b.get("name", "")).strip(), f"{cname}/{bid}: name vazio"
            assert str(b.get("identity", "")).strip(), f"{cname}/{bid}: identity vazia"


def test_ramo_tem_ao_menos_1_habilidade():
    for cname, c in CLASSES.items():
        for bid in (c.get("branches") or {}):
            abl = _branch_abilities(cname, bid)
            assert len(abl) >= 1, f"{cname}/{bid}: sem habilidade"


def test_tronco_tem_ao_menos_2_habilidades():
    for cname in CLASSES:
        trunk = [a for a in _trunk_abilities(cname)
                 if "all" not in (ABILITIES[a].get("classes") or [])]
        assert len(trunk) >= 2, f"{cname}: tronco com {len(trunk)}"


def test_sem_habilidade_so_texto():
    """Toda habilidade tem efeito que o motor resolve OU effects tipado."""
    for aid, a in ABILITIES.items():
        formula = str(a.get("damage_formula", "0")).strip()
        has_damage = formula not in ("", "0")
        has_cond = bool(a.get("conditions"))
        has_effects = bool(a.get("effects"))
        is_heal = str(a.get("damage_type", "")).lower() in ("cura", "heal")
        assert has_damage or has_cond or has_effects or is_heal, \
            f"{aid}: habilidade só-texto (sem dano/condição/effects/cura)"


def test_todas_habilidades_de_custo_usam_entropia():
    for aid, a in ABILITIES.items():
        if int(a.get("cost", 0) or 0) > 0:
            assert a.get("resource_type") == "Entropia", \
                f"{aid}: custa mas não é Entropia"


def test_requires_dentro_do_mesmo_ramo_ou_tronco():
    for aid, a in ABILITIES.items():
        for r in a.get("requires") or []:
            req = ABILITIES[r]
            rb, ab = req.get("branch"), a.get("branch")
            assert rb is None or rb == ab, \
                f"{aid} ({ab}) requer {r} de ramo diferente ({rb})"


def test_cadeia_de_tiers_no_ramo():
    """Tier 3 de ramo sempre exige algo (assinatura no fim da cadeia)."""
    for aid, a in ABILITIES.items():
        if a.get("branch") and a.get("tier") == 3:
            assert a.get("requires"), f"{aid}: tier 3 de ramo sem requires"


def test_starting_abilities_pertencem_a_classe():
    for cname, c in CLASSES.items():
        for aid in c.get("starting_abilities") or []:
            classes = ABILITIES[aid].get("classes") or []
            assert cname in classes or "all" in classes, \
                f"{cname}: starting {aid} não pertence à classe"


def test_universais_continuam_all():
    assert ABILITIES["ataque_basico"].get("classes") == ["all"]
