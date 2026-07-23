"""Suíte da spec conflito-15: autoria/migração do bestiário para o schema v4.

100% determinístico, offline. Valida o bestiário migrado por
`scripts/migrate_bestiary_v4.py`: categoria, Virtudes 0-5, Vitalidade por Corpo,
resistências tipadas, perfil tático rico com regra de fuga/rendição, Cartas por
criatura (≥1 assinatura oculta) e a integração com a revelação da conflito-08.
"""
import json
import os

import pytest

import gamedata
from services import bestiary_knowledge as bk
from services import tactical_profile as tp

BEST = json.load(open(os.path.join("data", "bestiary.json"), encoding="utf-8"))
CREATURES = list(BEST.values())
CATS = {"lacaio", "padrao", "elite", "chefe", "nomeado"}
DANO_VALIDO = set(gamedata.DANO_FISICO + gamedata.DANO_SOBRENATURAL)


def _hidden_card_ids():
    ids = set()
    for fn in os.listdir(os.path.join("data", "cards")):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join("data", "cards", fn), encoding="utf-8") as f:
            for c in (json.load(f).get("cards") or []):
                if c.get("oculta"):
                    ids.add(c["id"])
    return ids


HIDDEN = _hidden_card_ids()


# --------------------------------------------------------------------------
# Etapa 1 — migração de campos triviais
# --------------------------------------------------------------------------
def test_todas_criaturas_tem_categoria_valida():
    for cre in CREATURES:
        assert cre.get("categoria") in CATS, f"{cre.get('name')}: categoria {cre.get('categoria')!r}"


def test_regions_preservado_da_migracao():
    # R5: regiões não são reautoradas — cada criatura mantém as suas.
    com_regiao = [c for c in CREATURES if c.get("regions")]
    assert len(com_regiao) >= 70, "migração perdeu regiões"
    for cre in CREATURES:
        assert isinstance(cre.get("regions", []), list)


def test_sem_placeholder_todo_remanescente():
    # critério de aceite: nenhum TODO_REVISAO_MANUAL sobra.
    raw = json.dumps(BEST, ensure_ascii=False)
    assert "TODO_REVISAO_MANUAL" not in raw


def test_categoria_bate_com_tipo_antigo():
    mapa = {"Minion": "lacaio", "Elite": "elite", "BOSS": "chefe"}
    for cre in CREATURES:
        esperado = mapa.get(cre.get("type"))
        if esperado:
            assert cre["categoria"] == esperado, f"{cre['name']}: {cre['categoria']} != {esperado}"


# --------------------------------------------------------------------------
# Etapa 2 — perfil tático completo
# --------------------------------------------------------------------------
def test_toda_criatura_tem_pelo_menos_uma_prioridade_obrigatoria():
    for cre in CREATURES:
        prio = (cre.get("tactical_profile") or {}).get("priorities") or []
        assert prio, f"{cre['name']}: sem prioridades"
        assert any(p.get("tipo") == "obrigatorio" for p in prio), \
            f"{cre['name']}: nenhuma prioridade obrigatória"


def test_nenhuma_criatura_sem_regra_de_fuga_ou_rendicao_explicita():
    FLEE = ("foge", "fug", "recua", "rende", "reagrupa", "recuar", "abandona", "some")
    for cre in CREATURES:
        prio = (cre.get("tactical_profile") or {}).get("priorities") or []
        tem_fuga = any(any(k in str(p.get("action_hint", "")).lower() for k in FLEE)
                       for p in prio)
        # não-fuga só é aceitável se INTENCIONAL (resistência absoluta = luta até a morte)
        intencional = any(str(p.get("resistance")) == "absoluta" for p in prio)
        assert tem_fuga or intencional, \
            f"{cre['name']}: burra até a morte sem ser intencional"


def test_perfil_e_reusado_sem_llm():
    # get_or_generate_profile reusa o perfil persistido, NUNCA chama LLM.
    cre = dict(CREATURES[0])
    sentinel = object()
    prof = tp.get_or_generate_profile(cre, "qualquer", sentinel)  # LLM inválido de propósito
    assert prof == cre["tactical_profile"]


def test_pick_action_decide_sem_llm():
    for cre in CREATURES[:10]:
        d = tp.pick_action(cre["tactical_profile"], {"sempre": True})
        assert d["matched"] and d["action_hint"]


