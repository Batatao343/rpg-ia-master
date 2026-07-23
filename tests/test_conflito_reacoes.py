"""Suíte da spec conflito-06: Reações, Ataques de Oportunidade e Movimento Tático.

100% determinístico, offline. Exercita `services/reactions.py` (janela/cadeia/AoO)
e as manobras novas de `services/conflict_scene.py` (Engajar/Desengajar/Guardar/
Esconder-se/Procurar/alertar + ocultação relativa por observador)."""

from services import conflict_scene as cs
from services import reactions as rx


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _scene(*participants):
    s = cs.new_scene()
    for pid in participants:
        cs.place(s, pid)
    return s


def _reacao(card_id="reflexo", gatilho="ao_ser_atacado", custo=0, repetivel=False):
    return {"id": card_id, "name": card_id, "tipo": "reacao", "gatilho": gatilho,
            "custo_entropia": custo, "repetivel": repetivel,
            "efeito": {"kind": "contra_ataque", "formula": "1d8"}}


def _stats(agilidade=1, entropy=10, conscious=True, incapacitated=False):
    return {"virtudes": {"agilidade": agilidade}, "entropy": entropy,
            "conscious": conscious, "incapacitated": incapacitated}


# ==========================================================================
# Etapa 1 — janela de reação + limite de 1 comum por cadeia (R1/R3)
# ==========================================================================
def test_reacao_valida_antes_da_rolagem():
    # R1: janela abre sobre ação declarada; reação com gatilho válido é aceita e a
    # declaração original não muda.
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    chain = rx.open_reaction_window(action)
    ok = rx.offer_reaction(chain, "player", "reflexo", card=_reacao())
    assert ok is True
    assert chain["triggering_action"] == action           # declaração congelada (R1)
    assert len(chain["links"]) == 1


def test_um_personagem_nao_usa_duas_reacoes_comuns_na_mesma_cadeia():
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    chain = rx.open_reaction_window(action)
    assert rx.offer_reaction(chain, "player", "reflexo", card=_reacao("reflexo")) is True
    # segunda reação comum do MESMO personagem na mesma cadeia é rejeitada (R3)
    segunda = rx.offer_reaction(chain, "player", "outra", card=_reacao("outra"))
    assert segunda is False
    assert len(chain["links"]) == 1


def test_cadeia_termina_quando_ninguem_tem_reacao_valida():
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    chain = rx.open_reaction_window(action)
    rx.offer_reaction(chain, "player", "reflexo", card=_reacao())
    # aliado tenta reagir com carta cujo gatilho NÃO casa → sem link novo
    assert rx.offer_reaction(chain, "aliado", "grito",
                             card=_reacao("grito", gatilho="ao_ser_atacado")) is False
    resolved = rx.resolve_chain(chain)
    assert chain["closed"] is True
    assert len(resolved) == 1
    # cadeia fechada não aceita mais ofertas
    assert rx.offer_reaction(chain, "player3", "x", card=_reacao("x")) is False


def test_reacao_debita_entropia_do_reagente():
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    chain = rx.open_reaction_window(action)
    reactor = _stats(entropy=2)
    assert rx.offer_reaction(chain, "player", "reflexo",
                             card=_reacao(custo=2), reactor=reactor) is True
    assert reactor["entropy"] == 0
    # sem Entropia suficiente → recusa sem efeito colateral
    reactor2 = _stats(entropy=1)
    chain2 = rx.open_reaction_window(action)
    assert rx.offer_reaction(chain2, "player", "reflexo",
                             card=_reacao(custo=2), reactor=reactor2) is False
    assert reactor2["entropy"] == 1


def test_carta_carrega_do_banco_de_dados():
    # a carta de exemplo reflexo_lamina tem gatilho ao_ser_atacado
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    chain = rx.open_reaction_window(action)
    assert rx.offer_reaction(chain, "player", "reflexo_lamina") is True


