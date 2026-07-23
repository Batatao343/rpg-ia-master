"""Suíte da spec conflito-07: Última Ação, Estado Terminal, Cicatriz e rendição.

100% determinístico. Exercita `services/death_flow.py`. As rolagens usam um rng
fixo (min/max) para tornar sucesso/falha de estabilização exatos, sem seed frágil.
A Cicatriz é o 1º structured output novo do épico — guard de `FallbackLLM` testado."""

import gamedata
from services import death_flow as df
from llm_setup import FallbackLLM


class _Rng:
    """rng determinístico: retorna sempre o mínimo (fail) ou o máximo (success)."""
    def __init__(self, high):
        self.high = high

    def randint(self, a, b):
        return b if self.high else a


def _player(corpo=2, criticos=0, **over):
    espacos = gamedata.espacos_ferimento_para_corpo(corpo)
    fer = {"leve": [], "grave": [], "critico": []}
    for i in range(criticos):
        fer["critico"].append({"categoria": "critico", "regiao": f"r{i}", "suprimida": False})
    p = {"is_player": True, "class_name": "Devoto do Abismo",
         "virtudes": {"corpo": corpo, "mente": 2, "agilidade": 1, "forca": 1, "carisma": 1},
         "vitalidade": 0, "max_vitalidade": gamedata.vitalidade_para_corpo(corpo),
         "ferimento_espacos": espacos, "ferimentos": fer,
         "entropy": 0, "abyss_charge": 0}
    p.update(over)
    return p


def _full_criticos(corpo=2):
    espacos = gamedata.espacos_ferimento_para_corpo(corpo)
    return _player(corpo=corpo, criticos=int(espacos["critico"]))


# ==========================================================================
# Etapa 1 — Última Ação (R1)
# ==========================================================================
def test_ultimo_critico_dispara_ultima_acao_imediata():
    p = _full_criticos()
    assert df.critical_spaces_full(p) is True
    assert df.should_trigger_last_stand(p) is True
    res = df.trigger_last_stand(p)
    assert res["vantagem_extrema"] is True
    assert res["entra_em_estado_terminal"] is True


def test_ultima_acao_ignora_recurso_ausente_sem_criar_ferimento():
    p = _full_criticos()
    p["entropy"] = 1
    p["vitalidade"] = 0
    antes = len(p["ferimentos"]["critico"])
    res = df.last_stand_pay(p, entropy=5, vitality=4)   # paga além do que tem
    assert res["entropy"] == 0 and res["vitalidade"] == 0
    assert res["wound_criado"] is False
    assert len(p["ferimentos"]["critico"]) == antes    # NÃO cria Ferimento novo


def test_ultima_acao_pode_declarar_ruptura():
    p = _full_criticos()
    res = df.trigger_last_stand(p, ruptura=True)
    assert res["ruptura_declarada"] is True
    assert p["abyss_charge"] == 1                       # Carga gerada normalmente


# ==========================================================================
# Etapa 2 — Estado Terminal + morte/estabilização (R2/R3/R4)
# ==========================================================================
def test_sem_aliado_morte_imediata():
    p = _full_criticos()
    df.enter_terminal_state(p)
    res = df.attempt_stabilization(p, helper=None)
    assert res["dead"] is True and p["dead"] is True


def test_duas_falhas_de_estabilizacao_morte():
    p = _full_criticos()
    df.enter_terminal_state(p)
    helper = {"virtudes": {"mente": 0}}
    r1 = df.attempt_stabilization(p, helper, rng=_Rng(high=False))
    assert r1["revived"] is False and r1["dead"] is False and r1["attempts"] == 1
    r2 = df.attempt_stabilization(p, helper, rng=_Rng(high=False))
    assert r2["dead"] is True and p["dead"] is True


def test_medico_com_kit_reanima_automatico_metade_vitalidade():
    p = _full_criticos(corpo=2)
    df.enter_terminal_state(p)
    res = df.attempt_stabilization(p, {"virtudes": {"mente": 0}}, has_kit=True, is_medico=True)
    assert res["revived"] is True and res["auto"] is True and res["kit_cargas"] == 1
    assert p["vitalidade"] == int(p["max_vitalidade"] * 0.5)
    assert p["estado_terminal"] is False and df.check_scar_required(p) is True


def test_pocao_adequada_reanima_automatico():
    p = _full_criticos()
    df.enter_terminal_state(p)
    res = df.attempt_stabilization(p, helper=None, has_potion=True)
    assert res["revived"] is True and res["auto"] is True
    assert p["vitalidade"] == int(p["max_vitalidade"] * 0.5)


def test_aliado_improvisado_sucesso_volta_com_1_vitalidade():
    p = _full_criticos()
    df.enter_terminal_state(p)
    res = df.attempt_stabilization(p, {"virtudes": {"mente": 5}}, rng=_Rng(high=True))
    assert res["revived"] is True and res["auto"] is False
    assert p["vitalidade"] == 1                         # improvisado = 1 Vitalidade


