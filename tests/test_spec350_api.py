"""SPEC-350 Etapa 2 — API pura de services/plot_threads.py (catálogo sintético)."""

from __future__ import annotations

import ast
import json

import pytest

from services import plot_threads as pt
from tests.spec350_helpers import TID, good_data


def _use(tmp_path, monkeypatch, data=None, *, mode="on"):
    path = tmp_path / "plot_threads.json"
    path.write_text(json.dumps(data if data is not None else good_data()), encoding="utf-8")
    monkeypatch.setattr(pt, "CATALOG_PATH", str(path))
    monkeypatch.setenv("RPG_PLOT_THREADS", mode)
    pt.clear_cache()
    yield
    pt.clear_cache()


@pytest.fixture
def cat(tmp_path, monkeypatch):
    yield from _use(tmp_path, monkeypatch)


def test_catalog_invalid_returns_empty_and_logs(tmp_path, monkeypatch):
    calls = []
    import observability.telemetry as tel

    monkeypatch.setattr(tel, "log_event", lambda *a, **k: calls.append((a, k)))
    bad = tmp_path / "bad.json"
    bad.write_text("{ nao e json", encoding="utf-8")
    monkeypatch.setattr(pt, "CATALOG_PATH", str(bad))
    pt.clear_cache()
    assert pt.catalog().threads == ()
    assert calls and calls[0][0][:2] == ("plot", "catalog_invalid")
    monkeypatch.setattr(pt, "CATALOG_PATH", str(tmp_path / "nao_existe.json"))
    pt.clear_cache()
    assert pt.catalog().cast == {}
    # tipo inválido (link_kind) também cai em vazio
    d = good_data()
    d["threads"][0]["portas"][0]["link_kind"] = "inventado"
    bad.write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(pt, "CATALOG_PATH", str(bad))
    pt.clear_cache()
    assert pt.catalog().threads == ()
    pt.clear_cache()


def test_plot_doors_deterministic_order_and_postura_first(tmp_path, monkeypatch):
    d = good_data()
    second = json.loads(json.dumps(d["threads"][0]))
    second["id"] = "tr_na_alfa"
    for i, door in enumerate(second["portas"], start=1):
        door["id"] = f"tr_na_alfa__p{i}"
    second["postura_afinidade"] = []
    d["threads"].append(second)
    for _ in _use(tmp_path, monkeypatch, d):
        ids = [x.id for x in pt.plot_doors("nova_arcadia")]
        assert ids == sorted(ids)
        assert ids == [x.id for x in pt.plot_doors("nova_arcadia")]
        first = [x.id for x in pt.plot_doors("nova_arcadia", postura="Sangromante")]
        assert first[:3] == [f"{TID}__p1", f"{TID}__p2", f"{TID}__p3"]  # afinidade primeiro
        assert first[3:] == ["tr_na_alfa__p1", "tr_na_alfa__p2", "tr_na_alfa__p3"]
        assert pt.plot_doors("brekmar") == []


def test_plot_doors_off_returns_empty(tmp_path, monkeypatch):
    for _ in _use(tmp_path, monkeypatch, mode="off"):
        assert pt.plot_doors("nova_arcadia") == []


def test_plot_doors_filters_dead_captured_defected_anchor(cat):
    base = {"npcs": {}, "world_projection": {}}
    ids = lambda st: [x.anchor_npc_id for x in pt.plot_doors("nova_arcadia", state=st)]  # noqa: E731
    assert ids(base) == ["npc_a", "npc_b", "npc_c"]
    dead_row = {"npcs": {"npc_a": {"id": "npc_a", "status": "morto"}}}
    assert "npc_a" not in ids(dead_row)
    dead_proj = {"world_projection": {"entities": {"npc_b": {"alive": False}}}}
    assert "npc_b" not in ids(dead_proj)
    sim_dead = {"npc_sim": {"npcs": {"npc_c": {"dead": True}}}}
    assert "npc_c" not in ids(sim_dead)
    captured = {"npcs": {"npc_a": {"id": "npc_a", "status": "capturado"}}}
    assert "npc_a" not in ids(captured)
    sim_cap = {"npc_sim": {"npcs": {"npc_b": {"status": "capturado"}}}}
    assert "npc_b" not in ids(sim_cap)
    defected = {"world_projection": {"npc_affiliations": {"npc_c": "fac_rival"}}}
    assert "npc_c" not in ids(defected)
    stays = {"world_projection": {"npc_affiliations": {"npc_c": "fac_a"}}}
    assert "npc_c" in ids(stays)
    elsewhere = {"npcs": {"npc_a": {"id": "npc_a", "home_location_id": "bk_docas_velhas"}}}
    assert "npc_a" not in ids(elsewhere)
    assert ids(elsewhere) == ["npc_b", "npc_c"]


def test_plot_doors_never_exposes_secret_fields(cat):
    blob = json.dumps([x.model_dump() for x in pt.plot_doors("nova_arcadia")]).lower()
    for banned in ("segredo", "secret_ids", "sec_a", "npc_a_segredo"):
        assert banned not in blob
    assert "segredo" not in pt.public_thread_brief(TID).lower()


