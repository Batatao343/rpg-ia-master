"""SPEC-353 etapa 2/3: ordem unica, auto-dano, contrato do round_board, autoria do resumo."""

from __future__ import annotations

import random
import re

import pytest

from services import combat_preview as preview
from services import conflict_orchestrator as orch
from services import conflict_summary as summ
from services import conflict_turn as ct
from services import round_log
from tests.test_fix_vitalidade_terminal import _actor, _scene

SIDES = {"hero": ["player"], "ally": [], "enemy": ["boss"]}
ID_RE = re.compile(
    r"\b(cena|bas|dev|san|cor|arc|vig|bst|inf|mon|npc|enemy|fallback|sus)_[a-z0-9_]+\b"
)


def _sangromante_round(seed: int, card_id: str = "san_corte_troca", initiator="heroes"):
    hero = _actor("player", corpo=5, is_player=True)
    hero["class_name"] = "Sangromante"
    hero["prepared_cards"] = [card_id]
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 3
    decl = ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="card", card_id=card_id, target_id="boss")
    )
    vit_before = hero["vitalidade"]
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={"player": decl},
        initiator=initiator,
        state={"player": hero},
        rng=random.Random(seed),
    )
    return hero, boss, out, vit_before


@pytest.mark.parametrize("card_id", ["san_corte_troca", "bas_san_corte_raso"])
@pytest.mark.parametrize("seed", range(10))
def test_self_harm_line_and_oracle(seed, card_id):
    hero, boss, out, vit_before = _sangromante_round(seed, card_id)
    harm = [m for m in out["class_mechanics"] if m["kind"] == "self_harm"]
    assert harm and harm[0]["actor_id"] == "player" and harm[0]["card_id"] == card_id
    lines = preview.mech_log(out["attacks"], [hero, boss], out["ticks"], out=out)
    assert any("· custo ·" in ln and ln.startswith("Você · ") for ln in lines)
    reg = round_log.round_registry(out, {"player": hero, "boss": boss})
    assert any(ln.startswith("Você paga ") for ln in reg)
    board = preview.round_board(out, [hero, boss], {"boss"})
    assert any(e["tipo"] == "custo" and e["dano"] == harm[0]["amount"] for e in board)
    assert not any(ID_RE.search(ln) for ln in [*lines, *reg])
    # R14: o custo nunca some da conta de Vitalidade do heroi
    paid = harm[0]["amount"]
    drop = vit_before - hero["vitalidade"]
    assert drop >= min(paid, vit_before)


def test_one_order_in_three_surfaces():
    """R12: inimigo age primeiro (emboscada) -> aparece primeiro nas 3 superficies."""
    hero = _actor("player", corpo=5, is_player=True)
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 2
    decl = ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(kind="attack", target_id="boss", params={"dano_base": 3}),
    )
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={"player": decl},
        initiator="enemy",
        rng=random.Random(5),
    )
    assert out["attacks"][0]["actor_id"] == "boss"
    reg = round_log.round_registry(out, {"player": hero, "boss": boss})
    lines = preview.mech_log(out["attacks"], [hero, boss], out["ticks"], out=out)
    board = preview.round_board(out, [hero, boss], {"boss"})
    assert reg[0].startswith("Boss ataca")
    assert lines[0].startswith("Boss")
    assert board[0]["ator_id"] == "boss"


def test_round_board_tipo_and_dot_source():
    out = {
        "attacks": [],
        "ticks": [{"actor_id": "boss", "condition": "Sangramento", "dano_final": 1}],
        "turn_spans": [{"actor_id": "boss", "attacks": [0, 0], "cards": [0, 0]}],
        "deaths": ["boss"],
        "sem_vitalidade": [{"actor_id": "boss"}],
    }
    actors = [{"id": "boss", "name": "Criatura"}, {"id": "npc_ketil", "name": "Ketil"}]
    fontes = {"boss": {"Sangramento": "npc_ketil"}}
    board = preview.round_board(out, actors, {"boss"}, fontes=fontes)
    tick = board[0]
    assert tick["tipo"] == "dano_continuo" and tick["ator_id"] == "npc_ketil"
    assert tick["ator_nome"] == "Ketil" and tick["alvo_nome"] == "Criatura"
    assert {e["tipo"] for e in board} == {"dano_continuo", "queda"}
    unknown = preview.round_board(out, actors, {"boss"})[0]
    assert unknown["ator_id"] is None and unknown["lado"] == "efeito"
    assert unknown["ator_nome"] == "Sangramento"