# --------------------------------------------------------------------------
# Etapa 3 — Virtudes/Vitalidade/resistências
# --------------------------------------------------------------------------
def test_virtudes_no_intervalo_0_5():
    for cre in CREATURES:
        v = cre.get("virtudes") or {}
        assert set(v) >= {"mente", "agilidade", "forca", "carisma", "corpo"}, cre["name"]
        for k, val in v.items():
            assert isinstance(val, int) and 0 <= val <= 5, f"{cre['name']}: {k}={val}"


def test_vitalidade_da_criatura_bate_com_tabela_de_corpo():
    for cre in CREATURES:
        corpo = int((cre.get("virtudes") or {}).get("corpo", 0))
        assert cre["max_vitalidade"] == gamedata.vitalidade_para_corpo(corpo), cre["name"]
        assert cre["vitalidade"] == cre["max_vitalidade"]
        assert cre["ferimento_espacos"] == gamedata.espacos_ferimento_para_corpo(corpo)


def test_resistencias_usam_tipos_validos_de_dano():
    RESIST_SRC = set(gamedata.RESIST_MODIFIER)
    achou = 0
    for cre in CREATURES:
        for t, src in (cre.get("resistances") or {}).items():
            assert t in DANO_VALIDO, f"{cre['name']}: resistência tipo {t!r}"
            srcs = src if isinstance(src, list) else [src]
            assert all(s in RESIST_SRC for s in srcs), f"{cre['name']}: fonte {src!r}"
            achou += 1
        for t in (cre.get("immunities") or []):
            assert t in DANO_VALIDO, f"{cre['name']}: imunidade {t!r}"
    assert achou >= 10, "nenhuma resistência temática migrada?"


def test_chefe_mais_robusto_que_lacaio():
    # o piso de Corpo por categoria garante que Chefe tem mais Vitalidade que Lacaio.
    lac = [c["max_vitalidade"] for c in CREATURES if c["categoria"] == "lacaio"]
    chefe = [c["max_vitalidade"] for c in CREATURES if c["categoria"] == "chefe"]
    if lac and chefe:
        assert min(chefe) >= max(lac) or (sum(chefe) / len(chefe)) > (sum(lac) / len(lac))


# --------------------------------------------------------------------------
# Etapa 4 — Cartas por criatura + ocultação
# --------------------------------------------------------------------------
def test_criatura_tem_pelo_menos_uma_carta_especial():
    for cre in CREATURES:
        cartas = cre.get("cartas") or []
        assert cartas, f"{cre['name']}: sem Cartas"
        assert set(cartas) & HIDDEN, f"{cre['name']}: sem Carta assinatura oculta"


def test_cartas_referenciadas_existem():
    from services import cards
    todas = set(cards.all_cards())
    for cre in CREATURES:
        for cid in (cre.get("cartas") or []):
            assert cid in todas, f"{cre['name']}: Carta '{cid}' inexistente"


def test_carta_comeca_oculta_ate_primeiro_uso():
    # integração conflito-08: a Carta assinatura não aparece no painel público e
    # só fica revelada depois do 1º uso.
    cre = next(c for c in CREATURES if set(c.get("cartas") or []) & HIDDEN)
    entry = dict(cre)
    entry["revealed_cards"] = []
    signature = next(cid for cid in entry["cartas"] if cid in HIDDEN)
    assert not bk.is_card_revealed(entry, signature)
    assert "cartas" not in bk.public_panel(entry)  # perfil/cartas não são públicos
    bk.reveal_card(entry, signature)
    assert bk.is_card_revealed(entry, signature)


# --------------------------------------------------------------------------
# Etapa 5 — lint estendido
# --------------------------------------------------------------------------
def test_lint_do_bestiario_real_sem_erro():
    from services.content_validator import validate_bestiary
    assert validate_bestiary() == []


def test_lint_pega_bestiario_ruim(tmp_path):
    from services.content_validator import validate_bestiary
    bad = tmp_path / "bestiary.json"
    bad.write_text(json.dumps({
        "x": {"name": "X", "categoria": "invalida", "virtudes": {"corpo": 9},
              "max_vitalidade": 999, "tactical_profile": {"priorities": []},
              "cartas": []},
    }), encoding="utf-8")
    findings = validate_bestiary(str(bad), os.path.join("data", "cards"))
    msgs = " ".join(f.message for f in findings)
    assert "categoria" in msgs and "Virtude" in msgs and "sem Cartas" in msgs
