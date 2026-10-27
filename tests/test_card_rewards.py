"""SPEC-333 R1-R3 - espólio de Cartas: sorteio determinístico, pesos, recusa paga, tier, flag."""

from __future__ import annotations

import pytest

from services import card_rewards as cr
from services import card_telemetry, cards

TIERS = ("comum", "incomum", "rara")


def _player(level=6, class_name="Sangromante", **extra):
    base = [
        c["id"]
        for c in cards.cards_for_class(class_name)
        if not c.get("subclasse") and c.get("tipo") == "ativa" and c.get("level_req", 1) == 1
    ][:3]
    p = {
        "class_name": class_name,
        "level": level,
        "known_cards": list(base),
        "prepared_cards": list(base),
        "gold": 10,
        "entropy": 5,
        "max_entropy": 10,
    }
    p.update(extra)
    return p


def _state(**kw):
    return {"player": _player(**kw), "world": {"current_location_id": "nova_arcadia"}}


@pytest.fixture()
def rewards_on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _fake_catalog(monkeypatch, rows):
    """Injeta Cartas sintéticas no catálogo (restaurado pelo monkeypatch)."""
    catalog = dict(cards.all_cards())
    for cid, patamar, extra in rows:
        catalog[cid] = {
            "id": cid,
            "name": cid,
            "tipo": "ativa",
            "patamar": patamar,
            "level_req": 1,
            "frequencia": "livre",
            "efeito": {"kind": "dano", "categoria_arma": "leve", "dano_base": 3},
            **extra,
        }
    monkeypatch.setattr(cards, "_CARDS", catalog)


# ------------------------------------------------------------------ flag
def test_flag_padrao_off_e_valor_invalido_vira_off(monkeypatch):
    monkeypatch.delenv("RPG_CARD_REWARDS", raising=False)
    assert cr.mode() == "off"
    monkeypatch.setenv("RPG_CARD_REWARDS", "talvez")
    assert cr.mode() == "off"
    monkeypatch.setenv("RPG_CARD_REWARDS", "ON")
    assert cr.mode() == "on"


