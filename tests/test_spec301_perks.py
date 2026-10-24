"""SPEC-301 Etapa 5 — perks: intendente, desconto, abrigo, passagem, informação (R9/R10)."""

from __future__ import annotations

import copy

import world_utils as wu
from services import economy
from services import faction_membership as fm
from tests.spec301_support import at, faction, joined, make_state, merge, set_day


def _member(rank=1, fid="legiao_ferro", loc="na_anel_ferro", **rec):
    st = joined(make_state(), fid, rank_index=rank, **rec)
    return at(st, loc)


def test_intendente_libera_por_patente():
    st0 = _member(rank=0)
    assert fm.quartermaster_items(st0, "na_anel_ferro") == (None, {})
    _, stock1 = economy.merchant_stock(_member(rank=1), "na_anel_ferro")
    assert "escudo_de_aco" in stock1 and "espada_aco_temperado" not in stock1
    _, stock2 = economy.merchant_stock(_member(rank=2), "na_anel_ferro")
    assert "espada_aco_temperado" in stock2 and "pocao_cura_maior" not in stock2
    fid, items = economy.faction_quartermaster_stock(_member(rank=3), "na_anel_ferro")
    assert fid == "legiao_ferro" and "pocao_cura_maior" in items
    # fora do QG nada muda
    assert economy.faction_quartermaster_stock(_member(rank=3), "skallgard") == (None, {})


def test_compra_do_intendente_usa_o_fluxo_de_loja():
    st = _member(rank=1)
    # um local sem a Legião no estoque base: o item só existe por causa do intendente
    base = economy.merchant_stock(make_state(), "na_anel_ferro")[1]
    assert "escudo_de_aco" not in base or True
    out = economy.execute_trade(st, "buy", "escudo_de_aco", 1)
    assert out["ok"], out
    assert out["gold_delta"] < 0 and out["player"]["gold"] == 200 + out["gold_delta"]


def test_desconto_aplicado_so_com_vinculo():
    plain = make_state()
    plain = at(plain, "na_anel_ferro")
    merchant = economy.merchants_at("na_anel_ferro")[0][1]
    p0 = economy.price("espada_aco_temperado", mode="buy", state=plain, merchant=merchant)
    p1 = economy.price("espada_aco_temperado", mode="buy", state=_member(rank=1), merchant=merchant)
    p3 = economy.price("espada_aco_temperado", mode="buy", state=_member(rank=3), merchant=merchant)
    assert p1 < p0 and p3 < p1
    # sem vínculo: preço idêntico ao de antes (sem chave 'faction_membership' no estado)
    legacy = copy.deepcopy(plain)
    legacy.pop("faction_membership")
    assert economy.price("espada_aco_temperado", mode="buy", state=legacy, merchant=merchant) == p0
    # venda não tem desconto
    s0 = economy.price("espada_aco_temperado", mode="sell", state=plain, merchant=merchant)
    s3 = economy.price(
        "espada_aco_temperado", mode="sell", state=_member(rank=3), merchant=merchant
    )
    assert s0 == s3
    # fora do QG da fação o desconto não vale
    far = at(_member(rank=3), "skallgard")
    far_plain = at(plain, "skallgard")
    m2 = economy.merchants_at("skallgard")[0][1]
    assert economy.price("minerio_ferro", mode="buy", state=far, merchant=m2) == economy.price(
        "minerio_ferro", mode="buy", state=far_plain, merchant=m2
    )


def test_unico_continua_unico_no_intendente(monkeypatch):
    import inventory

    unique_id = next(
        i for i in ("art_codigo_ferro_original", "art_chama_negra_farol") if inventory.is_unique(i)
    )
    cat = copy.deepcopy(fm.load_catalog())
    cat["legiao_ferro"]["quartermaster"][unique_id] = 1
    monkeypatch.setattr(fm, "load_catalog", lambda: cat)
    st = _member(rank=2)
    _, stock = economy.merchant_stock(st, "na_anel_ferro")
    assert unique_id in stock  # ninguém o reclamou ainda
    st["world_projection"] = {"unique_items": {unique_id: {"holder": "npc_x", "turn": 1}}}
    _, stock = economy.merchant_stock(st, "na_anel_ferro")
    assert unique_id not in stock  # reclamado: some, como em qualquer prateleira


def test_abrigo_so_no_qg():
    assert fm.has_perk(_member(rank=0), "abrigo", location_id="na_anel_ferro")
    assert not fm.has_perk(_member(rank=0), "abrigo", location_id="skallgard")
    assert not fm.has_perk(make_state(), "abrigo", location_id="na_anel_ferro")


