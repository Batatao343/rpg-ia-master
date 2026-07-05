"""
Fase 6.1 — Economia viva: rotas, escassez e eventos no comércio.
Spec: specs/fase-6.1-economia-viva.md. 100% offline.

Geografia real usada: brekmar ↔ nova_arcadia são conexão direta;
brekmar tem economy_tags ["porto"] e tag de mapa via economy_tags.
"""
import pytest

import inventory as inv
from services import economy as eco
from services import graph_resolver as gr
from services.event_processor import apply_event, process_pending_events
from services.world_validators import validate_proposal

BREKMAR = "brekmar"
NOVA = "nova_arcadia"


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


def _state(**over):
    base = {
        "world": {"turn_count": 5, "current_location": "Nova Arcádia",
                  "current_location_id": NOVA,
                  "world_clock": {"day": 1, "period": "Manhã"}},
        "world_projection": {}, "event_log": [], "pending_world_events": [],
        "chronicle": [], "quests": [], "factions": [],
        "player": {"name": "T", "gold": 500, "inventory": [], "hp": 30, "max_hp": 30},
    }
    base.update(over)
    return base


def _blocked(*pairs):
    return {"blocked_routes": [{"a": a, "b": b, "blocked_by_event": "e"}
                               for a, b in pairs]}


def _prop(a=BREKMAR, b=NOVA, etype="route_blocked"):
    return {"type": etype, "target_id": a,
            "payload": {"other_location_id": b}, "detail": "x"}


# ---------------------------------------------------------------------------
# Etapa 1 — evento no pipeline
# ---------------------------------------------------------------------------

def test_route_blocked_valida_conexao_direta():
    ok = validate_proposal(_prop(), _state())
    assert ok.ok, ok.reason
    # não conectados diretamente
    bad = validate_proposal(_prop(a="skallgard", b="pantano_melancolia"), _state())
    assert not bad.ok
    # local inexistente
    bad2 = validate_proposal(_prop(b="atlantida"), _state())
    assert not bad2.ok


def test_route_blocked_aplica_e_cleared_remove():
    ev = {"event_id": "e1", "turn": 5, "type": "route_blocked",
          "target_id": BREKMAR, "payload": {"other_location_id": NOVA}}
    proj = apply_event(ev, {})
    assert proj["blocked_routes"][0]["a"] == BREKMAR
    ev2 = {"event_id": "e2", "turn": 6, "type": "route_cleared",
           "target_id": NOVA, "payload": {"other_location_id": BREKMAR}}  # ordem invertida
    proj2 = apply_event(ev2, proj)
    assert proj2["blocked_routes"] == []


def test_par_ja_bloqueado_rejeitado_e_cleared_exige_bloqueio():
    s = _state(world_projection=_blocked((BREKMAR, NOVA)))
    assert not validate_proposal(_prop(), s).ok
    assert validate_proposal(_prop(etype="route_cleared"), s).ok
    s2 = _state()
    assert not validate_proposal(_prop(etype="route_cleared"), s2).ok


def test_mesmo_turno_pares_diferentes_nao_e_duplicata():
    s = _state(event_log=[{"type": "route_blocked", "target_id": BREKMAR,
                           "turn": 5, "payload": {"other_location_id": NOVA}}])
    other = _prop(b="bk_docas_velhas")
    res = validate_proposal(other, s)
    assert res.ok, res.reason


# ---------------------------------------------------------------------------
# Etapa 2 — alcançabilidade + supply
# ---------------------------------------------------------------------------

def test_is_reachable_bfs_e_bloqueio():
    assert eco.is_reachable(NOVA, BREKMAR, {})
    # mapa é conexo: bloquear UMA aresta não isola se há caminho alternativo
    proj = _blocked((BREKMAR, NOVA))
    # brekmar ainda alcançável? depende do grafo; o que TEM que valer:
    # bloquear TODAS as connections de brekmar isola brekmar.
    from gamedata import get_location
    conns = get_location(BREKMAR)["connections"]
    proj_all = _blocked(*[(BREKMAR, c) for c in conns])
    assert not eco.is_reachable(NOVA, BREKMAR, proj_all)
    assert eco.is_reachable(NOVA, NOVA, proj_all)  # si mesmo


def test_supply_factor_produtor_local():
    # minerio_ferro (mineracao) em skallgard (mineracao) -> 0.6
    assert eco.supply_factor("minerio_ferro", "skallgard", {}) == eco.ABUNDANT_MULT


