import json
from pathlib import Path

from services.chronicle import ensure_chronicle_ids
from services.chronicle_search import ChronicleCandidate, search_chronicle


def _chronicle():
    return [
        {"title": "Porto", "started_turn": 1, "location": "Cais", "entries": [
            {"text": "Enganamos o mercador da doca.", "turn": 3, "kind": "prose"},
        ]},
        {"title": "Bosque", "started_turn": 5, "location": "Mata", "entries": [
            {"text": "Salvamos a curandeira.", "turn": 7, "kind": "milestone", "event_id": "e7"},
        ]},
    ]


def test_busca_lexical_rastreavel_e_limitada():
    result = search_chronicle(_chronicle(), "mercador doca", top_k=5)
    assert result["mode"] == "lexical_fallback"
    assert result["hits"][0]["chapter_title"] == "Porto"
    assert result["hits"][0]["entry_ids"]


def test_rrf_semantico_recupera_parafrase():
    base = search_chronicle(_chronicle(), "curandeira")
    document_id = base["hits"][0]["entry_ids"][0]
    semantic = [ChronicleCandidate(document_id, base["hits"][0]["chapter_id"], "entry", .95)]
    result = search_chronicle(_chronicle(), "médica resgatada", semantic=semantic)
    assert result["mode"] == "hybrid" and result["hits"][0]["chapter_title"] == "Bosque"


def test_corpus_ptbr_hibrido_supera_lexical_e_atinge_recall_85():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "chronicle_search_ptbr.json")
        .read_text(encoding="utf-8")
    )
    chronicle = ensure_chronicle_ids(fixture["chapters"], game_id="recall-ptbr")
    expected_ids = [
        chronicle[row["chapter"]]["entries"][row["entry"]]["entry_id"]
        for row in fixture["queries"]
    ]
    lexical_hits = 0
    hybrid_hits = 0
    for row, expected_id in zip(fixture["queries"], expected_ids, strict=True):
        lexical = search_chronicle(chronicle, row["query"], top_k=5)
        lexical_ids = {
            entry_id for hit in lexical["hits"] for entry_id in hit["entry_ids"]
        }
        lexical_hits += expected_id in lexical_ids

        # O adapter vetorial é testado separadamente; aqui o corpus fixa seu
        # ranking-oráculo e mede o contrato de fusão/rastreabilidade sem rede.
        chapter = chronicle[row["chapter"]]
        semantic = [
            ChronicleCandidate(expected_id, chapter["chapter_id"], "entry", 1.0),
        ]
        hybrid = search_chronicle(
            chronicle, row["query"], top_k=5, semantic=semantic,
        )
        hybrid_ids = {
            entry_id for hit in hybrid["hits"] for entry_id in hit["entry_ids"]
        }
        hybrid_hits += expected_id in hybrid_ids

    total = len(fixture["queries"])
    assert hybrid_hits / total >= 0.85
    assert hybrid_hits > lexical_hits