# ==========================================================================
# Etapa 2 — reação responde reação + ordem (R2/R4)
# ==========================================================================
def test_reacao_pode_responder_reacao_com_gatilho_valido():
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    chain = rx.open_reaction_window(action)
    rx.offer_reaction(chain, "player", "reflexo", card=_reacao())
    # a reação do player vira uma "ação" kind=reaction; carta com gatilho "sempre"
    # (ou que casa reaction) pode responder a ela (R2)
    ok = rx.offer_reaction(chain, "aliado", "eco",
                           card=_reacao("eco", gatilho="sempre"), respond_to_link=0)
    assert ok is True
    assert len(chain["links"]) == 2


def test_ordem_alvo_direto_depois_aliados_depois_agilidade():
    action = {"kind": "attack", "actor": "inimigo", "targets": ["player"]}
    stats = {
        "player": _stats(agilidade=1),
        "aliado_lento": _stats(agilidade=1),
        "aliado_rapido": _stats(agilidade=4),
        "colega_inimigo": _stats(agilidade=5),
    }
    ordem = rx.reaction_order(
        ["colega_inimigo", "aliado_lento", "aliado_rapido", "player"],
        action, stats_by_id=stats,
        target_allies=["aliado_lento", "aliado_rapido"],
        actor_allies=["colega_inimigo"],
    )
    # alvo direto primeiro, depois aliados do alvo (mais ágil antes), depois aliados do ator
    assert ordem == ["player", "aliado_rapido", "aliado_lento", "colega_inimigo"]


# ==========================================================================
# Etapa 3 — Ataques de oportunidade (R5, fora do limite de cadeia)
# ==========================================================================
def test_fuga_engajado_gera_aoo_de_todos_inimigos_aptos():
    s = _scene("player", "orc1", "orc2", "orc3")
    for orc in ("orc1", "orc2", "orc3"):
        cs.engage(s, "player", orc, spend=False)
    stats = {o: _stats() for o in ("orc1", "orc2", "orc3")}
    aoos = rx.trigger_opportunity_attack(s, "player", allies=[], stats_by_id=stats)
    assert {a["attacker"] for a in aoos} == {"orc1", "orc2", "orc3"}
    assert all(a["target"] == "player" and a["counts_common"] is False for a in aoos)


def test_aoo_pula_aliados_e_inconscientes():
    s = _scene("player", "orc1", "aliado", "orc_caido")
    for other in ("orc1", "aliado", "orc_caido"):
        cs.engage(s, "player", other, spend=False)
    stats = {"orc1": _stats(), "aliado": _stats(),
             "orc_caido": _stats(conscious=False)}
    aoos = rx.trigger_opportunity_attack(s, "player", allies=["aliado"], stats_by_id=stats)
    assert {a["attacker"] for a in aoos} == {"orc1"}   # aliado excluído, inconsciente pulado


def test_aoo_nao_conta_pro_limite_de_reacao_comum():
    # inimigo que já gastou a reação comum na cadeia AINDA faz AoO (funções separadas)
    action = {"kind": "attack", "actor": "player", "targets": ["orc1"]}
    chain = rx.open_reaction_window(action)
    rx.offer_reaction(chain, "orc1", "reflexo", card=_reacao())
    assert "orc1" in chain["used_common_reaction"]

    s = _scene("player", "orc1")
    cs.engage(s, "player", "orc1", spend=False)
    aoos = rx.trigger_opportunity_attack(s, "player", allies=[],
                                         stats_by_id={"orc1": _stats()})
    assert [a["attacker"] for a in aoos] == ["orc1"]   # AoO independe da cadeia


# ==========================================================================
# Etapa 4 — Engajar / Desengajar / Guardar (R6/R7/R8)
# ==========================================================================
def test_engajar_custa_pre_ou_pos_acao():
    s = _scene("player", "orc")
    r1 = cs.engage(s, "player", "orc")
    assert r1["ok"] and r1["via"] in ("pre_acao", "pos_acao")
    b = s["positions"]["player"]["budget"]
    assert b["pre_acao"] + b["pos_acao"] == 1          # gastou 1 dos 2
    # gastar a Ação também não impede: mas exaurir pre+pos bloqueia novo Engajar
    cs.place(s, "orc2")
    cs.engage(s, "player", "orc2")                     # gasta o outro pre/pos
    cs.place(s, "orc3")
    r3 = cs.engage(s, "player", "orc3")
    assert r3["ok"] is False and "Pré/Pós" in r3["error"]


