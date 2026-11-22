"""SPEC-422: marcas do arquivista vivem em `state_archive.ArchiveMarks` e continuam canais do grafo."""

import ast
from pathlib import Path
from typing import get_type_hints

from langgraph.graph import END, START, StateGraph

import state_archive
from state import GameState
from state_archive import ArchiveMarks

MARKS = {"archive_due", "archive_low", "archive_record"}


def test_gamestate_herda_as_marcas():
    assert set(ArchiveMarks.__annotations__) == MARKS
    assert set(get_type_hints(GameState)) >= MARKS
    assert GameState.__required_keys__ >= MARKS


def test_marcas_chegam_do_no_anterior_ao_seguinte_no_grafo():
    seen: dict = {}
    sent = {"archive_due": True, "archive_low": 3, "archive_record": {"kind": "rest", "turn": 3}}

    def writer(state):
        return dict(sent)

    def reader(state):
        seen.update({k: state.get(k) for k in MARKS})
        return {}

    g = StateGraph(GameState)
    g.add_node("writer", writer)
    g.add_node("reader", reader)
    g.add_edge(START, "writer")
    g.add_edge("writer", "reader")
    g.add_edge("reader", END)
    g.compile().invoke({"game_id": "t"})
    assert seen == sent


def test_modulo_nao_importa_projeto():
    tree = ast.parse(Path(state_archive.__file__).read_text(encoding="utf-8"))
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert mods <= {"typing"}
