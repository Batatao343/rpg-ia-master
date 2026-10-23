"""Fábricas compartilhadas dos testes da SPEC-297 (não é um arquivo de teste)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from infrastructure.shared_pool_store import JsonSharedPoolStore
from services import shared_pool as sp
from services.npc_seed import NpcSeed
from services.shared_pool_models import (
    PoolCriterion,
    PoolEvaluation,
    PoolNamespace,
    PoolStatus,
    SharedPoolEntry,
    fold_name,
)

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
OWNER_A = UUID("00000000-0000-0000-0000-00000000000a")
OWNER_B = UUID("00000000-0000-0000-0000-00000000000b")


def make_store(tmp_path):
    return JsonSharedPoolStore(lambda: tmp_path / "shared_pool.json")


def seed(**over) -> NpcSeed:
    base = {
        "race_id": "race_anoes_fuligem",
        "origin_region_id": "nova_arcadia",
        "home_location_id": "na_anel_lama",
        "faction_id": "legiao_ferro",
        "profession_id": "prof_ferreiro",
        "desire_id": "des_paz",
        "fear_id": "fear_fogo",
        "secret_id": "sec_roubou_uma_vez",
        "contradiction_id": "con_calmo_irritavel",
        "mannerism_id": "man_cantarola",
    }
    base.update(over)
    return NpcSeed(**base)


def npc_doc(name="Brunhilda Cobreira", **over) -> dict:
    doc = {
        "id": "npc_" + fold_name(name).replace(" ", "_"),
        "name": name,
        "role": "Ferreira de aldeia",
        "persona": "Mulher calada que molda ferraduras e ouve o que a rua comenta.",
        "appearance": "Ombros largos, barba trançada com fio de cobre.",
        "attributes": {"str": 12, "dex": 10, "con": 14, "int": 10, "wis": 11, "cha": 9},
        "initial_relationship": 5,
        "legend": "Dizem que nunca vendeu uma lâmina torta.",
    }
    doc.update(over)
    return doc


def entry(
    *,
    name="Brunhilda Cobreira",
    status=PoolStatus.HELD,
    ns=PoolNamespace.NPC,
    game="game-a",
    owner=OWNER_A,
    created=None,
    promote_after=None,
    region="nova_arcadia",
    doc=None,
    sd=None,
    entry_id=None,
    shingles=None,
    **over,
) -> SharedPoolEntry:
    created = created or NOW - timedelta(days=2)
    s = sd if sd is not None else seed()
    return SharedPoolEntry(
        entry_id=entry_id or f"pool_npc_{fold_name(name).replace(' ', '')[:12]}",
        namespace=ns,
        status=status,
        region_id=region,
        name=name,
        name_fold=fold_name(name),
        name_origin="narrator",
        document=doc if doc is not None else npc_doc(name),
        legend="Dizem que nunca vendeu uma lâmina torta.",
        seed=s,
        seed_signature=sp.seed_signature(s) if s else "",
        origin_owner_id=owner,
        origin_game_id=game,
        input_shingles=shingles or [],
        created_at=created,
        promote_after=promote_after or (created + timedelta(hours=24)),
        **over,
    )


def all_ok() -> PoolEvaluation:
    ok = PoolCriterion(ok=True, reason="ok")
    return PoolEvaluation(lore=ok, uniqueness=ok, content=ok, pii=ok, injection=ok)


class FakeJudge:
    """LLM falso: `with_structured_output(X).invoke(msgs)` devolve `result` e conta chamadas."""

    def __init__(self, result=None, raises=None):
        self.result = result if result is not None else all_ok()
        self.raises = raises
        self.calls = 0
        self.prompts: list = []

    def with_structured_output(self, schema):
        outer = self

        class _Bound:
            def invoke(self, messages):
                outer.calls += 1
                outer.prompts.append(messages)
                if outer.raises:
                    raise outer.raises
                return outer.result

        return _Bound()