def test_flee_roll_in_mech_log():
    out = {"fuga": {"total": 7, "dificuldade": 11, "sucesso": False}}
    assert preview.mech_log([], [], out=out) == ["Fuga · total 7 vs 11 · falhou"]


def test_zero_vitality_line_once():
    actor = {"id": "boss", "name": "Anão-Eco", "categoria": "elite", "virtudes": {"corpo": 3}}
    out = {"attacks": [], "sem_vitalidade": [{"actor_id": "boss"}]}
    reg = round_log.round_registry(out, {"boss": actor})
    assert len(reg) == 1 and reg[0].startswith("Anão-Eco está sem Vitalidade — cada golpe")


def test_final_blow_dot_recorded():
    boss = _actor("boss", corpo=0, categoria="lacaio", vitalidade=1)
    boss["active_conditions"] = [
        {"name": "Sangramento", "dot": 5, "duration": 3, "damage_type": "cortante"}
    ]
    hero = _actor("player", corpo=5, is_player=True)
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={},
        initiator="enemy",
        rng=random.Random(2),
    )
    blows = out.get("final_blows") or []
    assert blows and blows[0]["kind"] == "dano_continuo" and blows[0]["condition"] == "Sangramento"


# --- autoria do resumo (R8/R11) ---
def _auth(**kw):
    base = {"hero_cards": {}, "final_by_hero": False, "final_on_enemy": False}
    base.update(kw)
    return base


def test_attribution_rejects_smoke_texts():
    d5 = "O Sussurro Faminto, num estalo, encontra teu torso e te lança ao chão."
    assert "V1" in summ.validate_attribution(d5, _auth(hero_cards={"Sussurro Faminto": "hit"}))
    k4 = "Sua espada desce duas vezes, e a criatura desmorona na lama."
    assert "V3" in summ.validate_attribution(k4, _auth(final_on_enemy=True))
    r6 = "O Corte de Troca não encontra alvo, e o silêncio cai."
    assert "V2" in summ.validate_attribution(r6, _auth(hero_cards={"Corte de Troca": "hit"}))


def test_attribution_accepts_correct_texts():
    ok1 = "O Sussurro Faminto rasga a sombra diante de você, e o Anão-Eco cambaleia."
    assert not summ.validate_attribution(ok1, _auth(hero_cards={"Sussurro Faminto": "hit"}))
    ok2 = "Sua espada corta o ar sem achar nada; é o Sangramento que derruba a criatura."
    assert not summ.validate_attribution(ok2, _auth(final_on_enemy=True))
    ok3 = "O Corte de Troca encontra o alvo em cheio e a luta acaba."
    assert not summ.validate_attribution(ok3, _auth(hero_cards={"Corte de Troca": "hit"}))


def test_facts_have_actor_target_result_and_no_digits():
    hero = {"name": "Haldor", "vitalidade": 5, "max_vitalidade": 10}
    enemy = {"id": "c1", "name": "Criatura", "status": "ativo"}
    last_out = {
        "attacks": [
            {"actor_id": "player", "target_id": "c1", "acerto": False, "resultado": "erro"}
        ],
        "ticks": [{"actor_id": "c1", "condition": "Sangramento", "dano_final": 3}],
        "final_blows": [
            {
                "target_id": "c1",
                "kind": "dano_continuo",
                "by_actor_id": None,
                "condition": "Sangramento",
            }
        ],
    }
    facts = round_log.outcome_facts("victory", {}, hero, [enemy], last_out)
    text = "\n".join(facts)
    assert "Você atacou em Criatura: errou." in text
    assert "Sangramento corroeu Criatura." in text
    assert "Golpe final: o Sangramento (dano contínuo) em Criatura." in text
    assert "Seu último golpe errou." in text
    assert not re.search(r"\d", text)


