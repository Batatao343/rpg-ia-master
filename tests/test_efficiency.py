"""
Otimização de chamadas/tokens de LLM (pente fino): cadência do arquivista, catálogo de combate
filtrado, dedup do librarian sem LLM. Offline/determinístico.
"""
import agents.archivist as arch
import agents.combat as combat
import agents.librarian as lib


# --- Archivist: cadência (evento relevante OU a cada 10 turnos) ---
def test_should_archive_on_event_flag():
    assert arch._should_archive({"archive_due": True}, turn=1) is True


def test_should_archive_every_n_turns():
    assert arch._should_archive({"archivist_last_run": 0}, turn=5) is False
    assert arch._should_archive({"archivist_last_run": 0}, turn=10) is True
    assert arch._should_archive({"archivist_last_run": 8}, turn=12) is False  # 4 < 10


def test_archive_node_skips_llm_when_not_due(monkeypatch):
    # turno trivial (sem flag, sem 10 turnos) → pula o LLM, devolve só o reset da flag
    called = {"n": 0}
    monkeypatch.setattr(arch, "get_llm", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    state = {"game_id": "g", "messages": [], "world": {"turn_count": 3}, "archivist_last_run": 0}
    out = arch.archive_node(state)
    assert out == {"archive_due": False}
    assert called["n"] == 0  # nenhum LLM instanciado


# --- Combate: catálogo só do necessário ---
def test_ability_catalog_for_filters_to_player():
    # sem habilidades conhecidas → só as universais (catálogo enxuto)
    cat = combat._ability_catalog_for({"known_abilities": []})
    assert "ataque_basico" in cat
    assert cat.count("\n") <= 1  # ~2 linhas (universais), não o dict inteiro


# --- Librarian: dedup sem gastar LLM quando claramente novo ---
def test_librarian_no_llm_when_clearly_new(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("LLM não deveria ser chamado para entidade claramente nova")
    monkeypatch.setattr(lib, "get_llm", _boom)
    # nenhum token em comum com os ids existentes → entidade nova, sem LLM
    assert lib.find_existing_entity("Dragão Vermelho Antigo", "Monster",
                                    ["npc_guarda_bran", "item_espada_gasta"]) is None


def test_librarian_exact_slug_match_no_llm(monkeypatch):
    monkeypatch.setattr(lib, "get_llm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sem LLM")))
    assert lib.find_existing_entity("npc varg", "NPC", ["npc_varg"]) == "npc_varg"


def test_librarian_token_overlap_builds_candidate(monkeypatch):
    # "Varg" deve virar candidato de "npc_varg_acougueiro" (token comum) → chama o LLM
    seen = {"called": False}

    class _FakeMatch:
        match_found = True
        existing_id = "npc_varg_acougueiro"

    class _FakeLLM:
        def with_structured_output(self, *_a, **_k): return self
        def invoke(self, *_a, **_k):
            seen["called"] = True
            return _FakeMatch()

    monkeypatch.setattr(lib, "get_llm", lambda *a, **k: _FakeLLM())
    out = lib.find_existing_entity("Varg", "NPC", ["npc_varg_acougueiro", "item_poção"])
    assert seen["called"] is True
    assert out == "npc_varg_acougueiro"
