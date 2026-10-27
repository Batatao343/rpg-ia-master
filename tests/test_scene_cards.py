"""SPEC-331 R1-R3, R6, R8, R9 - Cartas de Cena (catálogo, elegibilidade, tick, presságio, LLM)."""

import random

import pytest

from services import card_effects as fx
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import encounter_preparation as prep
from services import scene_cards as sc

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}


def _actor(aid, **kw):
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _scene(ids=("player", "e"), cartas=()):
    scene = cs.new_scene([{"id": "z0", "name": "Campo", "connections": ["z1"]}])
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    scene["cartas_de_cena"] = list(cartas)
    return scene


def _ctx(scene, actors):
    return fx.Ctx(
        scene=scene,
        actors_by_id=actors,
        sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1),
    )


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")


def _cond_names(actor):
    return [c.get("name") or c.get("keyword") for c in actor.get("active_conditions") or []]


# ------------------------------------------------------------------ R1 catálogo
def test_catalogo_tem_24_cartas_e_valida():
    import json

    data = json.loads(sc._CATALOG_PATH.read_text(encoding="utf-8"))
    assert len(data["cartas"]) == 24
    assert sc.validate_catalog(data) == []


def test_validador_rejeita_efeito_e_acao_fora_do_catalogo():
    bad = {
        "cartas": [
            {
                "id": "x",
                "nome": "X",
                "pressagio": "p",
                "sabor": "s",
                "quando": "fim_rodada",
                "efeitos": [{"kind": "inventado"}],
                "acoes": [{"tipo": "explodir"}],
            }
        ]
    }
    errs = sc.validate_catalog(bad)
    assert any("fora do catálogo" in e for e in errs)
    assert any("acoes[0]" in e for e in errs)


# ------------------------------------------------------------------ flag off
def test_flag_off_e_o_padrao(monkeypatch):
    monkeypatch.delenv("RPG_SCENE_CARDS", raising=False)
    assert sc.mode() == "off"
    monkeypatch.setenv("RPG_SCENE_CARDS", "lixo")
    assert sc.mode() == "off"


def test_off_tick_nao_faz_nada(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "off")
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene(cartas=["nevoa_cinza_do_ermo"])
    assert sc.tick(_ctx(scene, actors), 1, "fim_rodada", {}) == []
    assert sc.forecast(scene, 1) == []
    assert "cena_estado" not in scene


def test_off_prompt_e_schema_identicos(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "off")
    assert prep._scene_cards_prompt({"location": "Skallgard"}) == ""
    captured = {}

    class _LLM:
        def with_structured_output(self, schema):
            captured["schema"] = schema
            return self

        def invoke(self, prompt):
            captured["prompt"] = prompt
            return prep.PreparedScene()

    prep.prepare_encounter({"location": "Skallgard", "enemies": [], "encounter_level": 1}, _LLM())
    assert captured["schema"] is prep.PreparedScene
    assert "cartas_de_cena" not in captured["prompt"]


# ------------------------------------------------------------------ R2 elegibilidade
def test_elegibilidade_por_regiao_e_tags():
    ids = {c["id"] for c in sc.eligible("Skallgard")}
    assert "nevoa_cinza_do_ermo" in ids
    assert "geada_do_abismo" in ids
    assert "esporos_de_xylos" not in ids
    assert "tempestade_de_eter" in ids  # universal
    # tags: o Anel de Ferro é industrial -> Chão da Fornalha; o Anel Dourado não é.
    assert "chao_da_fornalha" in {c["id"] for c in sc.eligible("Anel de Ferro")}
    assert "chao_da_fornalha" not in {c["id"] for c in sc.eligible("Anel Dourado")}


def test_id_fora_do_catalogo_ou_inelegivel_e_descartado(on):
    got = sc.sanitize_choices(
        ["nevoa_cinza_do_ermo", "carta_inventada", "esporos_de_xylos", "nevoa_cinza_do_ermo"],
        "Skallgard",
    )
    assert got == ["nevoa_cinza_do_ermo"]


def test_maximo_duas_cartas(on):
    got = sc.sanitize_choices(
        ["nevoa_cinza_do_ermo", "geada_do_abismo", "noite_de_seis_meses"], "Skallgard"
    )
    assert len(got) == 2


def test_prompt_limita_a_12_e_nao_tem_numero_de_efeito():
    opts = sc.prompt_options("Skallgard")
    assert 0 < len(opts) <= 12
    assert all(set(o) == {"id", "nome", "sabor"} for o in opts)


# ------------------------------------------------------------------ R8/R9 LLM
class _LLM:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, prompt):
        self.calls += 1
        self.prompt = prompt
        return self.result


def test_llm_escolhe_cartas_no_mesmo_structured_output(on):
    result = prep.PreparedSceneWithCards(
        zones=[prep.PreparedZone(id="z0", name="Ermo")],
        cartas_de_cena=["nevoa_cinza_do_ermo", "fantasma_inventado"],
    )
    llm = _LLM(result)
    scene = prep.prepare_encounter(
        {"location": "Skallgard", "enemies": [], "encounter_level": 1}, llm
    )
    assert llm.calls == 1  # R9: nenhuma chamada nova
    assert llm.schema is prep.PreparedSceneWithCards
    assert "nevoa_cinza_do_ermo" in llm.prompt and "Cego" not in llm.prompt
    assert scene["cartas_de_cena"] == ["nevoa_cinza_do_ermo"]


