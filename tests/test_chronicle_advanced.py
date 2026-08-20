from copy import deepcopy

from langchain_core.messages import AIMessage

from services.chronicle import append_entry, ensure_chronicle_ids, open_chapter
from services.chronicle_compression import chapter_source_hash, compress_chapter, should_compress


def test_ids_estaveis_e_raw_intocado_na_compressao():
    chronicle = open_chapter([], title="Arco", turn=1, location="Porto")
    chronicle = append_entry(chronicle, text="O selo caiu.", turn=2, kind="milestone", event_id="e1")
    normalized = ensure_chronicle_ids(chronicle, game_id="g")
    assert ensure_chronicle_ids(normalized, game_id="g") == normalized
    raw = deepcopy(normalized)
    class Fallback:
        def with_structured_output(self, _schema): return self
        def invoke(self, _messages): return AIMessage(content="erro")
    digest = compress_chapter(normalized[0], llm=Fallback())
    assert normalized == raw
    assert digest["status"] == "extractive_fallback"
    assert digest["milestones"][0]["text"] == "O selo caiu."
    assert digest["milestones"][0]["event_id"] == "e1"


def test_trigger_20_descobertas_e_hash_muda_sem_reescrever():
    chapter = open_chapter([], title="Longo", turn=0, location="")[0]
    for turn in range(20):
        chapter = append_entry([chapter], text=f"Entrada {turn}", turn=turn, kind="prose")[-1]
    assert should_compress(chapter)
    before = chapter_source_hash(chapter)
    chapter["digest"] = {"covered_entry_count": 20}
    assert not should_compress(chapter)
    assert chapter_source_hash(chapter) == before
