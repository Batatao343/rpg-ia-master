"""SPEC-349 Etapa 5/6 (12 regiões): mecânica, baralho próprio, padrão, assinatura e fases.

Fonte: ``data/bestiario/mecanica/<regiao>.yaml`` -> ``scripts/bestiario/gerar_mecanica.py`` ->
``data/bestiary.json`` + ``data/cards/criaturas/<regiao>.json`` + ``fases`` em ``_decks.json``.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pytest
import yaml

from agents.bestiary import load_bestiary
from services import bestiary_lint as bl
from services import card_effects as fx
from services import card_lint, cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import encounter_manifest as em
from services import enemy_decks as edk
from services.content_validator import validate_bestiary

ROOT = Path(__file__).resolve().parents[1]
FICHAS = {k: f for k, f in bl.load_fichas().items() if f.get("status") not in (None, "retro")}
BEST = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
CARD_FILES = sorted((ROOT / "data" / "cards" / "criaturas").glob("*.json"))
CARDS = {c["id"]: c for p in CARD_FILES for c in json.loads(p.read_text(encoding="utf-8"))["cards"]}
DECKS = json.loads(
    (ROOT / "data" / "cards" / "inimigos" / "_decks.json").read_text(encoding="utf-8")
)
AJ_PATH = ROOT / "data" / "bestiario" / "mecanica" / "_ajustes.yaml"
AJUSTES = (yaml.safe_load(AJ_PATH.read_text(encoding="utf-8")) or {}).get("ajustes", {})
NOVAS = {k: f for k, f in FICHAS.items() if f["status"] == "nova"}
SLOTS = {k: f for k, f in FICHAS.items() if f["status"] != "nova"}
CHEFES = {k: f for k, f in FICHAS.items() if f["categoria"] == "chefe"}
BAIRROS_CARTAS = {"lacaio": (2, 2), "padrao": (2, 3), "elite": (3, 3), "chefe": (3, 3)}


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_DECKS", raising=False)
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
    edk.reload()
    yield
    edk.reload()


def test_todas_as_regioes_tem_mecanica():
    assert len(FICHAS) >= 280
    for cid, f in FICHAS.items():
        assert cid in BEST, cid
        prof = BEST[cid]["tactical_profile"]
        assert prof["padrao"] == list(f["padrao"]), cid
        assert prof["assinatura"]["carta"] == f["mecanica_assinatura"]["carta"], cid
        assert prof["assinatura"]["a_cada_n"] == f["a_cada_n"], cid
        assert prof["assinatura"]["telegrafo"] == f["telegrafo"], cid


@pytest.mark.parametrize("cid", sorted(NOVAS))
def test_entrada_nova_shape(cid):
    f, e = NOVAS[cid], BEST[cid]
    assert e["origem"] == "bestiario-349" and e["onda"] == f["onda"]
    assert e["familia_valoria"] == f["familia"] and e["regions"] == [f["regiao"]]
    assert e["categoria"] == f["categoria"] and e["arquetipo"] == f["arquetipo"]
    assert e["appearance"] == f["aparencia"].strip() and len(e["appearance"]) <= 300
    assert (
        e["type"]
        == {"lacaio": "Minion", "padrao": "Standard", "elite": "Elite", "chefe": "BOSS"}[
            f["categoria"]
        ]
    )


def test_entradas_bestiario_validas():
    """R13: as 12 regiões passam em ``validate_bestiary`` (Virtudes 0-5, Vitalidade pela tabela
    de Corpo, fuga/rendição, Carta oculta, anti-clone)."""
    ids = set(FICHAS)
    achados = [f for f in validate_bestiary() if f.severity == "error" and f.item in ids]
    assert achados == [], [str(a) for a in achados[:5]]


def test_cartas_criaturas_lint():
    """R14: vocabulário, orçamento, voz e nomes únicos em todas as Cartas próprias."""
    pool = card_lint.load_pool()
    problemas = []
    for cid, c in CARDS.items():
        assert c["origem"] == "bestiario-349" and c["classe"] == "Inimigo", cid
        assert c["patamar"] == "inicial" and c["subclasse"] in FICHAS, cid
        outros = [o for o in pool if o["id"] != cid]
        issues = card_lint.errors(
            card_lint.check_vocabulary(c)
            + card_lint.check_budget(c)
            + card_lint.check_voice(c)
            + card_lint.check_names(c, outros)
        )
        problemas += [f"{cid}: {i.message}" for i in issues]
    assert problemas == [], problemas[:8]


@pytest.mark.parametrize("cid", sorted(FICHAS))
def test_baralho_proprio_por_categoria(cid):
    f, e = FICHAS[cid], BEST[cid]
    lo, hi = BAIRROS_CARTAS[f["categoria"]]
    propria = [c for c in e["cartas"] if c in CARDS]
    assert propria == e["cartas"] == e["cartas_autorais"], cid
    assert lo <= len(propria) <= hi, (cid, len(propria))
    assert any(CARDS[c].get("oculta") for c in propria), cid
    sig = f["mecanica_assinatura"]["carta"]
    assert sig in propria and CARDS[sig]["oculta"], cid
    assert CARDS[propria[0]]["id"] == propria[0]


def test_family_key_bate():
    """R14: o arquétipo da ficha é o do bestiário (slot congelado, R3) e resolve para a família."""
    for cid, f in FICHAS.items():
        familia = edk.family_key({**BEST[cid], "id": cid})
        assert familia == BEST[cid]["arquetipo"] == f["arquetipo"], cid


def test_padrao_e_assinatura_validos(monkeypatch):
    """R15: com ``on`` o plano devolve a assinatura na rodada certa e o telegrafo vem 1 antes."""
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    for cid, f in FICHAS.items():
        e = dict(BEST[cid])
        actor = {**e, "id": cid + "_1", "archetype_id": cid, "vitalidade": e["max_vitalidade"]}
        sig = edk.assinatura_of(actor)
        assert sig and sig["carta"] == f["mecanica_assinatura"]["carta"], cid
        assert sig["carta"] in cards.enemy_card_ids(actor), cid
        assert 2 <= len(edk.pattern_of(actor)) <= 4, cid
        rodadas = [r for r in range(2, 14) if edk._sig_falls_on(actor, sig, r)]
        assert rodadas, cid
        r = rodadas[0]
        plano = edk.plan(actor, r)
        assert plano and plano["assinatura"] == sig["carta"], (cid, r)
        assert edk.prenuncio(actor, r - 1) == f["telegrafo"].format(nome=e["name"]), cid


def test_chefe_fases(monkeypatch):
    """R16: o chefe troca de fase a 60 % e a 40 %, acrescenta Cartas e narra com o nome."""
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    assert len(CHEFES) >= 13
    for cid in CHEFES:
        fases = DECKS["fases"][cid]
        assert len(fases) == 2, cid
        assert [x["ate_vitalidade_pct"] for x in fases] == sorted(
            (x["ate_vitalidade_pct"] for x in fases), reverse=True
        ), cid
        for fz in fases:
            assert "{nome}" in fz["narracao"] and fz["baralho_extra"], cid
            for extra in fz["baralho_extra"]:
                assert extra in CARDS and CARDS[extra]["oculta"], (cid, extra)
                assert extra not in BEST[cid]["cartas"], (cid, extra)
        ator = {**BEST[cid], "id": cid, "archetype_id": cid}
        ator["vitalidade"] = ator["max_vitalidade"]
        sides = {"enemy": [cid]}
        out: dict = {}
        assert edk.apply_phases({cid: ator}, sides, out) is False
        ator["vitalidade"] = 1  # abaixo de todos os limiares
        assert edk.apply_phases({cid: ator}, sides, out, rnd=2) is True
        assert ator["fase_idx"] == 2 and len(out["logs"]) == 2
        assert all(ator["name"] in linha for linha in out["logs"]), cid
        assert set(sum((x["baralho_extra"] for x in fases), [])) <= set(ator["cartas"])


def test_resolve_por_nome():
    """R34: o nome resolve no id; o núcleo do nome não repete na mesma região."""
    best = load_bestiary()
    for cid in FICHAS:
        assert em.resolve_bestiary_name(best[cid]["name"], best) == cid, cid
    por_regiao: dict[str, dict[str, str]] = {}
    for cid, f in NOVAS.items():
        nucleo = em.name_tokens(f["nome"])[0]
        seen = por_regiao.setdefault(f["regiao"], {})
        assert nucleo not in seen, (f["regiao"], nucleo, cid, seen.get(nucleo))
        seen[nucleo] = cid


def test_appearance_chega_ao_art_brief():
    """R18: ``appearance`` do chefe sobrevive à ficha de combate e chega à linha ``BOSS:``.
    O slot ``enemy_aranha_de_cristal`` teve o ``type`` legado ("Monstrosidade") trocado por
    ``BOSS``, então entra em ``art_brief._BOSS_TYPES`` como os demais."""
    from services.art_brief import _boss_of

    for cid in CHEFES:
        ficha = orch.ensure_combat_sheet(
            {**BEST[cid], "id": cid, "name": BEST[cid]["name"]}, is_player=False
        )
        assert ficha.get("appearance") == BEST[cid]["appearance"], cid
        boss = _boss_of({"enemies": [ficha]})
        assert boss and boss["appearance"], cid


def test_ajustes_registrados_e_slots_sem_corpo():
    """Cada ajuste da arena tem a leitura que o motivou; slots nunca mexem em Virtudes (R3)."""
    for cid, a in AJUSTES.items():
        assert cid in FICHAS, cid
        assert isinstance(a.get("arena"), str) and "L" in a["arena"], cid
        for chave in ("corpo", "dano", "forca", "sig"):
            assert abs(int(a.get(chave, 0))) <= 7, (cid, chave)
        if cid in SLOTS:
            assert not a.get("corpo"), cid


def test_orcamento_das_cartas_com_modo_on_funciona(monkeypatch):
    """O baralho montado com ``on`` mantém as Cartas próprias primeiro e na ordem."""
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    rng = random.Random(3)
    for cid in rng.sample(sorted(FICHAS), 25):
        deck = edk.build_enemy_deck({**BEST[cid], "id": cid}, seed=1)
        assert deck[: len(BEST[cid]["cartas"])] == BEST[cid]["cartas"], cid


def test_cenas_nao_quebram_com_cartas_novas():
    """Smoke: toda Carta nova é resolvível pelo catálogo de Cartas (``cards.get_card``)."""
    for cid in CARDS:
        assert cards.get_card(cid), cid
        assert fx.primary_effect(cards.get_card(cid)), cid
    scene = cs.new_scene()
    assert scene is not None


def test_uso_das_cartas_de_familia_escala_com_o_bestiario(monkeypatch):
    """Teto de 15 criaturas por Carta de família (332) na população inteira, esteira incluída.

    SUPERADO_POR: SPEC-373 (R16, Etapa E). O teto proporcional de 36 da SPEC-349 caiu: a regra
    de montagem do R9 e as Cartas novas da Parte B2 trazem o uso de volta a 15. Gate congelado
    pelo autor de eval (``handoffs/SPEC-373-eval-authoring.md``); o executor não o edita."""
    import collections

    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    use: collections.Counter = collections.Counter()
    for bid, entry in BEST.items():
        deck = edk.build_enemy_deck({**entry, "id": bid}, 0)
        use.update(c for c in deck if c.startswith("inf_"))
    assert use and max(use.values()) <= 15, use.most_common(3)


@pytest.mark.parametrize("modo", ["off", "on"])
def test_save_load_com_criatura_nova_e_slot_em_bestiary_knowledge(monkeypatch, modo):
    """Critério de saves antigos: round-trip com criatura nova e o slot `enemy_gargula_ferro`
    nos inimigos e em `bestiary_knowledge`, com `off` e `on`."""
    import persistence

    monkeypatch.setenv("RPG_ENEMY_DECKS", modo)
    edk.reload()
    inimigos = []
    for cid in ("mon_roda_de_mandibulas", "enemy_gargula_ferro"):
        e = orch.ensure_combat_sheet({**BEST[cid], "id": f"{cid}_1"}, is_player=False)
        inimigos.append(e)
    gid = f"pytest349-{modo}"
    state = {
        "game_id": gid,
        "narrative_summary": "",
        "archivist_last_run": 0,
        "messages": [],
        "npcs": {},
        "factions": [],
        "campaign_plan": {},
        "player": {"name": "T", "class_name": "Devoto do Abismo", "level": 3},
        "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia"},
        "enemies": inimigos,
        "bestiary_knowledge": {
            "enemy_gargula_ferro": {"revealed_cards": ["cri_ra_de_lotus_mordida_adiantada"]}
        },
    }
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(os.path.join(persistence.SAVES_DIR, f"{gid}.json"))
    assert loaded["bestiary_knowledge"] == state["bestiary_knowledge"]
    for antes, depois in zip(state["enemies"], loaded["enemies"], strict=True):
        for campo in ("cartas", "tactical_profile", "max_vitalidade", "appearance"):
            assert depois.get(campo) == antes.get(campo), (antes["id"], campo)