def test_shadow_nao_grava_na_cena(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "shadow")
    llm = _LLM(
        prep.PreparedSceneWithCards(
            zones=[prep.PreparedZone(id="z0")], cartas_de_cena=["nevoa_cinza_do_ermo"]
        )
    )
    scene = prep.prepare_encounter(
        {"location": "Skallgard", "enemies": [], "encounter_level": 1}, llm
    )
    assert "cartas_de_cena" not in scene


def test_guard_fallback_llm_cena_sem_cartas_e_objetivo_padrao(on):
    from langchain_core.messages import AIMessage

    scene = prep.prepare_encounter(
        {"location": "Skallgard", "enemies": [], "encounter_level": 1},
        _LLM(AIMessage(content="erro")),
    )
    assert scene.get("safe_fallback") is True
    assert not scene.get("cartas_de_cena")
    assert "objetivo" not in scene


# ------------------------------------------------------------------ tick determinístico
def test_nevoa_aplica_cego_so_a_quem_esta_visivel(on):
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene(cartas=["nevoa_cinza_do_ermo"])
    scene["positions"]["e"]["ocultacao"] = "escondido"
    ev = sc.tick(_ctx(scene, actors), 1, "fim_rodada", {"logs": [], "terminal": [], "deaths": []})
    assert [e["card_id"] for e in ev] == ["nevoa_cinza_do_ermo"]
    assert "cego" in [str(n).casefold() for n in _cond_names(actors["player"])]
    assert not _cond_names(actors["e"])


def test_tick_e_deterministico(on):
    def run():
        actors = {"player": _actor("player"), "e": _actor("e")}
        scene = _scene(cartas=["chao_da_fornalha"])
        out = {"logs": [], "terminal": [], "deaths": []}
        sc.tick(_ctx(scene, actors), 1, "fim_rodada", out)
        return out["logs"], _cond_names(actors["player"])

    assert run() == run()


def test_a_cada_n_rodadas_e_uma_vez(on):
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene(cartas=["sinos_de_nova_arcadia", "telhado_que_cede"])
    cs.add_object(scene, {"id": "viga", "name": "Viga", "interactions": []}, from_trigger=True)
    ctx = _ctx(scene, actors)
    fired = [
        [
            e["card_id"]
            for e in sc.tick(ctx, r, "fim_rodada", {"logs": [], "terminal": [], "deaths": []})
        ]
        for r in (1, 2, 3, 4, 5, 6)
    ]
    assert fired[2] == ["sinos_de_nova_arcadia"] and fired[5] == ["sinos_de_nova_arcadia"]
    assert fired[0] == fired[1] == fired[3] == []
    # Telhado: inicio_rodada, a partir da 3, uma vez só; derruba o objeto.
    out = {"logs": [], "terminal": [], "deaths": []}
    first = sc.tick(ctx, 3, "inicio_rodada", out)
    again = sc.tick(ctx, 4, "inicio_rodada", out)
    assert [e["card_id"] for e in first] == ["telhado_que_cede"] and again == []
    assert scene["objects"][0]["destroyed"] is True


def test_shadow_registra_mas_nao_muda_estado(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "shadow")
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene(cartas=["nevoa_cinza_do_ermo"])
    assert sc.tick(_ctx(scene, actors), 1, "fim_rodada", {}) == []
    assert not _cond_names(actors["player"])


# ------------------------------------------------------------------ R3 presságio
def test_pressagio_uma_rodada_antes_e_sem_numeros(on):
    scene = _scene(cartas=["sinos_de_nova_arcadia"])
    assert sc.forecast(scene, 2) == []
    got = sc.forecast(scene, 3)
    assert [g["id"] for g in got] == ["sinos_de_nova_arcadia"]
    assert set(got[0]) == {"id", "nome", "pressagio", "quando", "rodada"}


def test_run_round_dispara_carta_de_cena_e_loga(on):
    player, e = _actor("player"), _actor("e")
    scene = _scene(cartas=["nevoa_cinza_do_ermo"])
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": {"actor_id": "player"}},
        rng=random.Random(2),
    )
    assert any("Névoa Cinza do Ermo" in line for line in out["logs"])
    assert out["scene_cards"][0]["card_id"] == "nevoa_cinza_do_ermo"


# ------------------------------------------------------------------ R6 objeto vira carta
def _scene_com_objeto():
    scene = _scene()
    cs.add_object(
        scene,
        {
            "id": "barril",
            "name": "Barril de óleo",
            "zone_id": "z0",
            "uses_remaining": 1,
            "interactions": [
                {
                    "label": "derrubar",
                    "effect": {"kind": "damage", "params": {"amount": 3, "target": "e"}},
                }
            ],
        },
        from_trigger=True,
    )
    return scene


def _piles():
    return {"compra": ["a"], "mao": ["a"], "descarte": [], "exaurida": []}


def test_objeto_vira_carta_na_mao_e_sai_ao_sair_da_zona(on, monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    scene, piles = _scene_com_objeto(), _piles()
    ids = sc.sync_hand(scene, piles, "player")
    assert len(ids) == 1 and ids[0] in piles["mao"]
    from services import cards

    card = cards.get_card(ids[0])
    assert card["frequencia"] == "cena" and card["custo_folego"] == 1
    assert card["palavras_chave"] == {"exaurir": True}
    scene["positions"]["player"]["zone_id"] = "z1"
    assert sc.sync_hand(scene, piles, "player") == []
    assert piles["mao"] == ["a"]


def test_objeto_carta_nunca_vira_baralho_e_sem_328_nao_age(on, monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    scene, piles = _scene_com_objeto(), _piles()
    piles["descarte"] = ["cena_barril_x"]
    sc.sync_hand(scene, piles, "player")
    assert piles["descarte"] == []
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    assert sc.sync_hand(scene, _piles(), "player") == []