def test_fallback_names_final_blow():
    blow = {"target_id": "c1", "kind": "dano_continuo", "condition": "Sangramento"}
    text = round_log.deterministic_outcome_text(
        "victory",
        {"mortos": ["Criatura"]},
        {"name": "Haldor"},
        last_out={"final_blows": [blow]},
        names={"c1": "Criatura"},
    )
    assert "O Sangramento termina o serviço: Criatura tomba." in text


def test_final_blow_attack_recorded_with_card():
    hero = _actor("player", corpo=5, is_player=True)
    foe = _actor("boss", corpo=0, categoria="lacaio", vitalidade=0)
    decl = ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(kind="attack", target_id="boss", params={"dano_base": 9}),
    )
    for seed in range(40):
        foe2 = dict(foe, ferimentos={"leve": [], "grave": [], "critico": []}, dead=False)
        out = orch.run_round(
            _scene("player", "boss"),
            {"player": dict(hero), "boss": foe2},
            SIDES,
            declarations={"player": decl},
            initiator="heroes",
            rng=random.Random(seed),
        )
        blows = [b for b in out.get("final_blows") or [] if b["target_id"] == "boss"]
        if blows:
            assert blows[0]["kind"] == "ataque" and blows[0]["by_actor_id"] == "player"
            return
    raise AssertionError("nenhum golpe final registrado em 40 seeds")


@pytest.mark.parametrize("card_id", ["san_corte_troca", "bas_san_corte_raso"])
@pytest.mark.parametrize("seed", range(20))
def test_r14_exact_sum_with_self_harm(seed, card_id, monkeypatch):
    """R14: custo da linha == Vitalidade realmente perdida pelo custo; conta total fecha exata."""
    from services import conflict_damage as cd

    hero = _actor("player", corpo=5, is_player=True)
    hero["class_name"] = "Sangromante"
    hero["prepared_cards"] = [card_id]
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 4
    excess: list[int] = []
    real = cd.resolve_damage_and_wounds

    def spy(target, **kw):
        res = real(target, **kw)
        if target is hero:
            excess.append(int(res.get("excedente", 0) or 0))
        return res

    monkeypatch.setattr(orch, "resolve_damage_and_wounds", spy)
    monkeypatch.setattr(ct.cd, "resolve_damage_and_wounds", spy)
    decl = ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="card", card_id=card_id, target_id="boss")
    )
    before = hero["vitalidade"]
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={"player": decl},
        initiator="enemy",
        state={"player": hero},
        rng=random.Random(seed),
    )
    harm = next(m for m in out["class_mechanics"] if m["kind"] == "self_harm")
    paid = -harm["vitality_delta"]
    lines = preview.mech_log(out["attacks"], [hero, boss], out["ticks"], out=out)
    line_cost = [
        int(m.group(1)) for ln in lines if (m := re.search(r"custo · (\d+) Vitalidade$", ln))
    ]
    assert line_cost == [harm["amount"]] and paid == harm["amount"]
    hits = sum(
        int(m.group(1)) for ln in lines if "→ Você" in ln and (m := re.search(r"(\d+) dano$", ln))
    )
    drop = before - hero["vitalidade"]
    assert drop == paid + hits - sum(excess), (seed, drop, paid, hits, excess)


def test_taunt_resist_line_and_applied_line():
    resisted = held = 0
    for seed in range(30):
        hero = _actor("player", corpo=5, is_player=True)
        boss = _actor("boss", corpo=3, categoria="padrao")
        boss["active_conditions"] = [
            {
                "name": "Provocado",
                "dot": 0,
                "duration": 3,
                "control": "taunt",
                "source_actor_id": "player",
            }
        ]
        out = orch.run_round(
            _scene("player", "boss"),
            {"player": hero, "boss": boss},
            SIDES,
            declarations={},
            initiator="enemy",
            rng=random.Random(seed),
        )
        reg = round_log.round_registry(out, {"player": hero, "boss": boss})
        if any(m["kind"] == "special:taunt_resisted" for m in out["class_mechanics"]):
            resisted += 1
            assert "Boss resiste à Provocação." in reg
        else:
            held += 1
    assert resisted and held  # a Provocação é probabilística (50 %): os dois desfechos aparecem