def test_sheet_for_row_by_id_ref_and_folded_alias(tmp_path, monkeypatch):
    d = good_data()
    base = d["cast"]["npc_a"]
    d["cast"] = {
        "npc_bors_martelo_partido": dict(base),
        "npc_velha_netta": dict(base),
    }
    for _ in _use(tmp_path, monkeypatch, d):
        by_id = pt.sheet_for_row({}, "qualquer", {"id": "npc_velha_netta"})
        assert by_id and by_id.npc_id == "npc_velha_netta"
        by_key = pt.sheet_for_row({}, "npc_bors_martelo_partido", {})
        assert by_key and by_key.npc_id == "npc_bors_martelo_partido"
        # id gerado por nome diverge do canônico: resolve pelo nome dobrado
        folded = pt.sheet_for_row({}, "velha_netta", {"id": "velha_netta", "name": "VELHA  netta"})
        assert folded and folded.npc_id == "npc_velha_netta"
        short = pt.sheet_for_row({}, "Bors", {"name": "Bors"})
        assert short and short.npc_id == "npc_bors_martelo_partido"
        assert pt.sheet_for_row({}, "Ninguém", {"name": "Ninguém"}) is None


def test_cast_npc_row_is_deterministic_and_secret_free(cat):
    a = pt.cast_npc_row("npc_a", game_id="g1", home_location_id="loc_1")
    b = pt.cast_npc_row("npc_a", game_id="g1", home_location_id="loc_1")
    assert a == b
    assert a["id"] == "npc_a" and a["plot_sheet_id"] == "npc_a"
    assert a["role"].startswith("ajudante")
    assert a["home_location_id"] == "loc_1" and a["hidden_traits"]
    blob = json.dumps(a, ensure_ascii=False).lower()
    for banned in ("segredo", "sargento procura", "chave da adega"):
        assert banned not in blob
    assert pt.cast_npc_row("npc_x", game_id="g1") == {}


def test_cast_npc_row_persona_comes_from_public_doc_only(cat, monkeypatch, tmp_path):
    pub = tmp_path / "pub.md"
    pub.write_text("---\nid: npc_a\n---\n", encoding="utf-8")
    from services import codex_loader

    def fake_parse(path):
        return {"id": "npc_a", "visibility": "public"}, "# Dalva\n\nAjudante da adega.\n\nOutro."

    monkeypatch.setattr(codex_loader, "parse_codex_file", fake_parse)
    monkeypatch.setattr(pt, "_public_docs", lambda: {"npc_a": str(pub)})
    assert pt.cast_npc_row("npc_a", game_id="g")["persona"] == "Ajudante da adega."


def test_public_thread_brief_has_no_secret(cat):
    brief = pt.public_thread_brief(TID)
    assert "A trama de teste" in brief and "adega foi revistada" in brief
    assert "Quem fica com os barris" in brief
    assert "npc_chefe" not in brief and "sec_a" not in brief
    assert pt.public_thread_brief("tr_nope") == ""


def test_region_cast_and_stake_line(cat):
    assert pt.region_cast("nova_arcadia") == ["npc_a", "npc_b", "npc_c"]
    assert pt.region_cast("brekmar") == []
    assert pt.stake_line(pt.cast_sheet("npc_a")).startswith(
        "O que está em jogo para você: ajudante"
    )


def test_no_llm_no_io_in_module():
    for mod in ("services/plot_threads.py", "services/plot_threads_lint.py"):
        with open(mod, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & {"get_llm", "query_rag", "add_memory_to_session", "invoke"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                modes += [k.value.value for k in node.keywords if k.arg == "mode"]
                assert not any(m in ("w", "a", "wb", "x") for m in modes), mod


def test_sheet_for_row_name_match_requires_thread_region(tmp_path, monkeypatch):
    d = good_data()
    base = d["cast"]["npc_a"]
    d["cast"] = {
        "npc_bors_martelo_partido": dict(base),
        "npc_tr_bento_juros": dict(base),
    }
    for _ in _use(tmp_path, monkeypatch, d):
        # homônimo inventado em outra região não herda a ficha de Nova Arcádia
        assert (
            pt.sheet_for_row({}, "Bento", {"name": "Bento", "home_location_id": "sk_porto"}) is None
        )
        row = {"name": "Bento", "home_location_id": "sk_salao_do_jarl"}
        assert pt.sheet_for_row({}, "Bento", row) is None
        assert (
            pt.sheet_for_row({}, "Bento", {"name": "Bento", "home_location_id": "na_anel_ferro"})
            is not None
        )
        bors = pt.sheet_for_row({}, "Bors", {"name": "Bors", "home_location_id": "na_anel_ferro"})
        assert bors and bors.npc_id == "npc_bors_martelo_partido"
        # sem local: aceita; id canônico de outro NPC do grafo: recusa
        assert pt.sheet_for_row({}, "Bento", {"name": "Bento"}) is not None
        other = {"id": "npc_grum", "name": "Bento", "home_location_id": "na_anel_ferro"}
        assert pt.sheet_for_row({}, "Bento", other) is None
