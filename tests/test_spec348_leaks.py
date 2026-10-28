"""SPEC-348 — vazamentos de segredo da lore (R37-R42, R53-R54).

Frases comparadas em minúsculas e SEM acento contra o frontmatter + corpo de cada doc
público do Codex. O fato movido para fora do público tem de continuar existindo em
algum doc oculto (corrigir vazamento = mover, nunca apagar).
"""

from __future__ import annotations

import re

import pytest

from services.content_validator import NPC_SECRET_LABELS
from services.leak_phrases import leak_phrases
from services.secret_signatures import SECRET_SIGNATURES
from tests.spec348_helpers import (
    codex_docs,
    doc,
    docs_containing,
    fold,
    hidden_docs,
    load_json,
    public_docs,
)

LEAK_PHRASES: dict[str, list[str]] = leak_phrases()  # SPEC-350: dado em data/world/leak_phrases.json

# Fatos que precisam seguir existindo em doc oculto (R54): tuplas = termos no MESMO doc.
HIDDEN_FACTS: dict[str, list[tuple[str, ...]]] = {
    "vibora": [("magda", "lider da mao sombria")],
    "barril": [("testamento", "grum")],
    "corpos": [("silas vane", "corpos", "marcad")],
    "farol": [("farol", "rede carmesim", "suprim"), ("farol", "guardiao", "cem anos")],
    "arauto": [("aprendiz", "arauto")],
    "pacto": [("daruun", "armadura de malagor", "decimo ano")],
    "praga": [("vane", "caixa", "cepa atual")],
}

# Termos que o doc PÚBLICO de cada NPC/lugar novo não pode carregar (o segredo dele).
EXPANSION_SECRET_TERMS: dict[str, list[str]] = {
    "npc_ilsa": ["herdeir", "testamento", "colina cinza", "magda", "legitim"],
    "npc_bertil": ["daruun", "armadura", "masmorra", "valerius desc"],
    "npc_sennar_o_pregador_da_cicatriz": ["ress", "alistad", "rolos da legiao"],
    "npc_kahen": ["groth", "recibo", "vergonha"],
    "pr_solvhen": ["solvhara", "sonho coletivo"],
    "ma_forja_profunda": ["rei subterraneo"],
    "npc_volkar_o_guardiao_do_farol": ["rede carmesim", "anti-luz suprime"],
}


def _paragraph_hits(text: str, phrase: str) -> bool:
    return phrase in text


def test_public_codex_has_no_leak_phrases():
    offenders: dict[str, list[str]] = {}
    for d in public_docs():
        for group, phrases in LEAK_PHRASES.items():
            for ph in phrases:
                if ph in d["text"]:
                    offenders.setdefault(d["id"], []).append(f"{group}:{ph}")
        # armadura de Malagor + pacto no mesmo parágrafo
        for para in re.split(r"\n\s*\n", d["path"].read_text(encoding="utf-8")):
            f = fold(para)
            if "armadura de malagor" in f and "pacto" in f:
                offenders.setdefault(d["id"], []).append("pacto:armadura+pacto")
            if "daruun" in f and "pacto" in f and "valerius" in f:
                offenders.setdefault(d["id"], []).append("pacto:daruun+pacto")
    assert not offenders, offenders


@pytest.mark.parametrize("group", sorted(HIDDEN_FACTS))
def test_hidden_codex_keeps_each_leaked_fact(group):
    docs = hidden_docs()
    for terms in HIDDEN_FACTS[group]:
        found = [d["id"] for d in docs if all(fold(t) in d["text"] for t in terms)]
        assert found, (group, terms)


def test_seed_gists_and_bestiary_have_no_leak_phrases():
    seeds = load_json("data/world/rumor_seeds.json")["seeds"]
    bad = []
    for sid, seed in seeds.items():
        gist = fold(seed.get("gist", ""))
        for _group, phrases in LEAK_PHRASES.items():
            bad += [(sid, ph) for ph in phrases if ph in gist]
    for loc in load_json("data/world_map.json")["locations"]:
        seed = fold(loc.get("lore_seed", ""))
        for _group, phrases in LEAK_PHRASES.items():
            bad += [(loc["id"], ph) for ph in phrases if ph in seed]
    bestiary = load_json("data/bestiary.json")
    for eid, enemy in bestiary.items():
        desc = fold(enemy.get("description", ""))
        for _group, phrases in LEAK_PHRASES.items():
            bad += [(eid, ph) for ph in phrases if ph in desc]
    assert not bad, bad


# NPCs tocados por R37/R40/R41/R39: nenhum parágrafo com rótulo "de segredo" no público.
_TOUCHED_NPCS = [
    "npc_velha_magda",
    "npc_volkar_o_guardiao_do_farol",
    "npc_o_eco_do_aprendiz",
    "npc_doutor_silas_vane",
    "npc_grum",
    "npc_nehla_ouvido_de_aurora",
]
_EXTRA_SECRET_LABELS = {"papel real", "natureza", "o que sabe", "o que revela", "o carrinho"}


@pytest.mark.parametrize("npc_id", _TOUCHED_NPCS)
def test_npc_public_docs_have_no_secret_label_paragraphs(npc_id):
    labels = set(NPC_SECRET_LABELS) | _EXTRA_SECRET_LABELS
    bad = []
    for para in re.split(r"\n\s*\n", doc(npc_id)["body"]):
        first = para.strip().splitlines()[0] if para.strip() else ""
        if ":" in first and not first.lstrip().startswith("#"):
            label = fold(first.split(":", 1)[0])
            if label in labels:
                bad.append(label)
    assert not bad, (npc_id, bad)


def test_new_npc_public_docs_hide_their_secret_terms():
    ids = {d["id"] for d in codex_docs()}
    bad = []
    for doc_id, terms in EXPANSION_SECRET_TERMS.items():
        if doc_id not in ids:
            continue  # NPC/lugar ainda não existe nesta etapa
        d = doc(doc_id)
        assert d["visibility"] == "public", doc_id
        bad += [(doc_id, t) for t in terms if t in d["text"]]
    assert not bad, bad


def test_magda_public_card_says_only_the_cover():
    d = doc("npc_velha_magda")
    assert "vibora" not in d["text"]
    assert "identidade_secreta" not in d["text"]
    assert "espetinhos" in d["text"]
    assert docs_containing("velha magda", hidden_docs())


def test_testamento_doc_is_hidden():
    assert doc("art_testamento_real_no_barril")["visibility"] == "hidden"