def test_taunt_applied_line():
    out = {
        "attacks": [],
        "condicoes_novas": [
            {
                "victim_id": "boss",
                "condition": "Provocado",
                "source_id": "player",
                "control": "taunt",
            }
        ],
    }
    reg = round_log.round_registry(
        out, {"player": {"name": "H", "is_player": True}, "boss": {"name": "Criatura"}}
    )
    assert reg == ["Criatura está provocado: a próxima intenção dele mira você (com chance)."]


def test_condition_from_reaction_has_unknown_source():
    actor = {"id": "boss", "name": "B", "active_conditions": []}
    before = {"boss": []}
    actor["active_conditions"].append({"name": "Sangramento", "dot": 1, "duration": 2})
    out = {"reactions": [{"x": 1}]}
    orch._note_turn_records(before, {"boss": actor}, "boss", out)
    assert out["condicoes_novas"][0]["source_id"] is None
    # sem reação na janela, a fonte é o autor do turno
    out2: dict = {}
    other = {"id": "t", "name": "T", "active_conditions": []}
    b2 = {"t": []}
    other["active_conditions"].append({"name": "Sangramento", "dot": 1, "duration": 2})
    orch._note_turn_records(b2, {"t": other}, "player", out2)
    assert out2["condicoes_novas"][0]["source_id"] == "player"


def test_custo_board_entry_uses_ptbr_wound():
    out = {
        "attacks": [],
        "class_mechanics": [
            {
                "kind": "self_harm",
                "actor_id": "player",
                "card_id": "san_corte_troca",
                "amount": 3,
                "ferimento": {"categoria": "critico", "regiao": "torso"},
            }
        ],
    }
    board = preview.round_board(out, [{"id": "player", "name": "H", "is_player": True}], set())
    assert board[0]["efeito"] == "−3 Vitalidade, ferimento crítico no torso"


def test_record_flags_never_land_on_actors():
    """P3-4: nada de marca de registro no ator (vai para o save) e a linha 'sem Vitalidade' sai 1×."""
    import json

    boss = _actor("boss", corpo=3, categoria="elite", vitalidade=0)
    hero = _actor("player", corpo=5, is_player=True)
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={},
        initiator="heroes",
        rng=random.Random(1),
    )
    blob = json.dumps([hero, boss], default=str)
    assert "_sem_vit_avisado" not in blob and "_taunt_resisted" not in blob
    assert len([x for x in out.get("sem_vitalidade", []) if x["actor_id"] == "boss"]) <= 1


def _taunted_boss():
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["active_conditions"] = [
        {
            "name": "Provocado",
            "dot": 0,
            "duration": 9,
            "control": "taunt",
            "source_actor_id": "player",
        }
    ]
    return boss


def test_taunt_resist_survives_the_round_with_intent_on_and_does_not_leak(monkeypatch):
    """P3-7: com presságio `on` a rolagem do congelamento mora na cena e a linha sai na rodada
    seguinte; cena nova não herda nada; o ator fica limpo."""
    import json

    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    found = None
    for seed in range(40):
        hero = _actor("player", corpo=5, is_player=True)
        boss = _taunted_boss()
        scene = _scene("player", "boss")
        actors = {"player": hero, "boss": boss}
        for _ in range(3):
            out = orch.run_round(
                scene, actors, SIDES, declarations={}, initiator="heroes", rng=random.Random(seed)
            )
            hero["vitalidade"] = hero["max_vitalidade"]
            if any(m["kind"] == "special:taunt_resisted" for m in out["class_mechanics"]):
                found = (scene, out, actors)
                break
        if found:
            break
    assert found, "nenhuma seed produziu 'resiste à Provocação' com o presságio on"
    scene, out, actors = found
    reg = round_log.round_registry(out, {"player": actors["player"], "boss": actors["boss"]})
    assert "Boss resiste à Provocação." in reg
    assert "boss" not in scene.get("taunt_resistidos", [])  # consumido ao agir
    assert "_taunt_resisted" not in json.dumps(actors, default=str)
    assert not _scene("player", "boss").get("taunt_resistidos")  # cena nova: zerada


def test_public_panel_exposes_armor_reducoes_max():
    from services import bestiary_knowledge as bk

    panel = bk.public_panel({"armor": {"protecao": 2, "integridade_atual": 3, "reducoes_max": 2}})
    assert panel["reducoes_max"] == 2 and "resist_tipos" not in panel
