"""Suíte da spec conflito-05: Armadura, Tipos de Dano e Ferimentos localizados.

100% determinístico. Exercita `services/conflict_damage.py` (pipeline R8)."""

import gamedata
from services import conflict_damage as cd


def _target(vit=10, corpo=2, **over):
    t = {"virtudes": {"corpo": corpo, "agilidade": 1, "forca": 1, "mente": 1, "carisma": 1},
         "vitalidade": vit, "max_vitalidade": vit,
         "ferimentos": {"leve": [], "grave": [], "critico": []},
         "ferimento_espacos": gamedata.espacos_ferimento_para_corpo(corpo),
         "active_conditions": []}
    t.update(over)
    return t


def _armor(protecao=2, reducoes_max=0, integ=6):
    return {"categoria": "media", "protecao": protecao, "integridade_max": integ,
            "integridade_atual": integ, "reducoes_max": reducoes_max, "comprometida": False}


# --------------------------------------------------------------------------
# Etapa 1 — dano-base + tipos físicos
# --------------------------------------------------------------------------
def test_dano_base_por_categoria_arma():
    assert gamedata.DANO_BASE_ARMA == {"leve": 3, "marcial": 4, "versatil": 6, "pesada": 8}


def test_cortante_aplica_sangramento():
    t = _target(vit=3, corpo=2)
    r = cd.resolve_damage_and_wounds(t, damage_base=5, damage_type="cortante")
    assert r["wound"] is not None  # excedente 2 -> Ferimento Leve
    assert any(c["name"] == "Sangramento" for c in t["active_conditions"])
    # não acumula
    cd.resolve_damage_and_wounds(t, damage_base=5, damage_type="cortante")
    assert sum(1 for c in t["active_conditions"] if c["name"] == "Sangramento") == 1


def test_perfurante_reduz_protecao_um():
    base = _target(vit=20, armor=_armor(protecao=2))
    perf = _target(vit=20, armor=_armor(protecao=2))
    rc = cd.resolve_damage_and_wounds(base, damage_base=5, damage_type="cortante")
    rp = cd.resolve_damage_and_wounds(perf, damage_base=5, damage_type="perfurante")
    assert rc["dano_final"] == 3   # proteção 2
    assert rp["dano_final"] == 4   # proteção 2-1=1


def test_impactante_reduz_integridade_extra():
    t = _target(vit=20, armor=_armor(protecao=2, integ=6))
    cd.resolve_damage_and_wounds(t, damage_base=5, damage_type="impactante")
    assert t["armor"]["integridade_atual"] == 5   # -1 extra ao proteger


# --------------------------------------------------------------------------
# Etapa 2 — tipos sobrenaturais
# --------------------------------------------------------------------------
def test_igneo_mais_2_se_atravessa():
    t = _target(vit=20)
    r = cd.resolve_damage_and_wounds(t, damage_base=3, damage_type="igneo")
    assert r["dano_final"] == 5   # 3 +2


def test_gelido_da_vantagem_ao_proximo():
    t = _target(vit=20)
    r = cd.resolve_damage_and_wounds(t, damage_base=3, damage_type="gelido")
    assert t["_gelido_next_attack"] is True
    assert any(s["kind"] == "next_attack_advantage_vs_target" for s in r["secondary"])


def test_eletrico_desvantagem_ao_proximo():
    t = _target(vit=20)
    cd.resolve_damage_and_wounds(t, damage_base=3, damage_type="eletrico")
    assert t["_eletrico_next_attack"] is True


def test_arcano_remove_beneficio():
    t = _target(vit=20)
    r = cd.resolve_damage_and_wounds(t, damage_base=3, damage_type="arcano")
    assert any(s["kind"] == "remove_temp_buff" for s in r["secondary"])


def test_corrosivo_integridade_custa_dobro():
    # armadura COMPATÍVEL com corrosivo (sobrenatural só é reduzido se compatível)
    armor = _armor(protecao=1, reducoes_max=2, integ=6)
    armor["resist_tipos"] = ["corrosivo"]
    t = _target(vit=20, armor=armor)
    cd.resolve_damage_and_wounds(t, damage_base=5, damage_type="corrosivo")
    # 2 reduções × custo 2 = 4 Integridade
    assert t["armor"]["integridade_atual"] == 2


def test_abissal_deixa_exposto():
    t = _target(vit=20)
    cd.resolve_damage_and_wounds(t, damage_base=3, damage_type="abissal")
    assert t["exposto"] is True and t["_abissal_ignore_resist_next"] is True


# --------------------------------------------------------------------------
# Etapa 3 — Resistência/Vulnerabilidade/Imunidade
# --------------------------------------------------------------------------
def test_resistencia_reduz_2():
    t = _target(vit=20, resistances={"cortante": "resistencia"})
    r = cd.resolve_damage_and_wounds(t, damage_base=5, damage_type="cortante")
    assert r["dano_final"] == 3


def test_imunidade_zera():
    t = _target(vit=20, immunities=["igneo"])
    r = cd.resolve_damage_and_wounds(t, damage_base=8, damage_type="igneo")
    assert r["imune"] and r["dano_final"] == 0 and t["vitalidade"] == 20


def test_fontes_iguais_nao_acumulam():
    assert cd.net_resistance(["resistencia", "resistencia"]) == -2