def test_supply_factor_alcancavel_e_escasso():
    from gamedata import get_location
    # pocao_cura tem tag ervas; produtores: pantano/floresta
    assert eco.supply_factor("pocao_cura", NOVA, {}) == 1.0
    producers = eco.producing_locations("pocao_cura")
    # bloquear TODAS as connections de cada produtor isola os produtores
    pairs = []
    for p in producers:
        pairs += [(p, c) for c in get_location(p)["connections"]]
    proj = _blocked(*pairs)
    assert eco.supply_factor("pocao_cura", NOVA, proj) == eco.SCARCE_MULT


def test_item_sem_tags_neutro():
    proj = _blocked((BREKMAR, NOVA))
    assert eco.supply_factor("espada_gasta", NOVA, proj) == 1.0


# ---------------------------------------------------------------------------
# Etapa 3 — preço/estoque reagem
# ---------------------------------------------------------------------------

def _isolate(producers_item):
    from gamedata import get_location
    pairs = []
    for p in eco.producing_locations(producers_item):
        pairs += [(p, c) for c in get_location(p)["connections"]]
    return _blocked(*pairs)


def test_price_explode_com_rota_bloqueada():
    s_ok = _state(world={"current_location_id": "na_anel_dourado",
                         "world_clock": {"day": 1, "period": "Manhã"}})
    s_blocked = _state(world={"current_location_id": "na_anel_dourado",
                              "world_clock": {"day": 1, "period": "Manhã"}},
                       world_projection=_isolate("pocao_cura"))
    assert eco.price("pocao_cura", mode="buy", state=s_blocked) > \
        eco.price("pocao_cura", mode="buy", state=s_ok)


def test_estoque_some_item_escasso_e_volta():
    proj = _isolate("pocao_cura")
    s = _state(world={"current_location_id": "na_anel_dourado",
                      "world_clock": {"day": 1, "period": "Manhã"}},
               world_projection=proj)
    _, stock = eco.merchant_stock(s, "na_anel_dourado")
    assert "pocao_cura" not in stock
    assert "espada_gasta" in stock  # sem tags: segue à venda
    # restock não repõe enquanto bloqueado (view continua escondendo)
    s["world"]["world_clock"]["day"] = 30
    eco.restock(s["world"])
    _, stock2 = eco.merchant_stock(s, "na_anel_dourado")
    assert "pocao_cura" not in stock2
    # rota limpa -> normaliza
    s["world_projection"] = {}
    _, stock3 = eco.merchant_stock(s, "na_anel_dourado")
    assert "pocao_cura" in stock3


# ---------------------------------------------------------------------------
# Etapa 4 — regra do porto (rule_engine 2.7)
# ---------------------------------------------------------------------------

def test_porto_hostil_bloqueia_rotas():
    state = _state(factions=[{"id": "grupos_piratas_rivais", "disposition": "hostil"}],
                   pending_world_events=[{
                       "type": "location_control_changed", "target_id": BREKMAR,
                       "payload": {"new_controller_id": "grupos_piratas_rivais"},
                       "detail": "Piratas tomam o porto"}])
    out = process_pending_events(state)
    blocked = out["world_projection"].get("blocked_routes", [])
    assert blocked, "regra do porto não disparou"
    derived = [e for e in out["event_log"]
               if e["type"] == "route_blocked" and e["source"] == "rule_engine"]
    assert derived
    # critério da Fase 6: item de tag 'porto' fica escasso na cidade dependente?
    # (nenhum item porto na 1ª leva — validar via supply_factor sintético)
    from gamedata import get_location
    conns = get_location(BREKMAR)["connections"]
    assert all(any(frozenset((r["a"], r["b"])) == frozenset((BREKMAR, c))
                   for r in blocked) for c in conns)


def test_porto_controlador_neutro_nao_bloqueia():
    state = _state(factions=[{"id": "osshari_brekmar", "disposition": "neutro"}],
                   pending_world_events=[{
                       "type": "location_control_changed", "target_id": BREKMAR,
                       "payload": {"new_controller_id": "osshari_brekmar"},
                       "detail": "Osshari assumem o porto"}])
    out = process_pending_events(state)
    assert not out["world_projection"].get("blocked_routes")


# ---------------------------------------------------------------------------
# Etapa 5 — visibilidade
# ---------------------------------------------------------------------------

def test_context_builder_renderiza_rota():
    from services.context_builder import render_event
    ev = {"event_id": "e", "turn": 7, "type": "route_blocked",
          "target_id": BREKMAR, "payload": {"other_location_id": NOVA}}
    txt = render_event(ev)
    assert "BLOQUEADA" in txt


def test_world_block_expoe_blocked_routes():
    import api as api_mod
    block = api_mod._world_block({"current_location": "X"},
                                 _blocked((BREKMAR, NOVA)), [])
    assert block["blocked_routes"] == [{"a": BREKMAR, "b": NOVA}]
