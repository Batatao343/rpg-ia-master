"""SPEC-297 Etapa 5 - dedupe semantico (R15)."""

from services import shared_pool as sp
from services.shared_pool_models import PoolStatus
from tests.spec297_support import NOW, FakeJudge, entry, make_store, npc_doc, seed

PROFILE = "fake-8"


def embedder(text: str):
    """Embedding bag-of-letters determinístico (8 dims)."""
    vec = [0.0] * 8
    for ch in text.lower():
        vec[ord(ch) % 8] += 1.0
    return vec


def _promoted(store, name, persona, eid, profile=PROFILE):
    e = entry(
        name=name,
        status=PoolStatus.PROMOTED,
        entry_id=eid,
        doc=npc_doc(name, persona=persona),
        sd=seed(desire_id="des_cura"),
        embedding=embedder(sp.signature_text(entry(doc=npc_doc(name, persona=persona)))),
        embedding_profile=profile,
    )
    store.insert(e)
    return e


def test_near_duplicate_rejected_with_duplicate_of(tmp_path):
    store = make_store(tmp_path)
    base = _promoted(
        store,
        "Gertrudes Bronze",
        "Mulher calada que molda ferraduras e ouve a rua.",
        "pool_npc_base",
    )
    new = entry(
        name="Berta Cobre",
        entry_id="pool_npc_new",
        doc=npc_doc("Berta Cobre", persona="Mulher calada que molda ferraduras e ouve a rua."),
        sd=seed(desire_id="des_cura", fear_id="fear_frio"),
    )
    store.insert(new)
    judge = FakeJudge()
    out = sp.promote_due(store, now=NOW, llm=judge, embedder=embedder, embedding_profile=PROFILE)
    got = store.get("pool_npc_new")
    assert out["rejected"] == 1 and judge.calls == 0
    assert got.status == PoolStatus.REJECTED
    assert got.duplicate_of == base.entry_id
    assert got.evaluation["code"] == "near_duplicate"


def test_different_profile_not_compared(tmp_path):
    store = make_store(tmp_path)
    _promoted(
        store,
        "Gertrudes Bronze",
        "Mulher calada que molda ferraduras e ouve a rua.",
        "pool_npc_base",
        profile="outro-9",
    )
    new = entry(
        name="Berta Cobre",
        entry_id="pool_npc_new",
        doc=npc_doc("Berta Cobre", persona="Mulher calada que molda ferraduras e ouve a rua."),
        sd=seed(desire_id="des_cura", fear_id="fear_frio"),
    )
    dup, mode, vec, _ = sp.find_duplicate(
        new,
        store.select(statuses=[PoolStatus.PROMOTED]),
        embedder=embedder,
        embedding_profile=PROFILE,
    )
    assert dup is None and mode == "embedding" and vec is not None


def test_lexical_fallback_without_embedder(tmp_path):
    store = make_store(tmp_path)
    base = _promoted(
        store,
        "Gertrudes Bronze",
        "Mulher calada que molda ferraduras e ouve a rua.",
        "pool_npc_base",
    )
    new = entry(
        name="Berta Cobre",
        entry_id="pool_npc_new",
        doc=npc_doc("Berta Cobre", persona="Mulher calada que molda ferraduras e ouve a rua."),
        sd=seed(desire_id="des_cura"),
    )
    dup, mode, _vec, _ = sp.find_duplicate(new, [base], embedder=None)
    assert dup is not None and mode == "lexical"
    distinct = entry(
        name="Orik Pedra",
        entry_id="pool_npc_o",
        doc=npc_doc(
            "Orik Pedra",
            persona="Mineiro taciturno que tosse poeira de carvão",
            appearance="Baixo e largo",
        ),
        sd=seed(desire_id="des_cura", profession_id="prof_mineiro"),
    )
    assert sp.find_duplicate(distinct, [base], embedder=None)[0] is None


def test_origin_game_keeps_rejected_entity(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    store = make_store(tmp_path)
    _promoted(
        store,
        "Gertrudes Bronze",
        "Mulher calada que molda ferraduras e ouve a rua.",
        "pool_npc_base",
    )
    new = entry(
        name="Berta Cobre",
        entry_id="pool_npc_new",
        game="game-b",
        doc=npc_doc("Berta Cobre", persona="Mulher calada que molda ferraduras e ouve a rua."),
        sd=seed(desire_id="des_cura", fear_id="fear_frio"),
    )
    store.insert(new)
    sp.promote_due(store, now=NOW, llm=FakeJudge(), embedder=embedder, embedding_profile=PROFILE)
    rejected = store.get("pool_npc_new")
    assert rejected.status == PoolStatus.REJECTED
    assert sp.visible_entry(rejected, game_id="game-b")
    assert not sp.visible_entry(rejected, game_id="game-c")
