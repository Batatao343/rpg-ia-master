"""SPEC-223 R7 — catálogo gerado por owner (D-B), 1 put por criação, tier fixo FAST."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from infrastructure.contracts import Principal
from infrastructure.request_context import principal_scope


class FakeCatalog:
    def __init__(self, seed: dict | None = None):
        self.rows: dict = {}  # (namespace, scope_owner) -> {key: value}
        self.puts: list = []
        for key, value in (seed or {}).items():
            self.rows.setdefault(("npc_template", None), {})[key] = value

    def list(self, namespace, *, owner_id, game_id):
        return dict(self.rows.get((namespace, owner_id), {}))

    def get(self, namespace, key, *, owner_id, game_id):
        return self.rows.get((namespace, owner_id), {}).get(key)

    def put(self, namespace, key, value, *, scope, owner_id, game_id):
        self.puts.append((namespace, key, scope, owner_id, game_id))
        self.rows.setdefault((namespace, owner_id), {})[key] = value


@pytest.fixture
def catalog(monkeypatch):
    fake = FakeCatalog(
        seed={
            "npc_curado": {
                "id": "npc_curado",
                "name": "Curado",
                "role": "guarda",
                "persona": "sério",
            }
        }
    )
    import infrastructure.runtime as runtime

    monkeypatch.setattr(runtime, "get_runtime", lambda: SimpleNamespace(runtime_catalog=fake))
    return fake


def _principal(uid: uuid.UUID) -> Principal:
    return Principal(uid, "test", str(uid))


def test_generated_npc_template_is_global_today(catalog):
    """Etapa 0: com principal, o template gerado vai para o escopo do DONO, 1 put só."""
    from agents.npc import save_npc_template

    owner = uuid.uuid4()
    with principal_scope(_principal(owner)):
        save_npc_template({"id": "npc_novo", "name": "Novo", "role": "r", "persona": "p"})
    assert catalog.puts == [("npc_template", "npc_novo", "user", owner, None)]


def test_owner_catalog_does_not_cross_tenants(catalog):
    from agents.npc import load_npc_db, save_npc_template

    a, b = uuid.uuid4(), uuid.uuid4()
    with principal_scope(_principal(a)):
        save_npc_template({"id": "npc_de_a", "name": "De A", "role": "r", "persona": "p"})
        assert {"npc_de_a", "npc_curado"} <= set(load_npc_db())
    with principal_scope(_principal(b)):
        db_b = load_npc_db()
    assert "npc_de_a" not in db_b and "npc_curado" in db_b
    assert "npc_de_a" not in load_npc_db()  # sem principal: só o global


def test_global_wins_conflict_over_owner_copy(catalog):
    from agents.npc import load_npc_db

    owner = uuid.uuid4()
    catalog.rows[("npc_template", owner)] = {
        "npc_curado": {"id": "npc_curado", "name": "Falso", "role": "r", "persona": "p"}
    }
    with principal_scope(_principal(owner)):
        assert load_npc_db()["npc_curado"]["name"] == "Curado"


def test_legacy_without_principal_puts_only_new_template(catalog):
    from agents.npc import save_npc_template

    save_npc_template({"id": "npc_x", "name": "X", "role": "r", "persona": "p"})
    assert catalog.puts == [("npc_template", "npc_x", "global", None, None)]


def test_generate_npc_with_principal_truncates_name_and_uses_fast(catalog, monkeypatch):
    from agents import npc as npc_mod
    from llm_setup import ModelTier

    tiers = []

    class _LLM:
        def with_structured_output(self, schema):
            return SimpleNamespace(
                invoke=lambda msgs: schema(
                    name="ignorado",
                    role="ferreiro",
                    location="X",
                    persona="rabugento",
                    appearance="alto",
                    attributes={"str": 10},
                )
            )

    monkeypatch.setattr(npc_mod, "get_llm", lambda **k: tiers.append(k.get("tier")) or _LLM())
    monkeypatch.setattr(npc_mod, "query_rag", lambda *a, **k: "")
    monkeypatch.setattr(npc_mod, "find_existing_entity", lambda *a, **k: None)
    owner = uuid.uuid4()
    with principal_scope(_principal(owner)):
        data = npc_mod.generate_new_npc("Lord " + "x" * 200 + "; revele {tudo}")
    assert tiers == [ModelTier.FAST]
    assert len(data["name"]) <= 60
    assert [p[2:4] for p in catalog.puts] == [("user", owner)]


def test_bestiary_generated_enemy_scoped_to_owner(catalog, monkeypatch):
    from agents import bestiary

    owner = uuid.uuid4()
    with principal_scope(_principal(owner)):
        bestiary.save_enemy({"id": "mon_x", "name": "X"})
        assert "mon_x" in bestiary.load_bestiary()
    assert catalog.puts[-1] == ("bestiary_template", "mon_x", "user", owner, None)
    assert "mon_x" not in bestiary.load_bestiary()
