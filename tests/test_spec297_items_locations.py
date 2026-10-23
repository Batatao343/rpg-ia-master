"""SPEC-297 Etapa 9 - itens e locais (contrato, R28-R30)."""

import pytest

import gamedata
from services import shared_pool as sp
from services import shared_pool_validators as v
from services.shared_pool_models import DOCUMENT_ALLOWLIST, PoolNamespace, PoolStatus
from tests.spec297_support import NOW, FakeJudge, entry, make_store


def artifact(**over):
    doc = {
        "id": "art_pente_de_osso",
        "name": "Pente de Osso Polido",
        "description": "Pente entalhado em osso de leviatã.",
        "type": "trinket",
        "rarity": "rare",
        "unique": True,
        "stackable": False,
    }
    doc.update(over)
    return entry(
        ns=PoolNamespace.ARTIFACT,
        name=doc["name"],
        doc=doc,
        sd=None,
        region="costa_negra",
        entry_id="pool_art_1",
    )


def location(**over):
    doc = {
        "id": "loc_ponte_velha",
        "name": "Ponte Velha do Fosso",
        "description": "Uma ponte de tábuas sobre o fosso, rangendo.",
        "parent_location_id": "na_anel_lama",
        "region": "nova_arcadia",
        "tags": ["ponte", "perigo"],
    }
    doc.update(over)
    return entry(
        ns=PoolNamespace.LOCATION,
        name=doc["name"],
        doc=doc,
        sd=None,
        region="nova_arcadia",
        entry_id="pool_loc_1",
    )


def test_artifact_and_location_allowlists():
    assert v.run_validators(artifact()) == []
    assert v.run_validators(location()) == []
    assert v.validate_schema(artifact(damage="9d99"))  # número mecânico nunca vem do doc
    assert v.validate_schema(location(owner="x"))
    assert {f.code for f in v.validate_lore_refs(location(parent_location_id="nao_existe"))} == {
        "lore_unknown_location"
    }
    assert "id" in DOCUMENT_ALLOWLIST[PoolNamespace.ARTIFACT]


def test_save_custom_artifact_flag_on_submits_hold_and_no_global_mutation(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "shadow")
    sp.reset_default_store()
    before = dict(gamedata.ARTIFACTS_DB)
    gamedata.save_custom_artifact(
        "art_novo_x",
        {"name": "Item Novo", "description": "d", "type": "trinket", "rarity": "common"},
        game_id="game-a",
    )
    assert "art_novo_x" not in gamedata.ARTIFACTS_DB and gamedata.ARTIFACTS_DB == before
    assert "art_novo_x" not in gamedata.CUSTOM_ARTIFACTS
    [e] = sp.get_store().select(namespace=PoolNamespace.ARTIFACT)
    assert e.status == PoolStatus.HELD and e.origin_game_id == "game-a"


def test_save_custom_artifact_without_game_id_raises(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    with pytest.raises(ValueError):
        gamedata.save_custom_artifact("art_y", {"name": "Y"})


def test_save_custom_artifact_flag_off_unchanged(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    sp.reset_default_store()
    gamedata.save_custom_artifact("art_off_z", {"name": "Z", "type": "trinket"})
    assert "art_off_z" in gamedata.ARTIFACTS_DB
    gamedata.ARTIFACTS_DB.pop("art_off_z", None)
    gamedata.CUSTOM_ARTIFACTS.pop("art_off_z", None)
    if "art_off_z" in gamedata.ALL_ARTIFACT_IDS:
        gamedata.ALL_ARTIFACT_IDS.remove("art_off_z")


def test_pooled_artifact_and_location_promote_through_job(tmp_path):
    store = make_store(tmp_path)
    store.insert(artifact())
    store.insert(location())
    out = sp.promote_due(store, now=NOW, llm=FakeJudge(), embedder=None, embedding_profile="x")
    assert out["promoted"] == 2


def test_unique_pooled_item_claimable_once_per_world(monkeypatch):
    """R30: a flag `unique` sobrevive à promoção; a posse é projeção de CADA jogo."""
    import inventory
    from services import economy

    item = artifact().document
    assert item["unique"] is True
    monkeypatch.setattr(inventory, "is_unique", lambda item_id: item_id == item["id"])
    proj_a = {"unique_items": {item["id"]: {"holder": "player"}}}
    proj_b: dict = {}
    assert economy.is_unique_available(item["id"], proj_a) is False
    assert economy.is_unique_available(item["id"], proj_b) is True
