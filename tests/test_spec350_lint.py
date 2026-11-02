"""SPEC-350 Etapa 1 — lint do catálogo de tramas (fixtures sintéticas)."""

from __future__ import annotations

import pytest

from services.plot_threads_lint import lint_plot_threads
from tests.spec350_helpers import good_data, good_refs


def _errs(data=None, refs=None):
    return lint_plot_threads(data if data is not None else good_data(), refs or good_refs())


def _has(errs, *needles):
    return any(all(n in e for n in needles) for e in errs)


def test_valid_fixture_passes():
    assert _errs() == []


def test_unknown_ids_are_errors():
    d = good_data()
    t = d["threads"][0]
    t["core"][0] = "npc_fantasma"
    t["locations"].append("loc_zzz")
    t["factions"].append("fac_zzz")
    t["rumor_ids"].append("rumor_zzz")
    t["secret_ids"].append("sec_zzz")
    t["portas"][2]["quest_hint"]["anchor_id"] = "rota_zzz"
    d["cast"]["npc_a"]["archetype"] = "arq_zzz"
    errs = _errs(d)
    for needle in (
        "npc_fantasma",
        "loc_zzz",
        "fac_zzz",
        "rumor_zzz",
        "sec_zzz",
        "rota_zzz",
        "arq_zzz",
    ):
        assert _has(errs, needle), needle


def test_thread_needs_three_doors_two_locations():
    d = good_data()
    d["threads"][0]["portas"].pop()
    assert _has(_errs(d), "porta(s)")
    d = good_data()
    for door in d["threads"][0]["portas"]:
        door["location_id"] = "loc_1"
    assert _has(_errs(d), "locais distintos")


def test_door_anchor_cannot_be_core_or_leader():
    d = good_data()
    d["threads"][0]["portas"][0]["anchor_npc_id"] = "npc_chefe"
    assert _has(_errs(d), "núcleo/líder")
    refs = good_refs()
    refs.leader_ids.add("npc_c")
    assert _has(_errs(good_data(), refs), "npc_c", "núcleo/líder")
    d = good_data()
    d["cast"]["npc_c"]["tier"] = "nucleo"
    assert _has(_errs(d), "tier")


@pytest.mark.parametrize(
    "term",
    [
        "escolhido",
        "profecia",
        "predestinado",
        "destinada",
        "sangue real",
        "herdeiro",
        "unico que pode",
        "so voce",
        "marcado pelo destino",
        "voce",
    ],
)
def test_chosen_one_vocabulary_rejected(term):
    d = good_data()
    d["threads"][0]["portas"][0]["hook_public"] = f"Alguém diz que {term} resolve a adega."
    assert _has(_errs(d), "escolhido")


def test_lengths_enforced():
    d = good_data()
    d["threads"][0]["pergunta"] = "x" * 161
    d["threads"][0]["resumo_publico"] = "x" * 301
    d["threads"][0]["portas"][0]["hook_public"] = "x" * 221
    s = d["cast"]["npc_a"]
    s["desejo"], s["medo"], s["segredo_topico"] = "x" * 91, "x" * 91, "x" * 61
    s["voz"] = {"registro": "x" * 61, "fala": "x" * 121}
    s["threads"][0]["papel"] = "x" * 121
    errs = _errs(d)
    for label in (
        "pergunta",
        "resumo_publico",
        "hook_public",
        "desejo",
        "medo",
        "segredo_topico",
        "registro",
        "fala",
        "papel",
    ):
        assert _has(errs, label, "máx"), label


def test_forbidden_lexicon_rejected():
    d = good_data()
    d["cast"]["npc_c"]["desejo"] = "virar boss da ponte inteira"
    assert _has(_errs(d), "termo proibido")


def test_lore_ref_keyword_in_range():
    d = good_data()
    assert _errs(d) == []
    d["threads"][0]["lore_keyword"] = "dragao"
    assert _has(_errs(d), "lore_keyword")
    d = good_data()
    d["threads"][0]["lore_refs"] = ["lore_nova/outro.txt:1-2"]
    assert _has(_errs(d), "arquivo inexistente")
    d = good_data()
    d["threads"][0]["lore_refs"] = ["sem-formato"]
    assert _has(_errs(d), "formato")


