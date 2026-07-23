"""Suíte da spec conflito-04: Turnos, Iniciativa e Ataques (motor de resolução).

100% determinístico: `SeqRNG` injeta rolagens fixas em `services/conflict_resolution`."""

from services import conflict_resolution as cr


class SeqRNG:
    """RNG determinístico: randint devolve a sequência dada, em ordem."""
    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0

    def randint(self, a, b):
        v = self.seq[self.i]
        self.i += 1
        return v


def _actor(ag=1, forca=1, mente=1, corpo=1, carisma=1, **over):
    a = {"virtudes": {"agilidade": ag, "forca": forca, "mente": mente,
                      "corpo": corpo, "carisma": carisma}}
    a.update(over)
    return a


# --------------------------------------------------------------------------
# Etapa 1 — Iniciativa por lado
# --------------------------------------------------------------------------
def test_lado_iniciador_age_primeiro_sem_disputa():
    sides = {"party": [_actor(ag=1)], "inimigos": [_actor(ag=5)]}
    r = cr.roll_initiative_by_side(sides, initiator="party", rng=SeqRNG([1, 1, 1, 1]))
    assert r["order"][0] == "party" and r["auto"] is True
    assert r["rolls"]["party"] is None  # iniciador não disputa


def test_disputa_2d10_maior_agilidade():
    sides = {"party": [_actor(ag=4)], "inimigos": [_actor(ag=0)]}
    # party rola 5,5 (+4=14); inimigos rola 6,6 (+0=12) -> party vence mesmo com dados menores? 14>12
    r = cr.roll_initiative_by_side(sides, rng=SeqRNG([5, 5, 6, 6]))
    assert r["order"][0] == "party" and r["auto"] is False
    assert r["rolls"]["party"]["total"] == 14


def test_iniciativa_e_por_lado_nao_por_participante():
    sides = {"party": [_actor(), _actor()], "inimigos": [_actor()]}
    r = cr.roll_initiative_by_side(sides, rng=SeqRNG([3, 3, 4, 4]))
    # ordem é de LADOS (o jogador reordena a party internamente a cada rodada)
    assert set(r["order"]) == {"party", "inimigos"}


# --------------------------------------------------------------------------
# Etapa 2 — Ataque 2d10 + Virtude vs Esquiva
# --------------------------------------------------------------------------
def test_ataque_normal_2d10_mais_virtude():
    atk = _actor(forca=3)
    alvo = _actor(ag=2)  # esquiva 12
    r = cr.resolve_attack(atk, alvo, virtude_key="forca", rng=SeqRNG([4, 5]))
    assert r["dice_kept"] == [4, 5] and r["virtude"] == 3
    assert r["total"] == 12 and r["esquiva_alvo"] == 12
    assert r["resultado"] == "acerto" and r["efeito_principal_multiplicador"] == 1


def test_ataque_erro_abaixo_da_esquiva():
    r = cr.resolve_attack(_actor(forca=0), _actor(ag=5), virtude_key="forca",
                          rng=SeqRNG([2, 3]))
    assert r["resultado"] == "erro" and r["acerto"] is False


def test_critico_dupla_1a9():
    # dupla 5-5 = Crítico automático mesmo contra Esquiva altíssima
    r = cr.resolve_attack(_actor(forca=1), _actor(ag=5), virtude_key="forca",
                          esquiva=99, rng=SeqRNG([5, 5]))
    assert r["resultado"] == "critico" and r["acerto"] is True
    assert r["efeito_principal_multiplicador"] == 2


def test_supercritico_dupla_10():
    r = cr.resolve_attack(_actor(forca=1), _actor(), virtude_key="forca",
                          esquiva=99, rng=SeqRNG([10, 10]))
    assert r["resultado"] == "supercritico" and r["efeito_principal_multiplicador"] == 3


def test_efeito_principal_multiplicado_nao_secundario():
    efeitos = [{"kind": "damage", "principal": True, "valor": 10},
               {"kind": "apply_condition", "principal": False, "valor": 3}]
    out = cr.multiply_principal(efeitos, 2)
    assert out[0]["valor"] == 20 and out[1]["valor"] == 3