# ==========================================================================
# Etapa 3 — Consciência pós-conflito (R5)
# ==========================================================================
def test_so_leves_acorda_em_seguranca():
    p = _player()
    p["ferimentos"]["leve"].append({"categoria": "leve", "regiao": "braco"})
    assert df.post_combat_consciousness(p) == "acordado"


def test_grave_precisa_tratamento():
    p = _player()
    p["ferimentos"]["grave"].append({"categoria": "grave", "regiao": "perna"})
    assert df.post_combat_consciousness(p) == "tratavel"


def test_critico_fica_inconsciente_ate_intervencao():
    p = _player(criticos=1)
    assert df.post_combat_consciousness(p) == "inconsciente"


# ==========================================================================
# Etapa 4 — Cicatriz obrigatória (R6, LLM + guard)
# ==========================================================================
def test_sobreviver_ao_fluxo_completo_marca_scar_pendente():
    p = _full_criticos()
    df.enter_terminal_state(p)
    df.attempt_stabilization(p, helper=None, has_potion=True)
    assert df.check_scar_required(p) is True


def test_gerar_cicatriz_com_fallbackllm_nao_estoura_e_limpa_pendencia():
    # FallbackLLM.with_structured_output().invoke() devolve AIMessage, não ScarModel:
    # o guard isinstance/try tem de cair no template determinístico (convenção crítica).
    p = _full_criticos()
    p["scar_pending"] = True
    p["ferimentos"]["critico"].append({"categoria": "critico", "regiao": "olho"})
    scar = df.generate_scar(p, FallbackLLM("sem chave"))
    assert scar["consequencia_negativa"] and scar["habilidade_positiva_relacionada"]
    assert p["scars"] == [scar]
    assert p["scar_pending"] is False                   # não recusável, mas resolvida


# ==========================================================================
# Etapa 5 — Categorias de inimigo (R7)
# ==========================================================================
def test_lacaio_removido_por_qualquer_ferimento():
    lacaio = {"categoria": "lacaio"}
    assert df.minion_defeated_by_wound(lacaio) is True
    assert df.uses_full_death_flow(lacaio) is False


def test_padrao_derrotado_sem_estado_terminal():
    padrao = {"categoria": "padrao", "ferimentos": {"critico": [{"regiao": "x"}]},
              "ferimento_espacos": {"leve": 2, "grave": 2, "critico": 1}}
    assert df.uses_full_death_flow(padrao) is False
    assert df.should_trigger_last_stand(padrao) is False   # sem Última Ação


def test_elite_chefe_usa_sistema_completo():
    espacos = gamedata.espacos_ferimento_para_corpo(3)
    chefe = {"categoria": "chefe", "virtudes": {"corpo": 3},
             "ferimento_espacos": espacos,
             "ferimentos": {"leve": [], "grave": [],
                            "critico": [{"regiao": f"r{i}"} for i in range(espacos["critico"])]}}
    assert df.uses_full_death_flow(chefe) is True
    assert df.should_trigger_last_stand(chefe) is True


# ==========================================================================
# Etapa 6 — Golpe não-letal + rendição + encerramento (R8/R9/R10)
# ==========================================================================
def test_golpe_final_pode_ser_nao_letal_se_forma_permitir():
    assert df.can_be_nonlethal({"tipo": "cortante"}) is True
    assert df.can_be_nonlethal({"tipo": "queda_fatal"}) is False
    assert df.can_be_nonlethal({"tipo": "cortante", "letal_forcado": True}) is False
    alvo = {"conscious": True}
    df.apply_nonlethal_finish(alvo)
    assert alvo["dead"] is False and alvo["incapacitated"] is True


def test_rendicao_por_gatilho_de_perfil_sem_llm():
    enemy = {"vitalidade": 2, "max_vitalidade": 20}
    profile = {"rende_abaixo_de_vitalidade": 0.2}
    assert df.resolve_surrender(enemy, profile) is True
    assert enemy["surrendered"] is True
    # fanático nunca se rende, mesmo com gatilho
    fanatico = {"vitalidade": 1, "max_vitalidade": 20}
    assert df.resolve_surrender(fanatico, {"rende_abaixo_de_vitalidade": 0.2,
                                           "nunca_rende": True}) is False


def test_rendicao_por_lider_caido():
    enemy = {"vitalidade": 18, "max_vitalidade": 20}
    profile = {"rende_com_lider_caido": True}
    assert df.resolve_surrender(enemy, profile, {"leader_defeated": True}) is True


def test_combate_nao_termina_por_interpretacao_livre():
    # hostil vivo, consciente, sem gatilho → combate NÃO termina
    estado = {"hostiles": [{"conscious": True, "dead": False}]}
    assert df.combat_should_end(estado)["ended"] is False
    # todos renderam → termina com motivo representado
    estado2 = {"hostiles": [{"surrendered": True, "conscious": True}]}
    r = df.combat_should_end(estado2)
    assert r["ended"] is True and "render" in r["reason"]
