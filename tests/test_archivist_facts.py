"""Resiliência do MemoryUpdate: important_facts como dict não derruba o schema.

Achado dos smokes reais (specs #2/#3): o LLM às vezes devolve important_facts
como lista de dicts → 4 validation errors → fallback → perde memória do turno.
"""
from agents.archivist import MemoryUpdate


def test_facts_dict_role_content_vira_string():
    m = MemoryUpdate(new_summary="x", important_facts=[
        {"role": "user", "content": "O herói salvou a vila."},
        "Fato já em string.",
    ])
    assert m.important_facts == ["O herói salvou a vila.", "Fato já em string."]


def test_facts_dict_fato_type_vira_string():
    m = MemoryUpdate(new_summary="x", important_facts=[
        {"fato": "Grum é o taverneiro desconfiado.", "type": "npc"},
        {"fato": "Há um barril de óleo suspeito.", "type": "objeto"},
    ])
    assert m.important_facts == ["Grum é o taverneiro desconfiado.",
                                 "Há um barril de óleo suspeito."]


def test_facts_dict_desconhecido_e_descartado():
    m = MemoryUpdate(new_summary="x", important_facts=[{"a": 1, "b": "dois"}])
    assert m.important_facts == []


def test_facts_strings_intactas():
    m = MemoryUpdate(new_summary="x", important_facts=["um", "dois"])
    assert m.important_facts == ["um", "dois"]


def test_facts_vazio_ok():
    assert MemoryUpdate(new_summary="x", important_facts=[]).important_facts == []
