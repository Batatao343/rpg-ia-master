"""SPEC-297 Etapa 3 - geracao ligada ao pool (R7-R9, R13, R27)."""

import pytest
from langchain_core.messages import AIMessage

import agents.bestiary as bst_mod
import agents.npc as npc_mod
from services import shared_pool as sp
from services.shared_pool_models import PoolNamespace, PoolStatus
from tests.spec297_support import entry, npc_doc, seed

SCENE = "CENA-SECRETA-DO-JOGADOR-XYZ"


class RecordingLLM:
    def __init__(self, result=None):
        self.result = result
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        outer = self

        class _B:
            def invoke(self, messages):
                outer.prompts.append("\n".join(str(m.content) for m in messages))
                if outer.result is not None:
                    return outer.result
                return schema(**_defaults(schema))

        return _B()


def _defaults(schema):
    if schema is npc_mod.NPCSchema:
        return dict(
            name="x",
            role="Ferreira",
            location="Praça",
            persona="Calada e firme, molda ferraduras.",
            appearance="Ombros largos.",
            attributes={"str": 12, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 9},
            legend="Dizem que nunca errou uma ferradura.",
        )
    return dict(
        name="Verme das Cinzas",
        description="Verme que escava nas fundições.",
        categoria="padrao",
        regions=["nova_arcadia"],
    )