def test_off_nao_grava_nada_no_player(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    st = _state()
    before = dict(st["player"])
    assert (
        cr.grant_after_conflict(
            st, st["player"], conflict_id="c", seed=1, defeated=[], objective_result=None, turn=1
        )
        is None
    )
    assert st["player"] == before
    assert cr.public_pending(st["player"]) is None


# ------------------------------------------------------------------ R1 sorteio
def test_tres_cartas_distintas_e_deterministicas(rewards_on):
    st = _state()
    a = cr.roll_rewards(st, None, 1234)
    assert len(a) == 3 == len(set(a))
    assert a == cr.roll_rewards(st, None, 1234)  # mesma seed = mesmo espólio
    assert any(cr.roll_rewards(st, None, s) != a for s in range(1, 30))


def test_ofertas_so_de_cartas_ainda_nao_conhecidas_e_jogaveis_no_baralho(rewards_on):
    st = _state()
    known = set(st["player"]["known_cards"])
    for seed in range(60):
        for cid in cr.roll_rewards(st, None, seed):
            card = cards.get_card(cid)
            assert cid not in known
            assert card["tipo"] in cards._DECK_TIPOS and not card.get("basica")
            assert card.get("origem") != "cartas-333" and card["tipo"] not in cards.STATUS_TIPOS


def test_respeita_level_req_do_nivel_atual(rewards_on):
    low = _state(level=1)
    for seed in range(60):
        for cid in cr.roll_rewards(low, None, seed):
            assert int(cards.get_card(cid).get("level_req", 1) or 1) <= 1


def test_pesos_de_fonte_e_raridade(monkeypatch, rewards_on):
    rows = []
    for src in ("p", "n", "s"):
        for rar, pat in (("comum", "inicial"), ("incomum", "avancado"), ("rara", "epico_i")):
            for i in range(12):
                rows.append((f"fk_{src}_{rar}_{i}", pat, {}))
    _fake_catalog(monkeypatch, rows)
    pools = {
        "postura": sorted(c for c, *_ in rows if c.startswith("fk_p_")),
        "neutra": sorted(c for c, *_ in rows if c.startswith("fk_n_")),
        "saque": sorted(c for c, *_ in rows if c.startswith("fk_s_")),
    }
    monkeypatch.setattr(cr, "_pools", lambda *a, **k: pools)
    st = _state()
    n = 1500
    src_count = {"p": 0, "n": 0, "s": 0}
    rar_count = {r: 0 for r in TIERS}
    for seed in range(n):
        for cid in cr.roll_rewards(st, None, seed):
            _, src, rar, _i = cid.split("_")
            src_count[src] += 1
            rar_count[rar] += 1
    total = 3 * n
    assert abs(src_count["p"] / total - 0.60) < 0.04
    assert abs(src_count["n"] / total - 0.25) < 0.04
    assert abs(src_count["s"] / total - 0.15) < 0.04
    assert abs(rar_count["comum"] / total - 0.70) < 0.04
    assert abs(rar_count["incomum"] / total - 0.25) < 0.04
    assert abs(rar_count["rara"] / total - 0.05) < 0.03


def test_pool_de_uma_fonte_vazia_cai_nas_outras(monkeypatch, rewards_on):
    _fake_catalog(monkeypatch, [(f"fk_{i}", "inicial", {}) for i in range(5)])
    monkeypatch.setattr(
        cr,
        "_pools",
        lambda *a, **k: {"postura": [], "neutra": [], "saque": [f"fk_{i}" for i in range(5)]},
    )
    assert len(cr.roll_rewards(_state(), None, 7)) == 3


def test_abissal_so_com_chefe(monkeypatch, rewards_on):
    _fake_catalog(
        monkeypatch,
        [
            ("ab_cinza", "apice", {"raridade": "abissal", "apex": True}),
            ("ab_comum", "inicial", {}),
            ("ab_comum2", "inicial", {}),
            ("ab_comum3", "inicial", {}),
        ],
    )
    monkeypatch.setattr(
        cards, "enemy_card_ids", lambda e: ["ab_cinza", "ab_comum", "ab_comum2", "ab_comum3"]
    )
    import progression

    monkeypatch.setattr(progression, "eligible_cards", lambda p: [])
    st = _state()
    chefe = {"id": "e1", "categoria": "chefe"}
    lacaio = {"id": "e2", "categoria": "lacaio"}
    seen_boss = set()
    for seed in range(300):
        assert "ab_cinza" not in cr.roll_rewards(st, None, seed, defeated=[lacaio])
        seen_boss.update(cr.roll_rewards(st, None, seed, defeated=[chefe]))
    assert "ab_cinza" in seen_boss


def test_saque_de_tecnica_vem_das_cartas_do_derrotado(monkeypatch, rewards_on):
    _fake_catalog(monkeypatch, [("saq_a", "inicial", {}), ("saq_b", "inicial", {})])
    monkeypatch.setattr(cards, "enemy_card_ids", lambda e: ["saq_a", "saq_b"])
    import progression

    monkeypatch.setattr(progression, "eligible_cards", lambda p: [])
    out = set()
    for seed in range(40):
        out.update(cr.roll_rewards(_state(), None, seed, defeated=[{"id": "x"}]))
    assert out == {"saq_a", "saq_b"}


# ------------------------------------------------------------------ gancho do fim do conflito
def test_grant_on_grava_pendente_e_shadow_so_mede(monkeypatch):
    seen = []
    monkeypatch.setattr(card_telemetry, "log_event", lambda a, e, **kw: seen.append((e, kw)))
    st = _state()
    monkeypatch.setenv("RPG_CARD_REWARDS", "shadow")
    assert (
        cr.grant_after_conflict(
            st, st["player"], conflict_id="c1", seed=3, defeated=[], objective_result=None, turn=2
        )
        is None
    )
    assert "espolio_pendente" not in st["player"]
    assert seen and all(kw["source"] == "auto" for _, kw in seen)

    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    pend = cr.grant_after_conflict(
        st, st["player"], conflict_id="c1", seed=3, defeated=[], objective_result="cumprido", turn=2
    )
    assert pend and pend["origem"] == "objetivo" and len(pend["ofertas"]) == 3
    assert st["player"]["espolio_pendente"] is pend


def test_objetivo_falho_nao_rende_espolio(rewards_on):
    st = _state()
    assert (
        cr.grant_after_conflict(
            st,
            st["player"],
            conflict_id="c",
            seed=1,
            defeated=[],
            objective_result="falhou",
            turn=1,
        )
        is None
    )
    assert "espolio_pendente" not in st["player"]


def test_pendente_expira_no_proximo_conflito(rewards_on):
    st = _state()
    cr.grant_after_conflict(
        st, st["player"], conflict_id="c", seed=1, defeated=[], objective_result=None, turn=1
    )
    cr.expire_pending(st["player"])
    assert "espolio_pendente" not in st["player"]


# ------------------------------------------------------------------ R1/R2 aceitar e recusar
def _pending(rewards_on_fixture_state=None):
    st = _state()
    cr.grant_after_conflict(
        st, st["player"], conflict_id="c", seed=9, defeated=[], objective_result=None, turn=1
    )
    return st


def test_aceitar_entra_no_acervo_e_no_baralho(rewards_on):
    st = _pending()
    p = st["player"]
    p["deck"] = ["bas_san_golpe"] * 12
    pick = p["espolio_pendente"]["ofertas"][0]
    res = cr.accept(st, pick)
    assert res["ok"] and res["destino"] == "baralho"
    assert pick in p["known_cards"] and p["deck"][-1] == pick and pick in p["prepared_cards"]
    assert "espolio_pendente" not in p and p["gold"] == 10


def test_sem_baralho_vira_preparada_se_houver_vaga(rewards_on):
    st = _pending()
    p = st["player"]
    pick = p["espolio_pendente"]["ofertas"][1]
    res = cr.accept(st, pick)
    assert res["ok"] and res["destino"] in ("preparadas", "acervo")
    assert pick in p["known_cards"]


def test_baralho_cheio_deixa_so_no_acervo(rewards_on):
    st = _pending()
    p = st["player"]
    p["deck"] = ["bas_san_golpe"] * cards.DECK_MAX
    pick = p["espolio_pendente"]["ofertas"][0]
    res = cr.accept(st, pick)
    assert res["destino"] == "acervo" and len(p["deck"]) == cards.DECK_MAX
    assert pick in p["known_cards"]


def test_recusar_paga_15_de_ouro(rewards_on):
    st = _pending()
    res = cr.accept(st, None)
    assert res["ok"] and res["gold"] == 15 and res["destino"] == "ouro"
    assert st["player"]["gold"] == 25 and "espolio_pendente" not in st["player"]


def test_carta_fora_das_ofertas_ou_sem_pendente_e_rejeitada(rewards_on):
    st = _pending()
    assert not cr.accept(st, "san_inexistente")["ok"]
    assert "espolio_pendente" in st["player"]  # rejeitar nao consome o espólio
    cr.accept(st, None)
    assert not cr.accept(st, None)["ok"]


def test_telemetria_com_source_espolio(monkeypatch, rewards_on):
    seen = []
    monkeypatch.setattr(card_telemetry, "log_event", lambda a, e, **kw: seen.append((e, kw)))
    st = _pending()
    pick = st["player"]["espolio_pendente"]["ofertas"][2]
    cr.accept(st, pick)
    offered = [kw for e, kw in seen if e == "card_offered"]
    assert len(offered) == 3 and all(kw["source"] == "espolio" for kw in offered)
    assert [kw["card_id"] for kw in offered if kw["picked"]] == [pick]
    assert [kw["card_id"] for e, kw in seen if e == "card_picked"] == [pick]
    seen.clear()
    st2 = _pending()
    cr.accept(st2, None)  # recusa: ofertas sem nenhuma escolhida, sem card_picked
    assert not any(e == "card_picked" for e, _ in seen)
    assert all(not kw["picked"] for e, kw in seen if e == "card_offered")


def test_public_pending_traz_texto_gerado_e_some_com_flag_off(monkeypatch, rewards_on):
    st = _pending()
    view = cr.public_pending(st["player"])
    assert view["recusa_ouro"] == 15 and len(view["ofertas"]) == 3
    assert all(o["name"] and o["raridade"] in (*TIERS, "abissal") for o in view["ofertas"])
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    assert cr.public_pending(st["player"]) is None


# ------------------------------------------------------------------ nó de combate (integração)
def _victory(monkeypatch, mode):
    from tests.test_combat_xp_outside_prose import _kill_state

    monkeypatch.setenv("RPG_CARD_REWARDS", mode)
    cbt, state, _cap = _kill_state(monkeypatch)
    from services import conflict_orchestrator as orch

    fake_round = orch.run_round
    monkeypatch.setattr(
        orch, "run_round", lambda *a, **k: {**fake_round(*a, **k), "ended": True, "reason": "ok"}
    )
    state["player"].update({"class_name": "Sangromante", "level": 6, "known_cards": []})
    state["player"]["prepared_cards"] = []
    return cbt, state


def test_no_de_combate_off_identico_e_on_oferece(monkeypatch):
    cbt, state = _victory(monkeypatch, "off")
    off = cbt.combat_node(state)
    assert "espolio_pendente" not in off["player"]
    cbt2, state2 = _victory(monkeypatch, "on")
    on = cbt2.combat_node(state2)
    pend = on["player"]["espolio_pendente"]
    assert len(pend["ofertas"]) == 3 and pend["origem"] == "vitoria"
    # espólio não mexe em loot/XP/ouro
    for key in ("xp", "gold"):
        assert on["player"].get(key) == off["player"].get(key)
    assert on["next"] == off["next"] == "loot"


# ------------------------------------------------------------------ harness: tamanho médio do baralho
def test_politica_de_jogo_mantem_o_baralho_medio_entre_15_e_22(monkeypatch):
    """Plano 4: 50 turnos ~ 25 conflitos. Aceita sempre o espólio; esquece 1 carta a cada 2
    conflitos (descanso longo). O tamanho médio do baralho não pode inchar nem encolher."""
    from services import card_piles as cp

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    st = _state(level=10)
    cp.migrate_deck(st["player"])
    st["world"]["danger_level"] = 1
    sizes = []
    basics = {c for ids in cards.basicas_for_class("Sangromante").values() for c in ids}
    for i in range(25):
        cr.grant_after_conflict(
            st,
            st["player"],
            conflict_id=f"c{i}",
            seed=i,
            defeated=[],
            objective_result=None,
            turn=i,
        )
        pend = st["player"].get("espolio_pendente")
        if pend:
            assert cr.accept(st, pend["ofertas"][0])["ok"]
        if i % 2:
            cr.on_long_rest(st["player"])
            victim = (
                next((c for c in st["player"]["deck"] if c in basics and c.endswith("golpe")), None)
                or st["player"]["deck"][0]
            )
            cr.forget(st, victim, "descanso")
        sizes.append(len(st["player"]["deck"]))
        assert cards.DECK_MIN <= sizes[-1] <= cards.DECK_MAX
    assert 15 <= sum(sizes) / len(sizes) <= 22, sizes
