"""Suíte da spec conflito-08: perfil tático, companheiros e informação revelada.

100% determinístico. Exercita `services/tactical_profile.py` (pick_action +
validação de ordem + controle de party + geração com guard) e
`services/bestiary_knowledge.py` (painel público + revelação persistida no overlay
runtime — isolado em tmp pela fixture autouse do conftest)."""

from services import tactical_profile as tp
from services import bestiary_knowledge as bk
from llm_setup import FallbackLLM


class _CountingLLM:
    """LLM que devolve um TacticalProfileModel válido e conta invocações."""
    def __init__(self):
        self.calls = 0

    def with_structured_output(self, schema, *a, **k):
        self._schema = schema
        return self

    def invoke(self, _prompt):
        self.calls += 1
        return tp.TacticalProfileModel(priorities=[
            tp.PriorityModel(trigger="sempre", tipo="obrigatorio",
                             action_hint="ataca", resistance="flexivel"),
        ])


# ==========================================================================
# Etapa 1 — pick_action (R1/R2/R3)
# ==========================================================================
def test_primeira_prioridade_valida_prevalece():
    profile = {"priorities": [
        {"trigger": "lider_caido", "tipo": "obrigatorio", "action_hint": "vinga o líder"},
        {"trigger": "sempre", "tipo": "obrigatorio", "action_hint": "ataca o mais próximo"},
    ]}
    # líder não caiu → 1ª pula, 2ª (sempre) prevalece
    d0 = tp.pick_action(profile, {})
    assert d0["action_hint"] == "ataca o mais próximo"
    # líder caiu → 1ª prevalece (precedência por ordem)
    d1 = tp.pick_action(profile, {"lider_caido": True})
    assert d1["action_hint"] == "vinga o líder"


def test_prioridade_obrigatoria_executa_sem_escolha():
    profile = {"priorities": [{"trigger": "sempre", "tipo": "obrigatorio",
                               "action_hint": "carrega"}]}
    d = tp.pick_action(profile, {})
    assert d["requires_player_choice"] is False and d["matched"] is True


def test_prioridade_oferta_pergunta_ao_jogador():
    profile = {"priorities": [{"trigger": "aliado_em_perigo", "tipo": "oferta",
                               "action_hint": "sacrificar-se pelo aliado?"}]}
    d = tp.pick_action(profile, {"aliado_em_perigo": True})
    assert d["requires_player_choice"] is True and d["tipo"] == "oferta"


# ==========================================================================
# Etapa 2 — validação de ordem de companheiro (R3/R4/R6)
# ==========================================================================
def _paladino(resistance="absoluta"):
    return {"tactical_profile": {"priorities": [
        {"trigger": "ordem_incompativel", "tipo": "restricao",
         "action_hint": "O paladino se recusa a assassinar um inocente.",
         "resistance": resistance, "blocks": ["matar_inocente"]},
    ]}}


def test_ordem_flexivel_aceita():
    comp = _paladino(resistance="flexivel")
    res = tp.validate_companion_order(comp, {"action": "atacar", "tags": ["matar_inocente"]})
    assert res["accepted"] is True


def test_ordem_absoluta_recusa_sempre():
    comp = _paladino(resistance="absoluta")
    res = tp.validate_companion_order(comp, {"action": "atacar", "tags": ["matar_inocente"],
                                             "leverage": True})
    assert res["accepted"] is False               # nem leverage vence Absoluta


def test_ordem_resistente_cede_com_leverage():
    comp = _paladino(resistance="resistente")
    sem = tp.validate_companion_order(comp, {"tags": ["matar_inocente"]})
    com = tp.validate_companion_order(comp, {"tags": ["matar_inocente"], "leverage": True})
    assert sem["accepted"] is False and com["accepted"] is True


def test_ordem_recusada_devolve_escolha_ao_jogador():
    comp = _paladino(resistance="absoluta")
    res = tp.validate_companion_order(comp, {"tags": ["matar_inocente"]})
    assert res["return_choice_to_player"] is True and res["reason"]


