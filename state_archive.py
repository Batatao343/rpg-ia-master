"""Marcas transitórias do arquivista no estado do grafo (SPEC-422).

`GameState` herda deste TypedDict: o LangGraph lê as chaves herdadas como canais, então o
update do `storyteller` chega ao `archivist`. Este módulo não importa `state`.
"""

from typing import TypedDict


class ArchiveMarks(TypedDict):
    archive_due: bool  # flag transitória: evento relevante pede arquivamento (cadência)
    archive_low: int | None  # SPEC-318: turno cujo archive_due é de baixo valor (política lean)
    archive_record: dict | None  # SPEC-422: marca do turno (não persistida)
