"""SPEC-306 - script de revisão (formato canônico, página, approve)."""

from __future__ import annotations

import copy

from scripts import npc_seed_review as rv


def _open_bytes(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def test_dump_roundtrip_is_byte_identical():
    text = _open_bytes(rv.SEED_TABLES_PATH)
    assert "\r" not in text
    assert rv.dump_tables(rv.load_tables()) == text


def test_classify_precedence():
    assert rv.classify({"id": "x"}) == "universal"
    assert rv.classify({"regions": ["brekmar"]}) == "regional"
    assert rv.classify({"regions": ["brekmar"], "races": ["race_osshari"]}) == "raca"
    assert (
        rv.classify(
            {"regions": ["brekmar"], "races": ["race_osshari"], "factions": ["poder_kahen"]}
        )
        == "facao"
    )


def test_regional_matrix_counts():
    tables = {
        "professions": [
            {"id": "a", "label": "x", "regions": ["brekmar", "skallgard"]},
            {"id": "b", "label": "y", "regions": ["brekmar"], "factions": ["poder_kahen"]},
            {"id": "c", "label": "z", "regions": ["brekmar"], "races": ["race_osshari"]},
        ]
    }
    matrix = rv.regional_matrix(tables, ["brekmar", "skallgard", "ophidia"])
    assert matrix["brekmar"]["professions"] == 2
    assert matrix["skallgard"]["professions"] == 1
    assert matrix["ophidia"]["professions"] == 0
    assert matrix["brekmar"]["desires"] == 0


def test_render_review_lists_only_pending_and_is_deterministic():
    tables = rv.load_tables()
    tables = copy.deepcopy(tables)
    for table in rv.TABLE_KEYS:
        for row in tables[table]:
            row.pop("review", None)
    first = tables["secrets"][-1]
    first["review"] = "dono"
    first["regions"] = ["brekmar"]
    first["races"] = ["race_osshari"]
    page = rv.render_review(tables)
    assert page == rv.render_review(tables)
    pending_section = page.split("## secrets - pendentes", 1)[1].split("## ", 1)[0]
    assert f"`{first['id']}`" in pending_section
    assert "Brekmar" in pending_section and "Osshari" in pending_section
    other = tables["secrets"][0]["id"]
    assert f"`{other}`" not in pending_section
    assert "_Nenhuma linha pendente._" in page.split("## professions - pendentes", 1)[1]


def test_review_page_is_fresh():
    assert rv.render_review(rv.load_tables()) == _open_bytes(rv.REVIEW_PATH)


def test_approve_removes_review_only_for_ids():
    tables = {
        "professions": [
            {"id": "a", "label": "um", "review": "dono", "source": "s"},
            {"id": "b", "label": "dois", "review": "dono"},
        ],
        "desires": [{"id": "c", "label": "tres", "review": "dono"}],
    }
    only = rv.approve(tables, {"a"})
    assert "review" not in only["professions"][0]
    assert only["professions"][0]["source"] == "s"
    assert only["professions"][1]["review"] == "dono"
    assert only["desires"][0]["review"] == "dono"
    assert tables["professions"][0]["review"] == "dono"  # entrada intacta
    everything = rv.approve(tables, None)
    assert all("review" not in r for t in ("professions", "desires") for r in everything[t])
