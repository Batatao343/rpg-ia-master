"""Suíte da spec conflito-14: autoria completa das Cartas de classe/subclasse.

100% determinístico, offline. Valida o Acervo autoral gerado por
`scripts/gen_cards_v4.py` (`data/cards/{classe}.json`): cobertura das 15
combinações, catálogo fechado de efeitos, escala de dano nova (3/4/6/8),
Ruptura A/B nas centrais, Cartas de Virtude sugeridas, potência por nível e
parity de dano puro.
"""
import re

import pytest

import gamedata
from services import cards

# 5 classes × 3 subclasses (chaves de branch em data/classes.json).
COMBOS = {
    "Devoto do Abismo": ["consagrado", "zeloso", "enlutado"],
    "Sangromante": ["exposto", "avaro", "silencioso"],
    "Corruptor": ["biologia", "alma", "inorganica"],
    "Arcanista Cinzento": ["calibrado", "descoberto", "improvisador"],
    "Médico de Campo": ["cirurgiao_trincheira", "boticario", "cirurgiao_ferro"],
}
AUTORAIS = [c for c in cards.all_cards().values()
           if c.get("origem") == "conflito-14"]


def _avg(formula):
    t = 0.0
    for m in re.finditer(r"(\d+)d(\d+)", str(formula or "")):
        t += int(m.group(1)) * (int(m.group(2)) + 1) / 2
    return t


# --------------------------------------------------------------------------
# Etapa 1 — cobertura + catálogo fechado
# --------------------------------------------------------------------------
def test_todas_as_15_combinacoes_tem_cartas_proprias():
    for classe, subs in COMBOS.items():
        for sub in subs:
            proprias = [c for c in AUTORAIS
                        if c["classe"] == classe and c.get("subclasse") == sub]
            assert len(proprias) >= 3, f"{classe}/{sub}: só {len(proprias)} cartas próprias"


def test_toda_classe_tem_acervo_de_tronco():
    for classe in COMBOS:
        tronco = [c for c in AUTORAIS
                  if c["classe"] == classe and not c.get("subclasse")]
        assert len(tronco) >= 6, f"{classe}: tronco raso ({len(tronco)})"


def test_todas_as_cartas_usam_effectspec_kind_valido():
    for c in AUTORAIS:
        ef = c.get("efeito") or {}
        assert cards.valid_effect_kind(ef), \
            f"{c['id']}: efeito.kind {ef.get('kind')!r} fora do catálogo fechado"
        # Ruptura/Evolução também só podem usar kinds do catálogo.
        for path, sub in _all_nested_effects(c):
            assert cards.valid_effect_kind(sub), \
                f"{c['id']}.{path}: kind {sub.get('kind')!r} fora do catálogo"


def _all_nested_effects(card):
    rup = card.get("ruptura") or {}
    for k in ("caminho_a", "caminho_b"):
        if isinstance(rup.get(k), dict):
            yield f"ruptura.{k}", rup[k]
    evo = card.get("evolucao") or {}
    for k in ("caminho_a", "caminho_b"):
        branch = evo.get(k) or {}
        if isinstance(branch.get("efeito"), dict):
            yield f"evolucao.{k}.efeito", branch["efeito"]
        if isinstance(branch.get("ruptura"), dict):
            yield f"evolucao.{k}.ruptura", branch["ruptura"]


def test_cartas_tem_campos_obrigatorios():
    for c in AUTORAIS:
        for campo in ("id", "name", "tipo", "classe", "patamar",
                      "custo_entropia", "frequencia", "efeito"):
            assert campo in c, f"{c.get('id')}: falta {campo}"
        assert c["patamar"] in ("inicial", "avancado", "superior")
        assert c["frequencia"] in ("livre", "turno", "cena",
                                   "descanso_curto", "descanso_longo")
        assert c["tipo"] in ("ativa", "passiva", "utilitaria", "reacao")