# ==========================================================================
# Etapa 3 — controle de party / perda de controle (R6)
# ==========================================================================
def test_jogador_controla_party_com_protagonista_fora():
    party = [{"name": "herói", "conscious": False},           # protagonista fora
             {"name": "aliado", "conscious": True, "active_conditions": []}]
    assert tp.player_retains_party_control(party) is True
    assert tp.player_controls_member(party[1]) is True


def test_perfil_assume_turno_so_com_condicao_explicita():
    saudavel = {"conscious": True, "active_conditions": []}
    assert tp.profile_takes_over(saudavel) is False
    amedrontado = {"conscious": True, "active_conditions": [{"name": "medo"}]}
    assert tp.profile_takes_over(amedrontado) is True


def test_medo_confusao_controle_mental_tiram_comando():
    for cond in ("medo", "confusao", "controle mental"):
        m = {"conscious": True, "active_conditions": [{"name": cond}]}
        assert tp.loses_command(m) is True


# ==========================================================================
# Etapa 4 — geração do perfil (LLM 1×, persistida) + guard
# ==========================================================================
def test_perfil_gerado_uma_vez_e_reusado_sem_nova_chamada():
    llm = _CountingLLM()
    entry = {"archetype_id": "verme_do_po"}
    p1 = tp.get_or_generate_profile(entry, "Verme do Pó", llm)
    p2 = tp.get_or_generate_profile(entry, "Verme do Pó", llm)
    assert llm.calls == 1                          # 2ª vez reusa a ficha
    assert p1 == p2 and entry["tactical_profile"]["priorities"]


def test_geracao_com_fallbackllm_cai_no_default_sem_estourar():
    # FallbackLLM não devolve TacticalProfileModel → guard cai no perfil default.
    profile = tp.generate_tactical_profile("Qualquer", FallbackLLM("sem chave"))
    assert profile["priorities"] and profile["priorities"][0]["trigger"] == "sempre"


# ==========================================================================
# Etapa 5 — informação revelada progressiva (R7/R8/R9)
# ==========================================================================
def test_painel_inicial_mostra_so_campos_publicos():
    enemy = {"vitalidade": 12, "max_vitalidade": 20, "esquiva": 11, "protecao": 2,
             "virtudes": {"corpo": 3}, "ferimento_espacos": {"critico": 1},
             "tactical_profile": {"priorities": []}, "known_cards": ["segredo"]}
    panel = bk.public_panel(enemy)
    assert panel["vitalidade"] == 12 and panel["esquiva"] == 11
    assert "virtudes" not in panel and "tactical_profile" not in panel
    assert "ferimento_espacos" not in panel and "known_cards" not in panel


def test_carta_usada_revela_e_persiste_no_bestiario():
    e1 = {"archetype_id": "afogado", "name": "Afogado"}
    bk.reveal_card(e1, "maremoto")
    assert bk.is_card_revealed(e1, "maremoto")
    # 2º encontro, mesmo arquétipo → começa revelada
    e2 = {"archetype_id": "afogado", "name": "Afogado"}
    bk.apply_persisted_knowledge(e2)
    assert bk.is_card_revealed(e2, "maremoto")


def test_resistencia_ativada_revela_e_persiste():
    e1 = {"archetype_id": "golem_gelo"}
    bk.reveal_resistance(e1, "gelido")
    e2 = {"archetype_id": "golem_gelo"}
    bk.apply_persisted_knowledge(e2)
    assert bk.is_resistance_revealed(e2, "gelido")


def test_variante_pode_ter_carta_exclusiva_ainda_oculta():
    e1 = {"archetype_id": "afogado"}
    bk.reveal_card(e1, "maremoto")
    # variante do mesmo arquétipo com carta exclusiva marcada
    variante = {"archetype_id": "afogado", "variant_exclusive_cards": ["chamado_abissal"]}
    bk.reveal_card(variante, "chamado_abissal")     # não propaga pro arquétipo
    e3 = {"archetype_id": "afogado"}
    bk.apply_persisted_knowledge(e3)
    assert bk.is_card_revealed(e3, "maremoto")       # comum propaga
    assert not bk.is_card_revealed(e3, "chamado_abissal")  # exclusiva de variante não
