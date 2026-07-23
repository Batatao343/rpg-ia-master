"""Suíte da spec conflito-03: Zonas, Cena Congelada e Objetos Interativos.

100% determinístico, offline. Exercita o motor `services/conflict_scene.py`."""

from services import conflict_scene as cs


def _scene():
    s = cs.new_scene([
        {"id": "z0", "name": "Salão", "connections": ["z1"]},
        {"id": "z1", "name": "Corredor", "connections": ["z0"]},
    ])
    cs.place(s, "player", zone_id="z0", distance_state="separado")
    cs.place(s, "verme", zone_id="z0", distance_state="separado")
    return s


# --------------------------------------------------------------------------
# Etapa 1 — zonas, distância, engajamento
# --------------------------------------------------------------------------
def test_move_distance_um_estagio():
    s = _scene()
    r = cs.move_distance(s, "player", "aproximar", via="pre")
    assert r["ok"] and r["distance_state"] == "distante"


def test_move_distance_dois_estagios_pre_e_pos():
    s = _scene()
    cs.move_distance(s, "player", "aproximar", via="pre")   # separado -> distante
    cs.move_distance(s, "player", "aproximar", via="pos")   # distante -> proximo
    assert s["positions"]["player"]["distance_state"] == "proximo"


def test_move_distance_clampa_nos_extremos():
    s = _scene()
    for _ in range(5):
        cs.move_distance(s, "verme", "aproximar")
    assert s["positions"]["verme"]["distance_state"] == "proximo"
    for _ in range(5):
        cs.move_distance(s, "verme", "afastar")
    assert s["positions"]["verme"]["distance_state"] == "separado"


def test_engajamento_independente_de_distancia():
    s = _scene()
    # ambos Próximos, mas NÃO engajados
    s["positions"]["player"]["distance_state"] = "proximo"
    s["positions"]["verme"]["distance_state"] = "proximo"
    assert not cs.is_engaged(s, "player", "verme")
    cs.engage(s, "player", "verme")
    assert cs.is_engaged(s, "player", "verme") and cs.is_engaged(s, "verme", "player")
    cs.disengage(s, "player", "verme")
    assert not cs.is_engaged(s, "player", "verme")
    # desengajar não muda a distância
    assert s["positions"]["player"]["distance_state"] == "proximo"


# --------------------------------------------------------------------------
# Etapa 2 — Postura e Ocultação
# --------------------------------------------------------------------------
def test_protegido_momentaneo_expira_apos_um_ataque():
    s = _scene()
    cs.set_postura(s, "player", "protegido", mode="momentaneo")
    assert s["positions"]["player"]["postura"]["state"] == "protegido"
    cs.consume_postura_on_attack(s, "player")
    assert s["positions"]["player"]["postura"]["state"] == "neutro"


def test_protegido_sustentado_persiste_enquanto_causa_existir():
    s = _scene()
    cs.set_postura(s, "player", "protegido", mode="sustentado", cause="pilastra")
    cs.consume_postura_on_attack(s, "player")   # sustentada NÃO expira num ataque
    assert s["positions"]["player"]["postura"]["state"] == "protegido"
    cs.clear_sustained_postura(s, "player", "pilastra")  # causa some -> some
    assert s["positions"]["player"]["postura"]["state"] == "neutro"


# --------------------------------------------------------------------------
# Etapa 3 — Objetos interativos + catálogo fechado
# --------------------------------------------------------------------------
def _lustre():
    return {
        "id": "lustre", "name": "Lustre de Ferro", "distance_state": "distante",
        "zone_id": "z0", "uses_remaining": 1,
        "interactions": [{"label": "Derrubar", "cost": "acao",
                          "effect": {"kind": "damage", "params": {"formula": "2d8"}}}],
    }


def test_interacao_objeto_gera_effectspec_valido():
    s = _scene()
    cs.add_object(s, _lustre())
    r = cs.apply_object_interaction(s, "lustre", "Derrubar", "player")
    assert r["ok"] and r["effect"]["kind"] == "damage"
    # 1 uso -> destruído
    assert cs._find_object(s, "lustre")["destroyed"]


def test_effect_kind_fora_do_catalogo_e_rejeitado():
    assert cs.validate_effect_kind({"kind": "damage"})
    assert not cs.validate_effect_kind({"kind": "invocar_deus"})
    s = _scene()
    obj = _lustre()
    obj["interactions"][0]["effect"] = {"kind": "invocar_deus"}
    cs.add_object(s, obj)
    r = cs.apply_object_interaction(s, "lustre", "Derrubar", "player")
    assert not r["ok"] and "catálogo" in r["error"]


def test_objeto_secreto_nao_aparece_ate_descoberto():
    s = _scene()
    obj = _lustre()
    obj["id"] = "alcapao"
    obj["name"] = "Alçapão"
    obj["secret"] = True
    cs.add_object(s, obj)
    vis = [o["id"] for o in cs.visible_objects(s)]
    assert "alcapao" not in vis
    # interação bloqueada até descobrir
    r = cs.apply_object_interaction(s, "alcapao", "Derrubar", "player")
    assert not r["ok"]
    cs.discover_object(s, "alcapao")
    assert "alcapao" in [o["id"] for o in cs.visible_objects(s)]


def test_objeto_visivel_esconde_o_effect():
    s = _scene()
    cs.add_object(s, _lustre())
    vis = cs.visible_objects(s)[0]
    it = vis["interactions"][0]
    assert set(it.keys()) == {"label", "cost"}   # nunca expõe 'effect'


# --------------------------------------------------------------------------
# Etapa 4 — Cena congelada
# --------------------------------------------------------------------------
def test_freeze_bloqueia_novo_objeto_apos_inicio():
    s = _scene()
    cs.freeze(s)
    r = cs.add_object(s, _lustre())
    assert not r["ok"] and "congelada" in r["error"].lower()
    # participante também não entra
    rp = cs.place(s, "intruso")
    assert not rp["ok"]


def test_reforco_so_entra_via_gatilho_preparado():
    s = _scene()
    cs.add_reinforcement_trigger(s, {"id": "onda2", "participants": {
        "verme2": {"zone_id": "z1", "distance_state": "separado",
                   "postura": {"state": "neutro", "mode": "sustentado", "cause": None},
                   "ocultacao": "visivel", "engaged_with": []}}})
    cs.freeze(s)
    # gatilho não-preparado falha
    assert not cs.fire_reinforcement(s, "inexistente")["ok"]
    # gatilho preparado entra mesmo congelado
    r = cs.fire_reinforcement(s, "onda2")
    assert r["ok"] and r["effect"]["kind"] == "spawn_reinforcement"
    assert "verme2" in s["positions"]


def test_gatilho_de_reforco_so_antes_de_congelar():
    s = _scene()
    cs.freeze(s)
    r = cs.add_reinforcement_trigger(s, {"id": "tarde"})
    assert not r["ok"]