def test_resistencia_e_vulnerabilidade_se_compensam():
    assert cd.net_resistance(["resistencia", "vulnerabilidade"]) == 0
    assert cd.net_resistance(["resistencia_maior", "vulnerabilidade"]) == -2


# --------------------------------------------------------------------------
# Etapa 4 — Armadura/Escudo/Integridade/Comprometida
# --------------------------------------------------------------------------
def test_protecao_reduz_dano_automatico():
    t = _target(vit=20, armor=_armor(protecao=3, reducoes_max=0, integ=8))
    r = cd.resolve_damage_and_wounds(t, damage_base=8, damage_type="cortante")
    assert r["dano_final"] == 5 and r["protegido"] is True


def test_gastar_integridade_reduz_dano_extra():
    t = _target(vit=20, armor=_armor(protecao=1, reducoes_max=2, integ=6))
    r = cd.resolve_damage_and_wounds(t, damage_base=5, damage_type="cortante")
    assert r["dano_final"] == 2                    # 5 -1 proteção -2 integridade
    assert t["armor"]["integridade_atual"] == 4    # 2 pontos gastos


def test_integridade_zero_fica_comprometida():
    t = _target(vit=20, armor=_armor(protecao=1, reducoes_max=3, integ=2))
    cd.resolve_damage_and_wounds(t, damage_base=8, damage_type="cortante")
    assert t["armor"]["comprometida"] is True and t["armor"]["integridade_atual"] == 0


def test_armadura_e_escudo_nao_somam():
    t = _target(vit=20, armor=_armor(protecao=2, reducoes_max=0),
                shield={"categoria": "pesado", "protecao": 3, "integridade_max": 7,
                        "integridade_atual": 7, "reducoes_max": 0, "comprometida": False})
    com_armadura = cd.resolve_damage_and_wounds(dict(t, vitalidade=20), damage_base=8,
                                                damage_type="cortante", use_shield=False)
    com_escudo = cd.resolve_damage_and_wounds(dict(t, vitalidade=20), damage_base=8,
                                              damage_type="cortante", use_shield=True)
    assert com_armadura["dano_final"] == 6   # proteção 2
    assert com_escudo["dano_final"] == 5     # proteção 3 (não 2+3=5 de soma)


# --------------------------------------------------------------------------
# Etapa 5 — Ferimentos localizados + agravamento
# --------------------------------------------------------------------------
def test_excedente_cria_ferimento_pelos_limites_de_gravidade():
    t = _target(vit=10, corpo=2)   # excedente 6 -> Grave (6-10)
    r = cd.resolve_damage_and_wounds(t, damage_base=16, damage_type="perfurante")
    assert r["wound"]["categoria"] == "grave"
    assert len(t["ferimentos"]["grave"]) == 1


def test_mesma_regiao_agrava_leve_mais_leve_vira_grave():
    t = _target(corpo=2)
    cd.apply_wound(t, "leve", "braco")
    w = cd.apply_wound(t, "leve", "braco")
    assert w["categoria"] == "grave"
    assert len(t["ferimentos"]["leve"]) == 0 and len(t["ferimentos"]["grave"]) == 1


def test_categoria_cheia_escala_para_seguinte():
    t = _target(corpo=2)
    t["ferimento_espacos"] = {"leve": 1, "grave": 2, "critico": 1}
    cd.apply_wound(t, "leve", "perna")      # ocupa o único slot Leve
    w = cd.apply_wound(t, "leve", "cabeca")  # Leve cheio -> escala p/ Grave
    assert w["categoria"] == "grave"


# --------------------------------------------------------------------------
# Etapa 6 — Sacrifício de Vitalidade + recuperação
# --------------------------------------------------------------------------
def test_sangromante_paga_com_vitalidade_ate_zero_depois_vira_ferimento():
    t = _target(vit=3, corpo=2)
    r = cd.sacrifice_vitality(t, 5)
    assert t["vitalidade"] == 0 and r["deficit"] == 2
    assert r["wound"]["categoria"] == "leve"   # déficit 2 (1-5)


def test_armadura_nao_protege_sacrificio_voluntario():
    t = _target(vit=3, corpo=2, armor=_armor(protecao=3, integ=8))
    r = cd.sacrifice_vitality(t, 8)
    assert r["deficit"] == 5 and t["armor"]["integridade_atual"] == 8  # armadura intocada


def test_descanso_curto_remove_ferimento_leve():
    t = _target()
    cd.apply_wound(t, "leve", "mao")
    out = cd.rest_treat_wounds(t, rest="curto")
    assert out["removidos"]["leve"] == 1 and t["ferimentos"]["leve"] == []


def test_ferimento_grave_precisa_kit_custa_1_carga():
    t = _target()
    cd.apply_wound(t, "grave", "peito")
    out = cd.rest_treat_wounds(t, rest="curto", has_kit=True)
    assert out["kit_cargas"] == 1
    assert t["ferimentos"]["grave"][0]["suprimida"] is True


def test_recupera_integridade_curto_metade_longo_tudo():
    arm = _armor(protecao=2, integ=8)
    arm["integridade_atual"] = 2
    cd.recover_integrity(arm, "curto")
    assert arm["integridade_atual"] == 6   # 2 + ceil(8/2)=4
    cd.recover_integrity(arm, "longo")
    assert arm["integridade_atual"] == 8