# --------------------------------------------------------------------------
# Etapa 2 — dano na escala nova (3/4/6/8)
# --------------------------------------------------------------------------
def test_dano_base_das_cartas_ativas_bate_com_categoria_de_arma():
    achou = 0
    for c in AUTORAIS:
        ef = c.get("efeito") or {}
        if ef.get("kind") != "dano":
            continue
        cat = ef.get("categoria_arma")
        assert cat in cards.DANO_BASE_ARMA, f"{c['id']}: categoria {cat!r} inválida"
        base = cards.DANO_BASE_ARMA[cat]
        db = int(ef.get("dano_base", 0))
        # nunca abaixo da base da arma; o excedente é pago em Entropia
        assert db >= base, f"{c['id']}: dano_base {db} < base da arma {base}"
        achou += 1
    assert achou >= 10, "poucas cartas de dano detectadas — schema mudou?"


def test_nao_ha_formula_de_dado_antiga():
    # R2: escala nova é FLAT (dano_base), não '2d6'. Nenhuma carta ativa de dano
    # deve carregar fórmula de dado.
    for c in AUTORAIS:
        ef = c.get("efeito") or {}
        assert "formula" not in ef or not re.search(r"\dd\d", str(ef.get("formula"))), \
            f"{c['id']}: ainda usa fórmula de dado antiga"


# --------------------------------------------------------------------------
# Etapa 3 — Ruptura Caminho A/B + Evolução
# --------------------------------------------------------------------------
def test_cartas_centrais_tem_ruptura_com_dois_caminhos():
    centrais = [c for c in AUTORAIS if c.get("central")]
    # 1 central por subclasse (15) no mínimo
    assert len(centrais) >= 15, f"só {len(centrais)} cartas centrais"
    for c in centrais:
        rup = c.get("ruptura") or {}
        assert rup.get("caminho_a") and rup.get("caminho_b"), \
            f"{c['id']}: Ruptura sem os dois caminhos"
        evo = c.get("evolucao") or {}
        assert evo.get("caminho_a") and evo.get("caminho_b"), \
            f"{c['id']}: Evolução sem os dois caminhos"


def test_cada_subclasse_tem_uma_carta_central():
    for classe, subs in COMBOS.items():
        for sub in subs:
            centrais = [c for c in AUTORAIS if c["classe"] == classe
                        and c.get("subclasse") == sub and c.get("central")]
            assert len(centrais) == 1, \
                f"{classe}/{sub}: {len(centrais)} centrais (esperado 1)"


# --------------------------------------------------------------------------
# Etapa 4 — Cartas de Virtude sugeridas
# --------------------------------------------------------------------------
def test_cada_combinacao_tem_pelo_menos_duas_cartas_de_virtude_sugeridas():
    pool = {c["id"] for c in cards.virtue_cards_pool()}
    for classe, subs in COMBOS.items():
        for sub in subs:
            sug = cards.suggested_virtue_cards(classe, sub)
            assert len(sug) >= 2, f"{classe}/{sub}: {len(sug)} sugestões de Virtude"
            for cid in sug:
                assert cid in pool, f"{classe}/{sub}: sugere '{cid}' fora do pool de Virtude"


# --------------------------------------------------------------------------
# Etapa 5 — potência por nível (conflito-11)
# --------------------------------------------------------------------------
def test_potency_by_level_cobre_niveis_1_a_10_para_as_4_categorias():
    from services import encounter_preparation as ep
    for cat in ("fraco", "moderado", "forte", "devastador"):
        vals = [ep.potency_value(cat, n, "dano") for n in range(1, 11)]
        assert all(v > 0 for v in vals), f"{cat}: valor não-positivo em 1..10"
        assert vals == sorted(vals), f"{cat}: dano não-monotônico por nível"
    # escada de categorias no mesmo nível
    for n in (1, 5, 10):
        esc = [ep.potency_value(c, n, "dano")
               for c in ("fraco", "moderado", "forte", "devastador")]
        assert esc == sorted(esc) and len(set(esc)) == 4, \
            f"nível {n}: categorias não formam escada crescente ({esc})"


