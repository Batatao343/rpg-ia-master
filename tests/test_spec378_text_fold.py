"""SPEC-378 E1: ``services.text.fold`` contra o oraculo permanente das copias antigas.

Cada ``_legacy_*`` e a funcao original copiada verbatim antes da migracao; o site migrado
(``mod.fn``) e o ``fold(...)`` equivalente precisam concordar em todo o corpus.
"""

from __future__ import annotations

import importlib
import json
import random
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from services.text import fold

ADVERSARIAL = [
    "P\xe2ntano",
    "\xc1GUA  Viva ",
    "\xa0nbsp\xa0",
    "\u2003em-space",
    "\xdf",
    "\u1e9e",
    "\u03c2",
    "\ufb01",
    "\u0130stanbul",
    "\xa8",
    "\xb4",
    "\u216b",
    "\u2460",
    "\u2122",
    "\u2014",
    "\U0001f43a",
    "e\u0301",
    "\u0301",
    "a_b-c",
    "\t\n",
    "",
    "\u0345",
    "\u1fbc",
    "\uff9e",
    "\u0149",
    None,
    0,
    False,
    [],
    123,
]


def _data_strings() -> list[str]:
    out: set[str] = set()

    def walk(x):
        if isinstance(x, str):
            out.add(x[:300])
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(k)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for p in sorted(Path("data").rglob("*.json"))[:400]:
        try:
            walk(json.loads(p.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return sorted(out)


def _generated() -> list[str]:
    rnd = random.Random(378)
    alpha = list("abcdeéáâãçíóôúüÀÉÇ ABC_-  ") + [" ", "ß", "ﬁ", "™", "①", "ͅ", "ᾼ"]
    return ["".join(rnd.choice(alpha) for _ in range(rnd.randint(0, 20))) for _ in range(2000)]


CORPUS = ADVERSARIAL + _data_strings() + _generated()


def _legacy_party(s: str) -> str:
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def _legacy_services_combat_intents(text: object) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).lower()


def _legacy_services_companion_tags(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).lower()


def _legacy_inventory(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _legacy_services_reputation(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).strip().lower()


def _legacy_services_death_flow(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _legacy_services_leak_phrases(text: object) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _legacy_services_law(text: Any) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _legacy_services_memory_provenance(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def _legacy_services_npc_knowledge(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _legacy_services_faction_membership(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).strip().casefold()


def _legacy_services_plot_threads_lint(text: object) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()
    return " ".join(stripped.split())


def _legacy_services_shared_pool_models(text: object) -> str:
    """Nome dobrado: sem acento, casefold, espaços colapsados."""
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()
    return " ".join(stripped.split())


def _legacy_services_quest_log(value: object) -> str:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(plain.casefold().split())


def _legacy_services_world_validators(value: object) -> str:
    import unicodedata

    folded = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in folded if not unicodedata.combining(c)).casefold().split())


SITES = [
    ("party", "_fold", _legacy_party, {"case": "lower"}),
    ("services.combat_intents", "_fold", _legacy_services_combat_intents, {"case": "lower"}),
    ("services.companion_tags", "_fold", _legacy_services_companion_tags, {"case": "lower"}),
    ("inventory", "_fold", _legacy_inventory, {"case": "lower", "strip": True}),
    ("services.reputation", "_fold", _legacy_services_reputation, {"case": "lower", "strip": True}),
    ("services.death_flow", "_fold", _legacy_services_death_flow, {}),
    ("services.leak_phrases", "fold", _legacy_services_leak_phrases, {}),
    ("services.law", "_fold", _legacy_services_law, {}),
    ("services.memory_provenance", "_fold", _legacy_services_memory_provenance, {}),
    ("services.npc_knowledge", "_fold", _legacy_services_npc_knowledge, {}),
    ("services.faction_membership", "_fold", _legacy_services_faction_membership, {"strip": True}),
    ("services.plot_threads_lint", "fold", _legacy_services_plot_threads_lint, {"collapse": True}),
    (
        "services.shared_pool_models",
        "fold_name",
        _legacy_services_shared_pool_models,
        {"collapse": True},
    ),
    ("services.quest_log", "_fold_name", _legacy_services_quest_log, {"collapse": True}),
    ("services.world_validators", "_fold", _legacy_services_world_validators, {"collapse": True}),
]


@pytest.mark.parametrize(("mod", "fn", "legacy", "opts"), SITES, ids=[s[0] for s in SITES])
def test_migrated_site_matches_legacy_and_fold(mod, fn, legacy, opts):
    site = getattr(importlib.import_module(mod), fn)
    for x in CORPUS:
        want = legacy(x)
        assert site(x) == want, (mod, repr(x))
        assert fold(x, **opts) == want, (mod, repr(x))


def test_fold_defaults_and_none():
    assert fold(None) == "" and fold("Pântano") == "pantano"
    assert fold("  A  B ", strip=True, collapse=True) == "a b"
    assert unicodedata.normalize("NFC", fold("ÁGUA")) == "agua"
