"""Suíte da spec conflito-11: preparação de encontro pela LLM.

O que é testável offline (100% Python): Nível do Encontro (R6), validação de
catálogo/base narrativa/região (R4/R7/R8), tabela de potência (R5), cena
simplificada de segurança (R9) e a ficha de combate completa do NPC (R10). A
geração pela LLM usa o guard (`FallbackLLM` → cena de segurança)."""

from services import encounter_preparation as ep
from llm_setup import FallbackLLM


# ==========================================================================
# Etapa 1 — Nível do Encontro (R6)
# ==========================================================================
def test_nivel_encontro_nao_depende_do_nivel_da_party():
    # a função não tem parâmetro de party — mesmo local/região/evento = mesmo nível
    a = ep.compute_encounter_level(location_danger=3, region_danger=2, event_type="ritual")
    b = ep.compute_encounter_level(location_danger=3, region_danger=2, event_type="ritual")
    assert a == b


def test_nivel_encontro_deriva_de_local_regiao_evento():
    baixo = ep.compute_encounter_level(location_danger=1, region_danger=1, event_type="comum")
    alto = ep.compute_encounter_level(location_danger=4, region_danger=3, event_type="apex",
                                      importance="climax", unique_threats=1)
    assert alto > baixo
    assert ep.compute_encounter_level(location_danger=99) == ep.ENCOUNTER_LEVEL_MAX  # teto


# ==========================================================================
# Etapa 4 — Potência por categoria (R5)
# ==========================================================================
def test_fraco_moderado_forte_devastador_mapeiam_valor_por_nivel():
    nivel = 3
    f = ep.potency_value("fraco", nivel)
    m = ep.potency_value("moderado", nivel)
    forte = ep.potency_value("forte", nivel)
    d = ep.potency_value("devastador", nivel)
    assert f < m < forte < d                       # ordem das categorias
    # mesmo tier escala com o Nível do Encontro
    assert ep.potency_value("forte", 5) > ep.potency_value("forte", 1)


# ==========================================================================
# Etapa 2 — validação da cena preparada (R4/R8)
# ==========================================================================
def _valid_scene():
    return {
        "objects": [{"id": "alavanca", "base_narrativa": "alavanca enferrujada citada na cena",
                     "interactions": [{"label": "puxar", "effect": {"kind": "block_route", "params": {}}}]}],
        "abyss_events": [{"id": "romper", "base_na_cena": "alavanca",
                          "effect": {"kind": "reposition", "params": {}}}],
    }


def test_preparacao_valida_aceita():
    assert ep.validate_preparation(_valid_scene())["ok"] is True


def test_efeito_fora_do_catalogo_rejeitado():
    scene = _valid_scene()
    scene["objects"][0]["interactions"][0]["effect"] = {"kind": "inventar", "params": {}}
    res = ep.validate_preparation(scene)
    assert res["ok"] is False and any("catálogo" in e for e in res["errors"])


def test_objeto_sem_base_narrativa_rejeitado():
    scene = _valid_scene()
    scene["objects"][0]["base_narrativa"] = ""
    res = ep.validate_preparation(scene)
    assert res["ok"] is False and any("base narrativa" in e for e in res["errors"])


# ==========================================================================
# Etapa 3 — seleção de criatura por região (R7)
# ==========================================================================
def test_criatura_da_regiao_aceita():
    creature = {"name": "Verme do Pó", "regions": ["planicie_morta"]}
    assert ep.validate_creature_selection(creature, "planicie_morta") is True


def test_criatura_fora_da_regiao_sem_justificativa_rejeitada():
    creature = {"name": "Afogado", "regions": ["costa_naufraga"]}
    assert ep.validate_creature_selection(creature, "planicie_morta") is False
    # com justificativa de evento → aceita
    assert ep.validate_creature_selection(creature, "planicie_morta",
                                          event_justification=True) is True


# ==========================================================================
# Etapa 5 — fallback / cena simplificada de segurança (R9)
# ==========================================================================
def test_todos_falham_usa_cena_simplificada_de_seguranca():
    # FallbackLLM não devolve PreparedScene → guard cai na cena de segurança.
    ctx = {"location": "Ponte Velha", "enemies": [{"name": "Bandido"}], "encounter_level": 2}
    scene = ep.prepare_encounter(ctx, FallbackLLM("sem chave"))
    assert scene["safe_fallback"] is True
    assert scene["enemies"] == [{"name": "Bandido"}]
    assert ep.validate_preparation(scene)["ok"] is True     # a cena de segurança é sempre válida


def test_cena_simplificada_e_deterministica():
    ctx = {"location": "Cripta", "enemies": [{"name": "Esqueleto"}]}
    a = ep.fallback_safe_scene(ctx)
    b = ep.fallback_safe_scene(ctx)
    assert a["enemies"] == b["enemies"] and a["zones"] == b["zones"]


# ==========================================================================
# Etapa 6 — NPC nasce com ficha de combate completa (R10)
# ==========================================================================
def test_npc_gerado_tem_enemystats_completo_desde_criacao():
    sheet = ep.build_npc_combat_sheet({"name": "Mercador Grum",
                                       "virtudes": {"corpo": 2, "agilidade": 3,
                                                    "forca": 1, "mente": 2, "carisma": 4}})
    assert sheet["virtudes"]["carisma"] == 4
    assert sheet["vitalidade"] == sheet["max_vitalidade"] > 0
    assert sheet["ferimento_espacos"]["critico"] >= 1
    assert sheet["esquiva"] >= 10 and sheet["tactical_profile"]["priorities"]