# --------------------------------------------------------------------------
# Etapa 6 — guarda de parity de dano puro (banda adaptada à escala nova)
# --------------------------------------------------------------------------
def _pure_damage_dpe():
    """dano_base/custo das cartas de DANO PURO custeadas (sem DoT/condição/área)."""
    out = {}
    for c in AUTORAIS:
        ef = c.get("efeito") or {}
        if ef.get("kind") != "dano":
            continue
        custo = int(c.get("custo_entropia", 0) or 0)
        if custo <= 0:
            continue
        if ef.get("alvo") == "area":   # dano em área carrega payload (fora da banda limpa)
            continue
        db = int(ef.get("dano_base", 0) or 0)
        if db <= 0:
            continue
        out[c["id"]] = db / custo
    return out


def test_parity_dano_puro_dentro_da_banda():
    dpe = _pure_damage_dpe()
    assert dpe, "nenhuma carta de dano puro custeada detectada"
    for cid, v in dpe.items():
        assert 1.5 <= v <= 4.0, (
            f"{cid} fora da banda de parity: {v:.2f} dano/Entropia "
            f"(esperado 1.5–4.0). Rebalancear no gerador.")


def test_utilitarias_sem_custo_e_fora_de_combate():
    for c in AUTORAIS:
        if c.get("tipo") != "utilitaria":
            continue
        assert (c.get("efeito") or {}).get("kind") == "utilitaria", \
            f"{c['id']}: utilitária sem efeito utilitaria"
        assert c.get("custo_entropia", 0) == 0, f"{c['id']}: utilitária custa Entropia"


# --------------------------------------------------------------------------
# Integração com o motor de Cartas (conflito-02) — as autorais são usáveis
# --------------------------------------------------------------------------
def test_carta_autoral_usavel_pelo_motor():
    cid = "dev_muralha_viva"
    card = cards.get_card(cid)
    assert card and card["custo_entropia"] == 2
    st = {"player": {"class_name": "Devoto do Abismo", "level": 1,
                     "entropy": 10, "prepared_cards": [cid], "card_usage": {},
                     "virtue_cards": []},
          "world": {"danger_level": 1}, "combat": {"active": True}}
    r = cards.use_card(st, cid)
    assert r["ok"], r
    assert st["player"]["entropy"] == 8


# --------------------------------------------------------------------------
# Etapa 5 — lint de conteúdo (services.content_validator.validate_cards)
# --------------------------------------------------------------------------
def test_lint_das_cartas_reais_sem_erro():
    from services.content_validator import validate_cards
    assert validate_cards() == []


def test_lint_pega_carta_ruim(tmp_path):
    import json as _json
    from services.content_validator import validate_cards
    d = tmp_path / "cards"
    d.mkdir()
    (d / "ruim.json").write_text(_json.dumps({"cards": [
        {"id": "x", "origem": "conflito-14", "tipo": "ativa", "patamar": "inicial",
         "frequencia": "livre", "efeito": {"kind": "kind_inventado"}},
        {"id": "y", "origem": "conflito-14", "tipo": "ativa", "patamar": "inicial",
         "frequencia": "livre", "efeito": {"kind": "dano", "categoria_arma": "leve", "dano_base": 1}},
    ]}), encoding="utf-8")
    findings = validate_cards(str(d))
    ids = {(f.entity_id, f.message) for f in findings}
    assert any(e == "x" for e, _ in ids)          # kind fora do catálogo
    assert any(e == "y" and "dano_base" in m for e, m in ids)  # abaixo da base


def test_ruptura_autoral_gera_carga():
    cid = "dev_cons_liturgia"  # central, tem ruptura
    st = {"player": {"class_name": "Devoto do Abismo", "level": 4,
                     "entropy": 10, "abyss_charge": 0, "prepared_cards": [cid],
                     "card_usage": {}, "virtue_cards": []},
          "world": {"danger_level": 1}, "combat": {"active": True}}
    r = cards.use_ruptura(st, cid)
    assert r["ok"], r
    assert st["player"]["abyss_charge"] == 1
