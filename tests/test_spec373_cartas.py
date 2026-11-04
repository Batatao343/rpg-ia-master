"""SPEC-373 R14-R16: Cartas comuns de família novas (`origem: cartas-373`)."""

from __future__ import annotations

import collections

import pytest

from services import card_effects as fx
from services import card_lint, cards
from services import enemy_decks as edk

ORIGEM = "cartas-373"


@pytest.fixture(autouse=True)
def _reload():
    edk.reload()
    yield
    edk.reload()


def _familias() -> dict[str, list[dict]]:
    return {
        fam: [fx.materialize(cards.get_card(i)) for i in ids]
        for fam, ids in edk._pools()["familias"].items()
    }


def _novas() -> list[tuple[str, dict, list[dict]]]:
    out = []
    for fam, lst in _familias().items():
        for c in lst:
            if c.get("origem") == ORIGEM:
                out.append((fam, c, [o for o in lst if o["id"] != c["id"]]))
    return out


def test_ha_cartas_373_nas_familias_que_o_r14_pede():
    por_fam = collections.Counter(fam for fam, _c, _o in _novas())
    assert por_fam == {
        "covarde_oportunista": 6,
        "tatico": 7,
        "predador": 4,
        "bruto": 4,
        "guardiao": 3,
        "emboscador": 2,
        "conjurador": 1,
        "morto_vivo_implacavel": 1,
    }


def test_cartas_373_vocabulario_orcamento_voz():
    catalogo = list(cards._load_cards().values())
    bad = {}
    for fam, c, outras in _novas():
        assert c["classe"] == "Inimigo" and c["subclasse"] == fam and c["patamar"] == "inicial"
        assert c["id"].startswith(f"inf_{fam}_")
        resto = [o for o in catalogo if o["id"] != c["id"]]
        issues = (
            card_lint.check_vocabulary(c)
            + card_lint.check_budget(c)
            + card_lint.check_voice(c)
            + card_lint.check_names(c, resto)
            + card_lint.check_redundancy(c, outras)  # unicidade dentro da família
        )
        if issues or fx.budget_error(c):
            bad[c["id"]] = [str(i) for i in issues] + [fx.budget_error(c) or ""]
    assert not bad, bad


def test_cartas_373_nao_mais_fortes_que_a_familia():
    for fam, c, outras in _novas():
        antigas = [o for o in outras if o.get("origem") != ORIGEM]
        assert fx.power_score(c) <= max(fx.power_score(o) for o in antigas), (fam, c["id"])


def test_cartas_373_sem_dano_de_conjurador_nem_reforco():
    for _fam, c, _o in _novas():
        for eff in fx.normalize(c):
            assert str(eff.get("dano_tipo") or "") not in edk._CASTER_DAMAGE, c["id"]
        assert "reforc" not in str(c).lower()


def test_r14_nao_cria_assinatura_nova():
    meta = edk._meta()["familias"]
    sigs = {str(s["carta"]) for f in meta.values() for s in f["assinaturas"]}
    assert not {c["id"] for _f, c, _o in _novas()} & sigs


def test_uso_populacao_inteira_ate_15(monkeypatch):
    """R16: nenhuma `inf_*` em mais de 15 criaturas, sementes 0-11, ids de instância."""
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    from agents.bestiary import load_bestiary

    best = load_bestiary()
    pico = collections.Counter()
    for seed in range(12):
        use = collections.Counter()
        for bid, entry in best.items():
            deck = edk.build_enemy_deck({**entry, "id": f"{bid}_1"}, seed)
            use.update(c for c in deck if c.startswith("inf_"))
        for k, v in use.items():
            pico[k] = max(pico[k], v)
    assert max(pico.values()) <= 15, pico.most_common(5)