def test_lore_ref_reads_only_the_range(tmp_path, monkeypatch):
    f = tmp_path / "lore_nova"
    f.mkdir()
    (f / "teste.txt").write_text("a\nb\nbarril\nc\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    refs = good_refs()
    refs.lore_reader = None
    d = good_data()
    d["threads"][0]["lore_refs"] = ["lore_nova/teste.txt:3-3"]
    assert _errs(d, refs) == []
    d["threads"][0]["lore_refs"] = ["lore_nova/teste.txt:1-2"]
    assert _has(_errs(d, refs), "lore_keyword")


def test_secret_doc_required_and_hidden():
    d = good_data()
    d["cast"]["npc_a"]["segredo_doc_id"] = ""
    assert _has(_errs(d), "segredo_doc_id obrigatório")
    refs = good_refs()
    refs.secret_doc_visibility["npc_a_segredo"] = "public"
    assert _has(_errs(good_data(), refs), "não é oculto")
    d = good_data()
    d["cast"]["npc_a"]["segredo_doc_id"] = "doc_inexistente"
    assert _has(_errs(d), "inexistente")


def test_public_field_leaking_secret_rejected():
    # (a) assinatura de segredo da trama
    d = good_data()
    d["threads"][0]["resumo_publico"] = "Fala-se do testamento do antigo rei na adega."
    assert _has(_errs(d), "assinatura de segredo")
    # (b) LEAK_PHRASE da SPEC-348
    d = good_data()
    d["cast"]["npc_c"]["medo"] = "que descubram o herdeiro de Ostmar"
    assert _has(_errs(d), "LEAK_PHRASE")
    # (c) palavra exclusiva do doc de segredo usada na ficha pública
    d = good_data()
    d["cast"]["npc_a"]["segredo_topico"] = "a chave que entrega ao sargento"
    assert _has(_errs(d), "npc_a", "exclusiva do segredo")
    refs = good_refs()
    refs.secret_word_exceptions = {"chave", "entrega", "sargento"}
    assert not _has(_errs(d, refs), "exclusiva do segredo")
    # doc público novo vazando
    refs = good_refs()
    refs.public_doc_text["npc_a"] += " Guarda o testamento do antigo rei."
    assert _has(_errs(good_data(), refs), "doc público de npc_a")


def test_name_collision_with_curated_names():
    refs = good_refs()
    refs.name_owners = {"dalva torneira": {"npc_outro"}}
    assert _has(_errs(good_data(), refs), "colide")
    refs = good_refs()
    refs.npc_names["npc_a"] = ["Dalva Torneira", "Bors"]
    refs.name_owners = {"bors": {"npc_bors"}}
    assert _has(_errs(good_data(), refs), "'Bors'", "colide")
    refs = good_refs()
    refs.name_owners = {"dalva torneira": {"npc_a"}}
    assert _errs(good_data(), refs) == []


def test_duplicate_signature_rejected():
    d = good_data()
    d["cast"]["npc_b"]["threads"][0]["papel"] = "ajudante de taverna que rola barris"
    d["threads"][0]["portas"][1]["link_kind"] = "emprego"
    assert _has(_errs(d), "assinatura duplicada")


def test_jaccard_near_duplicate_rejected():
    d = good_data()
    a, c = d["cast"]["npc_a"], d["cast"]["npc_c"]
    for k in ("desejo", "medo", "segredo_topico"):
        c[k] = a[k]
    c["voz"]["fala"] = a["voz"]["fala"]
    assert _has(_errs(d), "quase iguais")


def test_same_role_radical_in_region_rejected():
    d = good_data()
    d["cast"]["npc_b"]["threads"][0]["papel"] = "ajudante de cozinha da guarda"
    assert _has(_errs(d), "mesmo radical")


def test_wave_coverage_and_dangling_thread():
    d = good_data()
    d["waves"][0]["status"] = "done"
    assert _has(_errs(d), "região nova_arcadia", "mín 5")
    d = good_data()
    d["cast"]["npc_a"]["threads"][0]["thread_id"] = "tr_inexistente"
    assert _has(_errs(d), "trama inexistente")


def test_door_anchor_must_be_thread_member():
    d = good_data()
    d["threads"][0]["borda"] = ["npc_a", "npc_b"]
    d["threads"][0]["portas"][2]["anchor_npc_id"] = "npc_chefe"
    d["cast"]["npc_chefe"] = d["cast"]["npc_c"]
    assert _has(_errs(d), "fora de core/borda") or _has(_errs(d), "núcleo/líder")
    d = good_data()
    d["threads"][0]["borda"] = ["npc_a", "npc_b"]  # npc_c é âncora mas não é membro
    assert _has(_errs(d), "npc_c", "fora de core/borda")
