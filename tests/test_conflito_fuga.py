"""Suíte da spec conflito-09: fuga e perseguição.

100% determinístico. Exercita `services/chase.py` (trilha, condutor/dificuldade,
Teste de Sorte, abandono simulado por seed, sacrifício e ataques em perseguição).
Rolagens usam um rng fixo (min/max) para tornar avanço/recuo exatos."""

from services import chase
from services import conflict_scene as cs


class _Rng:
    def __init__(self, high):
        self.high = high

    def randint(self, a, b):
        return b if self.high else a


def _predador():
    return {"id": "predador", "pursuit_policy": "persegue", "tactical_profile": {"priorities": [
        {"trigger": "alvo_fugindo", "tipo": "obrigatorio", "action_hint": "persegue a presa"},
        {"trigger": "sempre", "tipo": "obrigatorio", "action_hint": "ataca"},
    ]}}


def _guardiao():
    return {"id": "guardiao", "pursuit_policy": "nao_persegue", "tactical_profile": {"priorities": [
        {"trigger": "sempre", "tipo": "obrigatorio", "action_hint": "não abandona o posto"},
    ]}}


# ==========================================================================
# Etapa 1 — trilha de perseguição (R2/R3)
# ==========================================================================
def test_posicao_inicial_deriva_da_distancia():
    assert chase.initial_track("proximo") == "pressionado"
    assert chase.initial_track("distante") == "afastado"
    assert chase.initial_track("separado") == "quase_livre"


def test_recuar_abaixo_de_pressionado_e_alcancado():
    ch = {"trilha": "pressionado"}
    chase.resolve_chase_round(ch, condutor_virtude=0, difficulty=99, rng=_Rng(high=False))
    assert ch["trilha"] == "alcancado" and ch["alcancado"] is True


def test_perseguidor_so_persegue_se_perfil_permitir():
    s = cs.new_scene()
    cs.place(s, "player", distance_state="proximo")
    ch = chase.start_chase(s, "player", [_predador(), _guardiao()])
    assert ch["perseguidores"] == ["predador"]      # guardião não persegue
    assert ch["trilha"] == "pressionado"


def test_sem_perseguidor_disposto_escapa():
    s = cs.new_scene()
    cs.place(s, "player", distance_state="proximo")
    ch = chase.start_chase(s, "player", [_guardiao()])
    assert ch["trilha"] == "escapou" and ch["escapou"] is True


def test_prosa_nao_autoriza_perseguicao_sem_politica_fechada():
    fake = {"id": "fake", "tactical_profile": {"priorities": [
        {"trigger": "alvo_fugindo", "action_hint": "persegue para sempre"},
    ]}}
    assert chase.will_pursue(fake) is False


# ==========================================================================
# Etapa 2 — condutor + dificuldade (R4)
# ==========================================================================
def test_condutor_e_sempre_protagonista():
    party = [{"name": "aliado"}, {"name": "herói", "is_player": True}]
    assert chase.chase_conductor(party)["name"] == "herói"


def test_dificuldade_depende_do_perseguidor_principal():
    lento = {"virtudes": {"agilidade": 1}}
    veloz = {"virtudes": {"agilidade": 5}}
    assert chase.chase_difficulty(veloz) > chase.chase_difficulty(lento)


def test_abordagem_mapeia_virtude():
    assert chase.approach_virtude("rotas") == "mente"
    assert chase.approach_virtude("romper") == "forca"
    assert chase.approach_virtude("desconhecida") == "agilidade"


# ==========================================================================
# Etapa 3 — Teste de Sorte dos companheiros (R5)
# ==========================================================================
def test_1d10_faixas_complicacao_neutro_ajuda():
    assert chase.luck_roll(_Rng(high=False)) == -1     # rola 1 → Complicação
    assert chase.luck_roll(_Rng(high=True)) == 1        # rola 10 → Ajuda


def test_ajuda_e_complicacao_se_anulam():
    assert chase.luck_to_advantage([1, -1]) == 0


def test_nao_acumula_alem_de_uma_vantagem():
    assert chase.luck_to_advantage([1, 1, 1]) == 1
    assert chase.luck_to_advantage([-1, -1]) == -1


# ==========================================================================
# Etapa 4 — abandono + simulação automática (R6)
# ==========================================================================
def test_abandonar_remove_complicacao_separa_npc():
    party = [{"id": "hero", "is_player": True}, {"id": "peso_morto"}]
    removido = chase.abandon_companion(party, "peso_morto")
    assert removido["separated"] is True
    assert all((m.get("id") != "peso_morto") for m in party)   # saiu da party


def test_simulacao_e_deterministica_por_seed():
    comp = {"name": "Bran", "vitalidade": 5, "max_vitalidade": 20,
            "virtudes": {"agilidade": 2}}
    a = chase.simulate_abandoned_companion(comp, {"pursuers": 2}, seed=1234)
    b = chase.simulate_abandoned_companion(comp, {"pursuers": 2}, seed=1234)
    assert a["resultado"] == b["resultado"]                     # mesma seed → mesmo destino
    assert a["resultado"] in chase.ABANDON_OUTCOMES


def test_resultado_gera_fatos_relacionais():
    comp = {"name": "Bran", "vitalidade": 20, "max_vitalidade": 20}
    out = chase.simulate_abandoned_companion(comp, {}, seed=7)
    assert out["fatos_relacionais"] and len(out["fatos_relacionais"]) >= 2


# ==========================================================================
# Etapa 5 — sacrifício voluntário + ataques em perseguição (R7/R8)
# ==========================================================================
def test_sacrificio_so_com_traco_e_prioridade_valida():
    com_traco = {"se_sacrifica_pelo_grupo": True}
    sem_traco = {"tactical_profile": {"priorities": [
        {"trigger": "sempre", "action_hint": "foge sozinho"}]}}
    assert chase.can_volunteer_sacrifice(com_traco) is True
    assert chase.can_volunteer_sacrifice(sem_traco) is False


def test_jogador_pode_recusar_sacrificio():
    comp = {"se_sacrifica_pelo_grupo": True}
    recusa = chase.offer_sacrifice(comp, accept=False)
    assert recusa["sacrificed"] is False
    aceita = chase.offer_sacrifice(comp, accept=True)
    assert aceita["sacrificed"] is True and comp["sacrificed"] is True


def test_ataque_distancia_continua_acao_normal_em_perseguicao():
    ch = {"trilha": "afastado"}
    r = chase.chase_attack(ch, melee=False)
    assert r["allowed"] is True and r["ends_chase"] is False


def test_reengajar_em_pressionado_encerra_perseguicao():
    ch = {"trilha": "pressionado"}
    r = chase.chase_attack(ch, melee=True)
    assert r["ends_chase"] is True and ch["trilha"] == "alcancado"
    # em Afastado, corpo a corpo precisa reduzir distância antes
    ch2 = {"trilha": "afastado"}
    r2 = chase.chase_attack(ch2, melee=True)
    assert r2["allowed"] is False and r2["mode"] == "precisa_reduzir_distancia"