# --- Motor: `buff_iniciativa` como efeito principal de Carta ativa (revisões Sol P1-2 / Opus P1-1) --
# A Carta de dados da Parte C (Mão Adiantada, R21) migrou para a SPEC-369 B2 (D9 da 373), que
# entrega a passiva `cor1_tro_faro_do_abismo`. A correção de motor (`_SUPPORT_EFFECTS`) fica e é
# provada com uma Carta sintética de fixture, sem depender do acervo.

SYN_INI = "t_ini_ativa"


def _carta_ini() -> dict:
    return fx.materialize(
        {
            "id": SYN_INI,
            "name": "Passo Sintético",
            "tipo": "ativa",
            "origem": "teste",
            "classe": "Corruptor",
            "subclasse": "",
            "raridade": "comum",
            "custo_entropia": 2,
            "custo_folego": 1,
            "frequencia": "cena",
            "virtude_permitida": ["mente"],
            "efeitos": [{"kind": "buff_iniciativa", "valor": 2}],
            "descricao": "Carta de teste.",
            "tier": 1,
            "level_req": 1,
            "apex": False,
            "versao": 1,
        }
    )


def _jogar_carta_ini(monkeypatch):
    import random

    from services import card_piles as cp
    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs
    from services import conflict_turn as ct

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setitem(cards._load_cards(), SYN_INI, _carta_ini())
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Corruptor",
            "known_cards": [SYN_INI],
            "prepared_cards": [SYN_INI],
            "virtudes": {"forca": 2, "agilidade": 3, "corpo": 3, "mente": 3, "carisma": 1},
            "entropy": 8,
            "max_entropy": 10,
            "abyss_charge": 0,
        },
        is_player=True,
    )
    cp.migrate_deck(player)
    enemy = orch.ensure_combat_sheet(
        {
            "id": "gob_1",
            "name": "Goblin",
            "type": "Minion",
            "hp": 40,
            "max_hp": 40,
            "ac": 11,
            "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
        }
    )
    piles = cp.start_piles(player, 11)
    piles["mao"] = [SYN_INI]
    scene = cs.new_scene()
    for aid in ("player", "gob_1"):
        cs.place(scene, aid)
    cs.freeze(scene)
    state = {"player": player, "_piles": piles, "_deck_mode": "on"}
    actors = {"player": player, "gob_1": enemy}
    sides = {"hero": ["player"], "enemy": ["gob_1"]}
    step = ct.TurnStep(kind="card", card_id=SYN_INI, target_id="player")
    decl = ct.TurnDeclaration(actor_id="player", jogadas=[step])
    out = orch.run_round(
        scene, actors, sides, state, declarations={"player": decl}, rng=random.Random(5)
    )
    return out, player, enemy, state, (scene, actors, sides)


def test_buff_iniciativa_ativo_grava_condicao_de_iniciativa(monkeypatch):
    out, player, _e, state, _w = _jogar_carta_ini(monkeypatch)
    assert not any("sem resolução" in line for line in out["logs"])
    conds = [c for c in player["active_conditions"] if c.get("source") == SYN_INI]
    assert conds and conds[0]["stat"] == "initiative" and conds[0]["delta"] == 2
    assert state["_piles"]["exaurida"] == [SYN_INI]  # frequência `cena`


def test_buff_iniciativa_ativo_vale_na_rolagem_da_rodada_seguinte(monkeypatch):
    import random

    from services import conflict_orchestrator as orch
    from services import conflict_resolution as cr
    from services import conflict_turn as ct

    _out, player, _e, state, (scene, actors, sides) = _jogar_carta_ini(monkeypatch)
    base = cr.virtude_value(player, "agilidade")
    seen: list[int] = []
    real = cr._initiative_value

    def spy(actor):
        v = real(actor)
        if actor is player:
            seen.append(v)
        return v

    monkeypatch.setattr(cr, "_initiative_value", spy)
    passe = ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))
    orch.run_round(
        scene, actors, sides, state, declarations={"player": passe}, rng=random.Random(6)
    )
    assert seen and max(seen) == base + 2, (base, seen)
