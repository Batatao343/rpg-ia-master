"""Suíte da spec conflito-10: Cargas e Eventos do Abismo em conflito.

100% determinístico, zero LLM. Exercita `services/abyss_events.py` — base na cena,
carregamento por Cargas/gatilho/prioridade/seed, proibições do Abismo (R4/R6) e
assinatura visual fixa."""

from services import abyss_events as ab


def _event(**over):
    e = {"id": "romper_corrente", "gatilho": "sempre", "prioridade": 1,
         "cargas_necessarias": 1, "usos_permitidos": 1, "base_na_cena": "corrente_enferrujada",
         "effect": {"kind": "reposition", "params": {}}}
    e.update(over)
    return e


_SCENE_OBJS = [{"id": "corrente_enferrujada", "name": "Corrente enferrujada", "tags": ["metal"]}]


# ==========================================================================
# Etapa 1 — base na cena (R5)
# ==========================================================================
def test_evento_sem_base_na_cena_e_rejeitado():
    # cena sem água → evento de inundação não tem base
    ev = _event(id="inundacao", base_na_cena="reservatorio",
                effect={"kind": "alter_terrain", "params": {}})
    assert ab.validate_event_has_scene_basis(ev, _SCENE_OBJS) is False
    # base vazia também é rejeitada
    assert ab.validate_event_has_scene_basis(_event(base_na_cena=""), _SCENE_OBJS) is False


def test_evento_com_base_valida_e_aceito():
    assert ab.validate_event_has_scene_basis(_event(), _SCENE_OBJS) is True


def test_effect_kind_fora_do_catalogo_e_rejeitado():
    ev = _event(effect={"kind": "inventar_regra_nova", "params": {}})
    assert ab.validate_event_has_scene_basis(ev, _SCENE_OBJS) is False


# ==========================================================================
# Etapa 2 — carregamento determinístico/por seed (R2)
# ==========================================================================
def test_carrega_evento_quando_cargas_e_gatilho_atendidos_sem_llm():
    ev = _event(cargas_necessarias=2, gatilho="alvo_encurralado")
    assert ab.can_trigger(ev, {"alvo_encurralado": True}, charges_available=3,
                          scene_objects=_SCENE_OBJS) is True
    # Cargas insuficientes → não carrega
    assert ab.can_trigger(ev, {"alvo_encurralado": True}, charges_available=1) is False
    # gatilho ausente → não carrega
    assert ab.can_trigger(ev, {}, charges_available=3) is False


def test_prioridade_decide_entre_eventos_concorrentes():
    baixo = _event(id="a", prioridade=1)
    alto = _event(id="b", prioridade=5)
    escolhido = ab.select_event([baixo, alto], {}, charges_available=2,
                                scene_objects=_SCENE_OBJS)
    assert escolhido["id"] == "b"


def test_mesma_seed_mesmo_evento_carregado():
    e1 = _event(id="a", prioridade=3)
    e2 = _event(id="b", prioridade=3)         # empate de prioridade
    r1 = ab.select_event([e1, e2], {}, 2, seed=99, scene_objects=_SCENE_OBJS)
    r2 = ab.select_event([e1, e2], {}, 2, seed=99, scene_objects=_SCENE_OBJS)
    assert r1["id"] == r2["id"]


def test_usos_esgotados_nao_carrega():
    ev = _event(usos_permitidos=1)
    ev["usos_restantes"] = 0
    assert ab.can_trigger(ev, {}, charges_available=5) is False


# ==========================================================================
# Etapa 3 — proibições do Abismo (R4/R6)
# ==========================================================================
def test_nao_desfaz_sucesso_ja_resolvido():
    ok, _ = ab.validate_abyss_effect({"kind": "reposition", "params": {"undo_resolved": True}})
    assert ok is False
    ok2, _ = ab.validate_abyss_effect({"kind": "reposition"},
                                      context={"targets_resolved_success": True})
    assert ok2 is False


def test_nao_controla_mentalmente_npc():
    ok, _ = ab.validate_abyss_effect(
        {"kind": "apply_condition", "params": {"condition": "controle_mental"}})
    assert ok is False


def test_nao_cria_ou_agrava_ferimento_direto():
    ok, _ = ab.validate_abyss_effect({"kind": "damage", "params": {"direct_wound": True}})
    assert ok is False
    ok2, _ = ab.validate_abyss_effect(
        {"kind": "apply_condition", "params": {"aggravate_wound_out_of_combat": True}})
    assert ok2 is False


def test_transformar_algo_existente_e_permitido():
    ok, _ = ab.validate_abyss_effect({"kind": "reposition", "params": {"por_causa": "corrente"}})
    assert ok is True


def test_trigger_event_rejeita_efeito_proibido_sem_estourar():
    ev = _event(effect={"kind": "apply_condition", "params": {"condition": "dominado"}})
    res = ab.trigger_event(ev)
    assert res["ok"] is False and res["effect"] is None


# ==========================================================================
# Etapa 4 — assinatura visual + gasto reportado (R3)
# ==========================================================================
def test_gasto_de_carga_e_reportado_imediatamente_no_log():
    ev = _event(cargas_necessarias=2)
    res = ab.trigger_event(ev)
    assert res["ok"] is True and res["cargas_gastas"] == 2
    assert "2 Carga" in res["log"] and ab.ABYSS_SIGNATURE in res["log"]
    assert ev["usos_restantes"] == 0          # uso decrementado