def test_desengajar_custa_acao_evita_aoo():
    s = _scene("player", "orc")
    cs.engage(s, "player", "orc", spend=False)
    r = cs.disengage(s, "player", "orc")
    assert r["ok"] and r["safe"] is True
    assert s["positions"]["player"]["budget"]["acao"] == 0
    assert not cs.is_engaged(s, "player", "orc")
    # Desengajar sem Ação disponível falha
    cs.place(s, "orc2")
    cs.engage(s, "player", "orc2", spend=False)
    r2 = cs.disengage(s, "player", "orc2")
    assert r2["ok"] is False


def test_guardar_desvantagem_nos_dois_lados():
    s = _scene("player", "orc")
    r = cs.guard(s, "player")
    assert r["ok"] and cs.is_guarding(s, "player")
    assert s["positions"]["player"]["budget"]["acao"] == 0
    # ataque CONTRA quem Guarda → Desvantagem; ataque DE quem Guarda → Desvantagem (R8)
    assert cs.guard_defense_modifier(s, "player") == -1
    assert cs.guard_offense_modifier(s, "player") == -1
    cs.stop_guard(s, "player")
    assert cs.guard_defense_modifier(s, "player") == 0


# ==========================================================================
# Etapa 5 — Esconder-se / Procurar / alertar (R9/R10/R11)
# ==========================================================================
def test_esconder_exige_fonte_plausivel():
    s = _scene("player", "orc")
    sem_fonte = cs.hide(s, "player", source="")
    assert sem_fonte["ok"] is False
    com_fonte = cs.hide(s, "player", source="fumaça densa")
    assert com_fonte["ok"] is True
    assert cs.is_hidden_from(s, "player", "orc")
    assert s["positions"]["player"]["budget"]["acao"] == 0


def test_ocultacao_relativa_por_observador():
    s = _scene("player", "orc_a", "orc_b")
    cs.hide(s, "player", source="pilar", observers=["orc_a"])
    assert cs.is_hidden_from(s, "player", "orc_a")       # escondido de A
    assert not cs.is_hidden_from(s, "player", "orc_b")   # visível para B


def test_atacar_com_posicao_aproximada_tem_desvantagem():
    s = _scene("player", "orc")
    cs.hide(s, "player", source="escuridão", observers=["orc"])
    # sem posição: orc não pode mirar direto
    v0 = cs.occlusion_attack_modifier(s, "orc", "player")
    assert v0["can_target"] is False
    # com posição aproximada (via alerta): pode mirar, mas com Desvantagem
    cs.place(s, "orc2")
    cs.alert_party(s, "orc2", "player", ["orc"])
    v1 = cs.occlusion_attack_modifier(s, "orc", "player")
    assert v1["can_target"] is True and v1["advantage"] == -1


def test_alertar_party_propaga_posicao_aproximada():
    s = _scene("player", "orc_a", "orc_b", "orc_c")
    cs.hide(s, "player", source="neblina", observers=["orc_a", "orc_b", "orc_c"])
    cs.alert_party(s, "orc_a", "player", ["orc_b", "orc_c"])
    assert cs.has_approx_position(s, "player", "orc_b")
    assert cs.has_approx_position(s, "player", "orc_c")
    # ainda Escondido (aproximado não revela)
    assert cs.is_hidden_from(s, "player", "orc_b")


def test_atacar_oculto_da_vantagem_e_move_encerra_escondido():
    s = _scene("player", "orc")
    cs.hide(s, "player", source="sombra", observers=["orc"])
    v = cs.occlusion_attack_modifier(s, "player", "orc")   # player ataca oculto
    assert v["advantage"] == 1                              # Vantagem (R11)
    cs.reveal_after_attack(s, "player")
    assert not cs.is_hidden_from(s, "player", "orc")
    # e mudar de distância também encerra o Escondido (R11)
    cs.hide(s, "player", source="sombra", observers=["orc"])
    cs.move_distance(s, "player", "afastar")
    assert not cs.is_hidden_from(s, "player", "orc")
