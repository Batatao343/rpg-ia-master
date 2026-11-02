"""SPEC-361 Etapa 5 — integração no combate, no bestiário e no brief de arte (R18, R28-R30)."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

import agents.bestiary as bst
import agents.combat as combat
from services import creature_gen as cg
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state

ZHUR = {
    "current_location": "Deserto de Zhur",
    "current_location_id": "deserto_zhur",
    "turn_count": 40,
    "danger_level": 1,
    "visited": ["deserto_zhur"],
}


@pytest.fixture
def gen_on(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_GEN", "on")
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    token = cg.CONTADOR_ATUALIZADO.set(None)
    yield
    cg.CONTADOR_ATUALIZADO.reset(token)


def _overlay() -> dict:
    from infrastructure.runtime import get_runtime

    return get_runtime().runtime_catalog.list("bestiary_template", owner_id=None, game_id=None)


def test_flag_legacy_identico(monkeypatch):
    monkeypatch.delenv("RPG_CREATURE_GEN", raising=False)
    assert cg.mode() == "legacy"

    def boom(*a, **k):
        raise AssertionError("legacy não passa pelo gerador da SPEC-361")

    monkeypatch.setattr(cg, "gerar", boom)
    t = bst.generate_new_enemy("Verme das Cinzas Profundas", "teste")
    assert t["name"] and "geracao" not in t and "ficha" not in t


def test_grounded_aceita_geracao_pedido(gen_on, monkeypatch):
    def fake(name, context="", **kw):
        assert "state" in kw  # R30: o estado vai ao gerador
        return {
            "id": "mon_coro_de_quitina_rt_abcdef",
            "name": "Coro de Quitina",
            "categoria": "lacaio",
            "geracao": {"caminho": "nova", "nome": name},
        }

    monkeypatch.setattr(combat, "generate_new_enemy", fake)
    t = combat._grounded_template("Lacaio mente-colmeia", "ctx", 1, {"world": ZHUR})
    assert t["name"] == "Coro de Quitina"
    # sem a marca da geração, a trava de identidade continua valendo
    monkeypatch.setattr(
        combat,
        "generate_new_enemy",
        lambda name, context="", **kw: {"id": "x", "name": "Outra Coisa", "categoria": "lacaio"},
    )
    t2 = combat._grounded_template("Lacaio mente-colmeia", "ctx", 1, {"world": ZHUR})
    assert t2["name"] != "Outra Coisa"


def test_spawn_colmeia_zhur_variante(gen_on, monkeypatch):
    hint = "lacaio mente-colmeia"
    _install_llm(monkeypatch, scan=_scan(("Lacaio mente-colmeia", 1)))
    # o piso do grupo vale no spawn; o orçamento do encontro (SPEC-203/287) segue com a última
    # palavra, então o teste usa um perigo em que três lacaios cabem.
    state = _start_state(hint=hint, world={**ZHUR, "danger_level": 3})
    enemies, _ = combat._spawn_v4_enemies(state["messages"], hint, state, {})
    variantes = [e for e in enemies if e.get("variant_of") == "mon_saltador_de_palafita"]
    assert len(variantes) >= 3
    assert all(e["name"].startswith("Saltador de Palafita da Mente Única") for e in variantes)
    assert variantes[0]["tactical_profile"]["padrao"] == ["reforco_proprio", "ataque_multiplo"]
    # a variante fica no overlay do dono, nunca no pool
    assert "mon_saltador_de_palafita__v_mente_unica" in _overlay()


def test_spawn_nova_salva_overlay(gen_on):
    t = bst.generate_new_enemy(
        "Bebedor de Odres",
        "algo que vive dentro dos odres de água estragada",
        state={"game_id": "g-int", "world": dict(ZHUR)},
    )
    assert t["geracao"]["caminho"] == "nova" and t["geracao"]["estado"] == "local"
    saved = _overlay()[t["id"]]
    assert saved["ficha"]["revisao"] == "pendente" and saved["appearance"]
    assert cg.CONTADOR_ATUALIZADO.get() == (1, 40)


def test_contador_vai_ao_estado(gen_on, monkeypatch):
    def fake_node(state):
        cg.CONTADOR_ATUALIZADO.set((2, 41))
        return {"messages": [AIMessage(content="x")]}

    monkeypatch.setattr(combat, "_combat_node", fake_node)
    out = combat.combat_node({"world": dict(ZHUR)})
    assert out["world"]["creature_gen"] == {"novas": 2, "ultimo_turno": 41}
    assert out["world"]["current_location_id"] == "deserto_zhur"
    assert cg.CONTADOR_ATUALIZADO.get() is None


def test_art_brief_criatura_gerada(gen_on):
    from services.art_brief import build_creature_art_brief

    t = bst.generate_new_enemy(
        "Bebedor de Odres",
        "algo que vive dentro dos odres de água estragada",
        state={"game_id": "g-art", "world": dict(ZHUR)},
    )
    inst = combat._instances(t, 1, {}, None)[0]
    brief = build_creature_art_brief(inst, important=False)
    assert brief["player_description"] and brief["player_description"] in t["appearance"]
    var = combat._grounded_template(
        "lacaio mente-colmeia", "lacaio mente-colmeia", 1, {"world": dict(ZHUR)}
    )
    vb = build_creature_art_brief(combat._instances(var, 1, {}, None)[0], important=False)
    assert "mesma pose" in vb["player_description"]


def test_save_antigo_carrega(gen_on):
    """Inimigo e overlay do gerador antigo (EnemySchema) seguem válidos com a flag `on`."""
    import persistence
    from services import conflict_orchestrator as orch

    antigo = bst.materialize_enemy_concept(
        {"name": "Verme das Cinzas", "categoria": "padrao", "arquetipo": "bruto"}
    )
    bst.save_enemy(dict(antigo))
    inst = orch.ensure_combat_sheet({**antigo, "id": "enemy_verme_das_cinzas_1"})
    assert inst["max_vitalidade"] >= 1
    state = _start_state(hint="Verme das Cinzas", enemies=[inst], world=dict(ZHUR))
    state["game_id"] = "36136136-1361-4361-8361-361361361361"
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(
        persistence.save_path("36136136-1361-4361-8361-361361361361")
    )
    assert loaded["enemies"][0]["name"] == "Verme das Cinzas"
    assert "creature_gen" not in (loaded.get("world") or {})
    p = cg.PedidoCriatura.from_spawn(
        "x", "", state=loaded, encounter_level=1, location_id="deserto_zhur"
    )
    assert p.contador == (0, 0)
    # o overlay antigo (sem ficha) é achado de novo e não volta a gerar
    t = bst.generate_new_enemy("Verme das Cinzas", "", state=loaded)
    assert t["name"] == "Verme das Cinzas" and "ficha" not in t


def test_variante_telegrafa_antes_da_assinatura(gen_on, monkeypatch):
    """§6 passo 2 (offline): com baralhos e intenção ligados, o telegrafo da variante sai uma
    rodada antes da assinatura."""
    from services import enemy_decks

    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    var = combat._grounded_template(
        "lacaio mente-colmeia", "lacaio mente-colmeia", 1, {"world": dict(ZHUR)}
    )
    inst = combat._instances(var, 3, {}, 7)[0]
    sig = enemy_decks.assinatura_of(inst)
    assert sig and "congela no meio do passo" in sig["telegrafo"]
    rodadas = [r for r in range(1, 8) if enemy_decks.prenuncio(inst, r)]
    assert rodadas, "o telegrafo nunca apareceu"
    texto = enemy_decks.prenuncio(inst, rodadas[0])
    assert texto.startswith(inst["name"]) and "congela" in texto
    assert enemy_decks.plan(inst, rodadas[0] + 1)["assinatura"] == sig["carta"]
