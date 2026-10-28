"""SPEC-348 — clusters da timeline e âncoras `arquivo.txt:N` dos dados de mundo (R3, R4, R5)."""

from __future__ import annotations

import re

from scripts import lore_reanchor as lr
from scripts.migrate_lore_nova import _TIMELINE_HIDDEN_CLUSTERS, parse_timeline
from tests.spec348_helpers import ROOT, fold, load_json, lore_lines


def test_timeline_cluster_phrases_unique():
    """R3: cada frase-âncora de cluster aparece em exatamente um parágrafo da timeline."""
    text = fold((ROOT / "lore_nova/timeline_completa.txt").read_text(encoding="utf-8"))
    paragraphs = [p for p in re.split(r"\n\s*\n|\n-{3,}\n", text) if p.strip()]
    for start, end in _TIMELINE_HIDDEN_CLUSTERS:
        for phrase in (start, end):
            hits = [i for i, p in enumerate(paragraphs) if phrase in p]
            assert len(hits) == 1, (phrase, len(hits))


def test_timeline_hidden_clusters_actually_hide_paragraphs():
    sections = parse_timeline(str(ROOT / "lore_nova/timeline_completa.txt"))
    hidden = " ".join(fold(s.body) for s in sections if s.visibility == "hidden")
    public = " ".join(fold(s.body) for s in sections if s.visibility == "public")
    for start, end in _TIMELINE_HIDDEN_CLUSTERS:
        assert start in hidden and start not in public, start
        assert end in hidden and end not in public, end


def test_all_lore_anchors_resolve_to_nonempty_line():
    """R4: toda âncora dos 7 arquivos de dados aponta para linha não vazia."""
    assert lr.check() == []


def test_anchor_keyword_in_line_where_declared():
    """R4: quando a entrada declara `lore_keyword`, a palavra está nas linhas âncora."""
    pairs = []
    for rel in ("data/world/lore_quests.json", "data/world/world_quests.json"):
        raw = load_json(rel)

        def walk(node):
            if isinstance(node, dict):
                if "lore_keyword" in node:
                    refs = node.get("lore_refs") or [node.get("lore_ref")]
                    pairs.append((rel, node["lore_keyword"], [r for r in refs if r]))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(raw)
    assert pairs
    for rel, keyword, refs in pairs:
        chunks = []
        for ref in refs:
            m = lr.ANCHOR_RE.search(ref)
            a, b = int(m.group("a")), int(m.group("b") or m.group("a"))
            lines = lore_lines(m.group("file"))
            chunks.append(" ".join(lines[a - 1 : b]))
        assert fold(keyword) in fold(" ".join(chunks)), (rel, keyword, refs)


def test_line_map_follows_inserted_and_edited_lines():
    old = ["a", "b", "c", "d texto longo original aqui"]
    new = ["a", "NOVA", "b", "c", "d texto longo original alterado aqui"]
    m = lr.build_line_map(old, new)
    assert m[1] == (1, lr.IGUAL)
    assert m[2] == (3, lr.IGUAL)
    assert m[3] == (4, lr.IGUAL)
    assert m[4][0] == 5 and m[4][1] == lr.ALTERADA


def test_line_map_flags_removed_line():
    m = lr.build_line_map(["x", "linha completamente diferente"], ["x", "zzz qqq www"])
    assert m[2][0] is None and m[2][1] == lr.REMOVIDA