# --------------------------------------------------------------------------
# Etapa 3 — Vantagem / Desvantagem
# --------------------------------------------------------------------------
def test_vantagem_3d10_mantem_dois_maiores():
    r = cr.resolve_attack(_actor(forca=0), _actor(), virtude_key="forca",
                          advantage=1, esquiva=99, rng=SeqRNG([2, 7, 9]))
    assert r["dice_rolled"] == [2, 7, 9] and r["dice_kept"] == [7, 9]


def test_desvantagem_3d10_mantem_dois_menores():
    r = cr.resolve_attack(_actor(forca=0), _actor(), virtude_key="forca",
                          advantage=-1, esquiva=99, rng=SeqRNG([2, 7, 9]))
    assert r["dice_kept"] == [2, 7]


def test_vantagem_e_desvantagem_se_cancelam():
    assert cr.net_advantage(1, 1) == 0
    assert cr.net_advantage(1, 0) == 1
    assert cr.net_advantage(0, 1) == -1
    assert cr.net_advantage(2, 1) == 1   # magnitude não acumula, só o sinal
    # net 0 -> rola 2d10 (não 3)
    roll = cr.roll_kept(cr.net_advantage(1, 1), SeqRNG([4, 6]))
    assert len(roll["rolled"]) == 2


# --------------------------------------------------------------------------
# Etapa 4 — Testes gerais (Ímpeto + Presságio + Virtude)
# --------------------------------------------------------------------------
def test_impeto_maior_consequencia_favoravel():
    r = cr.general_test(_actor(mente=2), "mente", "comum", rng=SeqRNG([8, 3]))
    assert r["impeto"] == 8 and r["pressagio"] == 3
    assert r["total"] == 13 and r["sucesso"] is True
    assert r["consequencia"] == "favoravel"


def test_pressagio_maior_desfavoravel():
    r = cr.general_test(_actor(mente=0), "mente", "comum", rng=SeqRNG([3, 8]))
    assert r["consequencia"] == "desfavoravel"


def test_empate_resultado_puro():
    r = cr.general_test(_actor(mente=1), "mente", "facil", rng=SeqRNG([5, 5]))
    assert r["consequencia"] == "puro"


def test_dificuldades_base_corretas():
    assert cr.DIFICULDADES == {"facil": 9, "comum": 12, "dificil": 15,
                               "extremo": 18, "quase_impossivel": 21}


def test_ataque_nao_usa_matriz_de_consequencia():
    r = cr.resolve_attack(_actor(forca=2), _actor(), virtude_key="forca", rng=SeqRNG([4, 4]))
    assert "consequencia" not in r  # ataque não tem Ímpeto/Presságio


# --------------------------------------------------------------------------
# Etapa 5 — Ruptura
# --------------------------------------------------------------------------
def test_ruptura_ataque_concede_vantagem():
    # ruptura -> advantage +1 -> rola 3 dados
    r = cr.resolve_attack(_actor(forca=0), _actor(), virtude_key="forca",
                          ruptura=True, esquiva=99, rng=SeqRNG([2, 7, 9]))
    assert len(r["dice_rolled"]) == 3 and r["dice_kept"] == [7, 9]
    assert r["ruptura"] is True


def test_ruptura_teste_geral_dois_impeto_mantem_maior():
    r = cr.general_test(_actor(mente=1), "mente", "comum", ruptura=True,
                        rng=SeqRNG([4, 9, 3]))
    assert r["impetos_rolados"] == [4, 9] and r["impeto"] == 9
    assert r["pressagio"] == 3


def test_ruptura_e_critico_acumulam():
    # 3 dados (vantagem por ruptura), mantém [5,5] -> Crítico + ruptura
    r = cr.resolve_attack(_actor(forca=1), _actor(), virtude_key="forca",
                          ruptura=True, esquiva=99, rng=SeqRNG([5, 5, 2]))
    assert r["resultado"] == "critico" and r["ruptura"] is True