@pytest.fixture
def pool_on(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    sp.reset_default_store()
    yield
    sp.reset_default_store()


def _gen(monkeypatch, llm, **kw):
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(npc_mod, "query_rag", lambda *a, **k: "lore publica")
    return npc_mod.generate_new_npc(
        "Brunhilda Cobreira",
        f"Local: Anel de Lama. Cena: {SCENE}",
        game_id="game-a",
        location_id="na_anel_lama",
        turn=3,
        **kw,
    )


def test_off_generate_npc_prompt_still_has_scene(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    llm = RecordingLLM()
    saved = []
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(npc_mod, "query_rag", lambda *a, **k: "")
    monkeypatch.setattr(npc_mod, "save_npc_template", lambda d: saved.append(d))
    npc_mod.generate_new_npc("Brunhilda", f"Cena: {SCENE}", game_id="game-a")
    assert SCENE in llm.prompts[0] and len(saved) == 1
    assert sp.get_store().select() == []


def test_flag_on_prompt_has_seed_not_scene(monkeypatch, pool_on):
    llm = RecordingLLM()
    data = _gen(monkeypatch, llm)
    prompt = llm.prompts[0]
    assert SCENE not in prompt
    assert "<semente>" in prompt and "lore publica" in prompt
    assert data["pool_entry_id"].startswith("pool_npc_")


def test_generated_npc_submitted_held_not_user_scope(monkeypatch, pool_on):
    saved = []
    monkeypatch.setattr(npc_mod, "save_npc_template", lambda d: saved.append(d))
    _gen(monkeypatch, RecordingLLM())
    assert saved == []  # R9: submissão substitui a escrita no catálogo
    [e] = sp.get_store().select(namespace=PoolNamespace.NPC)
    assert e.status == PoolStatus.HELD and e.origin_game_id == "game-a"
    assert e.seed is not None and e.name_origin == "narrator"
    assert set(e.document) <= set(
        __import__("services.shared_pool_models", fromlist=["x"]).DOCUMENT_ALLOWLIST[
            PoolNamespace.NPC
        ]
    )
    assert e.legend.startswith("Dizem")


def test_fallback_never_submitted(monkeypatch, pool_on):
    data = _gen(monkeypatch, RecordingLLM(AIMessage(content="erro")))
    assert data["id"] == "fallback"
    assert sp.get_store().select() == []


def test_player_named_npc_not_pool_eligible(monkeypatch, pool_on):
    _gen(monkeypatch, RecordingLLM(), name_origin="player")
    [e] = sp.get_store().select(namespace=PoolNamespace.NPC)
    assert e.status == PoolStatus.LOCAL_ONLY


def test_own_hold_found_by_name_but_other_game_pool_is_not(monkeypatch, pool_on):
    sp.get_store().insert(
        entry(
            name="Garrick Pedra", status=PoolStatus.PROMOTED, game="game-z", entry_id="pool_npc_z"
        )
    )
    own = entry(
        name="Brunhilda Cobreira", status=PoolStatus.HELD, game="game-a", entry_id="pool_npc_own"
    )
    sp.get_store().insert(own)
    db = npc_mod.load_npc_db("game-a")
    names = {v.get("name") for v in db.values()}
    assert "Brunhilda Cobreira" in names and "Garrick Pedra" not in names  # R25


def test_cache_hit_never_puts_promoted(monkeypatch, pool_on):
    store = sp.get_store()
    promoted = entry(status=PoolStatus.PROMOTED, game="game-a", entry_id="pool_npc_p")
    store.insert(promoted)
    before = store.get("pool_npc_p")
    llm = RecordingLLM()
    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(
        npc_mod, "find_existing_entity", lambda name, kind, ids: ids[0] if ids else None
    )
    data = npc_mod.generate_new_npc("Brunhilda Cobreira", "Local: x", game_id="game-a")
    assert llm.prompts == []  # cache-hit: sem LLM
    assert data["name"] == "Brunhilda Cobreira"
    assert store.get("pool_npc_p") == before and len(store.select()) == 1


def test_guard_fallbackllm_generation(monkeypatch, pool_on):
    class Boom(RecordingLLM):
        def with_structured_output(self, schema):
            raise RuntimeError("sem structured output")

    data = _gen(monkeypatch, Boom())
    assert data["id"] == "fallback" and sp.get_store().select() == []


def test_bestiary_submit_and_promoted_visible_by_name(monkeypatch, pool_on):
    llm = RecordingLLM()
    monkeypatch.setattr(bst_mod, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(bst_mod, "query_rag", lambda *a, **k: "lore")
    monkeypatch.setattr(
        bst_mod,
        "find_existing_entity",
        lambda name, kind, ids: (
            next((i for i in ids if i.startswith("pool_")), None) if "Verme" in name else None
        ),
    )
    out = bst_mod.generate_new_enemy(
        "Verme das Cinzas",
        "ctx",
        game_id="game-a",
        location_id="na_anel_ferro",
        name_origin="narrator",
    )
    assert out["name"] and out["max_vitalidade"] > 0
    [e] = sp.get_store().select(namespace=PoolNamespace.CREATURE)
    assert (
        e.status == PoolStatus.HELD
        and "max_vitalidade" not in e.document
        and e.region_id == "nova_arcadia"
    )
    # promovida: o jogo B (flag on) enxerga o TIPO pela view do bestiário, ficha recalculada pelo motor
    sp.get_store().update(e.entry_id, {"status": "promoted"})
    view = bst_mod.load_bestiary("game-b", "nova_arcadia")
    pooled = [v for v in view.values() if v.get("pool_entry_id") == e.entry_id]
    assert pooled and pooled[0]["max_vitalidade"] > 0 and pooled[0]["virtudes"]
    # flag shadow: nenhum leitor expõe entrada de outro jogo
    import os

    os.environ["RPG_SHARED_POOL"] = "shadow"
    assert not [v for v in bst_mod.load_bestiary("game-b", "nova_arcadia").values() if v.get("pool_entry_id")]
    os.environ["RPG_SHARED_POOL"] = "on"


def test_pooled_creature_numbers_ignored(monkeypatch, pool_on):
    e = entry(
        ns=PoolNamespace.CREATURE,
        status=PoolStatus.PROMOTED,
        game="game-z",
        name="Verme Forte",
        entry_id="pool_bst_1",
        sd=None,
        doc={
            "id": "pool_verme",
            "name": "Verme Forte",
            "description": "d",
            "categoria": "padrao",
            "arquetipo": "bruto",
            "max_vitalidade": 9999,
        },
    )
    sp.get_store().insert(e)
    tpl = bst_mod._pool_creature_template(e)
    assert tpl["max_vitalidade"] != 9999


def test_npc_doc_helper_still_clean():
    assert npc_doc()["name"] and seed().race_id