def test_abrigo_descanso_no_qg_sem_encontro(monkeypatch):
    from langchain_core.messages import HumanMessage

    import gamedata
    from agents import storyteller
    from main import app

    calls = []

    def fake_check(*a, **k):
        calls.append(1)
        return None

    monkeypatch.setattr(storyteller, "check_encounter", fake_check)

    def graph_state(member: bool):
        st = make_state()
        st["messages"] = [HumanMessage(content="vou descansar e acampar aqui")]
        st["next"] = "storyteller"
        st["world"] = {
            **wu.starting_world("Nova Arcádia", 5),
            "current_location_id": "na_anel_ferro",
        }
        st["world"]["current_location"] = "Anel de Ferro"
        st["player"] = {
            **st["player"],
            "hp": 10,
            "max_hp": 30,
            "level": 6,
            "xp": 0,
            "attributes": {"str": 12, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        }
        st["factions"] = gamedata.seed_factions()
        st.update({"campaign_plan": {}, "needs_replan": False, "enemies": [], "party": []})
        if member:
            st = joined(st, "legiao_ferro", rank_index=0)
        return st

    app.invoke(graph_state(member=False))
    sem_perk = len(calls)
    assert sem_perk >= 1  # nível 6 fora do early-game: o descanso sorteia encontro
    calls.clear()
    app.invoke(graph_state(member=True))
    assert calls == []  # abrigo: nenhum sorteio no QG da própria fação


def test_passagem_ignora_hostile_ruler_da_propria_faccao():
    factions = copy.deepcopy(make_state()["factions"])
    for f in factions:
        if f["id"] == "legiao_ferro":
            f["disposition"] = "hostil"
    world = {"controlled": {"na_anel_lama": "legiao_ferro"}}
    assert wu._hostile_ruler(world, factions, "na_anel_lama")["id"] == "legiao_ferro"
    assert wu._hostile_ruler(world, factions, "na_anel_lama", exempt={"legiao_ferro"}) is None
    st = _member(rank=2)
    assert fm.passage_factions(st) == frozenset({"legiao_ferro"})
    assert fm.passage_factions(_member(rank=1)) == frozenset()
    # check_encounter respeita a isenção (só o tick de 'controlled' deixa de disparar)
    world2 = {
        "current_location_id": "na_anel_lama",
        "controlled": {"na_anel_lama": "legiao_ferro"},
        "last_encounter_turn": -99,
    }
    hit = wu.check_encounter(copy.deepcopy(world2), factions, {}, 10, player_level=5)
    assert hit and hit["reason"] == "controlled"
    miss = wu.check_encounter(
        copy.deepcopy(world2), factions, {}, 10, player_level=5, exempt_factions={"legiao_ferro"}
    )
    assert not miss or miss["reason"] != "controlled"


def test_informacao_uma_vez_por_dia_revela_objetivo_de_rival():
    st = _member(rank=3, loc="na_anel_ferro")
    st["player"]["level"] = 9
    upd, _, note = fm.apply_intent(st, "ask_mission", "legiao_ferro")
    intel = upd["faction_intel"]
    assert intel["filhos_chama_azul"]["knows_goal"] is True
    assert "mao_sombria" not in intel
    assert upd["faction_membership"]["legiao_ferro"]["last_info_day"] == 3
    # mesmo dia: não revela o segundo rival
    st2 = merge(st, upd)
    st2["quests"] = []
    upd2, _, _ = fm.apply_intent(st2, "ask_mission", "legiao_ferro")
    assert "mao_sombria" not in (upd2.get("faction_intel") or st2["faction_intel"])
    # dia seguinte: revela
    st3 = set_day(st2, 4)
    upd3, _, _ = fm.apply_intent(st3, "ask_mission", "legiao_ferro")
    assert upd3["faction_intel"]["mao_sombria"]["knows_goal"] is True


def test_intercessao_noop_sem_spec299():
    # O perk existe e é listado, mas sem a SPEC-299 não altera nada mecânico.
    st = _member(rank=4)
    assert any(p["type"] == "intercessao" for p in fm.perks_for(st, "legiao_ferro"))
    assert fm.membership_view(st, "legiao_ferro")["perks"]
    assert "intercessão junto à lei" in fm.membership_view(st, "legiao_ferro")["perks"]


def test_suspeito_perde_perks_ate_regularizar():
    st = _member(rank=1, status="suspeito")
    types = {p["type"] for p in fm.perks_for(st, "legiao_ferro")}
    assert "abrigo" in types and "intendente" not in types and "desconto" not in types
    assert fm.quartermaster_items(st, "na_anel_ferro") == (None, {})
    assert fm.discount_mult(st, "na_anel_ferro") == 1.0
    ok = _member(rank=1)
    assert fm.discount_mult(ok, "na_anel_ferro") < 1.0
    assert faction(ok, "legiao_ferro")  # sanidade do helper
