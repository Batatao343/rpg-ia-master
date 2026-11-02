"""playtest/opening_checks.py — oráculo E1–E7 da abertura (SPEC-351 R23).

CONGELADO na Etapa 1 da SPEC-351, antes do código de produto: quem otimiza a
abertura não altera limiares, listas nem regras daqui sem atualizar a spec com
aprovação do dono (integridade de eval, AGENTS.md). Determinístico, zero LLM,
sem I/O de rede. As consultas ao mundo (grafo, líderes, Codex oculto) usam as
fontes reais por padrão e podem ser injetadas nos testes.

Entradas são dicts simples:
- `scenario`: prologue, opening_scene_brief, beats, climax, seeking, thread_refs,
  plot_npc_id, personal_npc (dict|None) — o `StartScenario.model_dump()`;
- `menu`: {"region_id", "doors": [{"door_id","name",...}], "npcs": [{"entity_id",...}]}.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache

# --- constantes congeladas -------------------------------------------------- #
SHINGLE_WORDS = 6
SEEKING_MAX_CHARS = 200
NAME_TOKEN_MIN = 3
EDGE_FORBIDDEN = (
    "escolhid",
    "profecia",
    "destinad",
    "unico capaz",
    "salvar valoria",
    "herdeiro secreto",
)
_CONTENT_STOPWORDS = frozenset(
    "para como mais pelo pela pelos pelas esse essa este esta isso isto aqui "
    "onde quem qual quais coisa algo alguem ninguem muito pouco sobre entre "
    "desde ainda depois antes porque quando sempre nunca nada tudo cada outro "
    "outra seus suas dele dela deles delas".split()
)
_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class CheckResult:
    code: str
    ok: bool
    detail: str = ""


# --- utilidades ------------------------------------------------------------- #
def fold(text: object) -> str:
    """Minúsculas, sem acento (NFKD), espaços normalizados."""
    import unicodedata

    raw = unicodedata.normalize("NFKD", str(text or "").lower())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split())


def _words(text: object) -> list[str]:
    return _WORD.findall(fold(text))


def word_shingles(text: object, size: int = SHINGLE_WORDS) -> set[str]:
    words = _words(text)
    if len(words) < size:
        return set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def _scenario_text(scenario: dict) -> str:
    parts = [
        scenario.get("prologue"),
        scenario.get("opening_scene_brief"),
        scenario.get("climax"),
        *(scenario.get("beats") or []),
    ]
    return " ".join(str(p or "") for p in parts)


def _public_text(scenario: dict) -> str:
    """Tudo que o cliente vê: cena + NPCs (inclui a camada pública do pessoal)."""
    parts = [_scenario_text(scenario), scenario.get("seeking"), scenario.get("plot_npc_hook")]
    personal = scenario.get("personal_npc") or {}
    parts += [
        personal.get(k)
        for k in ("name", "role_public", "persona_public", "appearance", "legend", "bond")
    ]
    for npc in scenario.get("seed_npcs") or []:
        parts += [npc.get(k) for k in ("name", "role", "persona")]
    return " ".join(str(p or "") for p in parts)


# --- E1 --------------------------------------------------------------------- #
def check_thread_linked(scenario: dict, menu: dict) -> CheckResult:
    refs = [str(r) for r in (scenario.get("thread_refs") or [])]
    doors = {str(d.get("door_id")): d for d in (menu.get("doors") or [])}
    if not refs:
        return CheckResult("E1", False, "thread_refs vazio")
    outside = [r for r in refs if r not in doors]
    if outside:
        return CheckResult("E1", False, f"thread_refs fora do menu: {outside}")
    text = fold(_scenario_text(scenario))
    for ref in refs:
        name = fold(doors[ref].get("name"))
        if name and name in text:
            return CheckResult("E1", True)
    return CheckResult("E1", False, "nenhum nome de porta aparece no texto da cena")


# --- E2 --------------------------------------------------------------------- #
def _default_graph_entity(ref: str) -> dict | None:
    from services import npc_world

    return npc_world.graph_entity(ref)


def _default_home(ref: str) -> str:
    from services import npc_world

    return npc_world.home_of({}, ref)


def _default_region_of(location_id: str) -> str:
    from services import world_pressures

    return world_pressures.region_of(location_id)


def _default_leaders() -> Iterable[str]:
    from services import npc_world

    return npc_world.leaders().keys()


def _default_secret_ids() -> set[str]:
    from services.secret_signatures import SECRET_ENTITY_IDS

    return {i for ids in SECRET_ENTITY_IDS.values() for i in ids}


def check_plot_npc_valid(
    scenario: dict,
    menu: dict,
    *,
    graph_entity: Callable[[str], dict | None] = _default_graph_entity,
    home_of: Callable[[str], str] = _default_home,
    region_of: Callable[[str], str] = _default_region_of,
    leaders: Iterable[str] | None = None,
    secret_ids: Iterable[str] | None = None,
    dead_ids: Iterable[str] = (),
) -> CheckResult:
    npc_id = str(scenario.get("plot_npc_id") or "")
    if not npc_id:
        if not (menu.get("npcs") or []):
            return CheckResult("E2", True, "menu sem NPC: nada a validar")
        return CheckResult("E2", False, "plot_npc_id vazio")
    ent = graph_entity(npc_id)
    if not ent:
        return CheckResult("E2", False, "NPC da trama não existe no grafo")
    if str(ent.get("visibility", "public")) != "public":
        return CheckResult("E2", False, "NPC da trama não é public")
    region = str(menu.get("region_id") or "")
    if region_of(home_of(npc_id)) != region:
        return CheckResult("E2", False, "casa do NPC fora da região de início")
    if npc_id in set(dead_ids):
        return CheckResult("E2", False, "NPC da trama está morto")
    lead = set(_default_leaders() if leaders is None else leaders)
    if npc_id in lead:
        return CheckResult("E2", False, "NPC da trama é líder")
    secrets = set(_default_secret_ids() if secret_ids is None else secret_ids)
    if npc_id in secrets:
        return CheckResult("E2", False, "NPC da trama está em secret_entities")
    return CheckResult("E2", True)


# --- E3 --------------------------------------------------------------------- #
def _allowed_keys() -> frozenset[str]:
    from services.shared_pool_models import DOCUMENT_ALLOWLIST, PoolNamespace

    return DOCUMENT_ALLOWLIST[PoolNamespace.NPC]


def _doc_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _doc_strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _doc_strings(v)]
    return []


def check_personal_npc_private(
    entry_or_doc: object,
    *,
    character_name: str,
    backstory: str = "",
    seeking: str = "",
    validate: bool = False,
    owner_values: Iterable[str] = (),
) -> CheckResult:
    """`entry_or_doc`: documento (dict) ou `SharedPoolEntry`. Com `validate=True` exige
    também `run_validators(entry) == []` (caso limpo; só para `SharedPoolEntry`)."""
    entry = None if isinstance(entry_or_doc, dict) else entry_or_doc
    doc = entry_or_doc if isinstance(entry_or_doc, dict) else getattr(entry, "document", {})
    extra = sorted(set(doc) - _allowed_keys())
    if extra:
        return CheckResult("E3", False, f"chaves fora da allowlist: {extra}")
    texts = _doc_strings(doc)
    if entry is not None:
        texts += [str(getattr(entry, "name", "")), str(getattr(entry, "legend", ""))]
    blob = " ".join(texts)
    doc_words = set(_words(blob))
    for token in _words(character_name):
        if len(token) >= NAME_TOKEN_MIN and token in doc_words:
            return CheckResult("E3", False, "token do nome do personagem no documento")
    doc_shingles = word_shingles(blob)
    for label, source in (("backstory", backstory), ("seeking", seeking)):
        if doc_shingles & word_shingles(source):
            return CheckResult("E3", False, f"shingle de {label} no documento")
    if validate:
        if entry is None:
            return CheckResult("E3", False, "validate=True exige SharedPoolEntry")
        from services.shared_pool_validators import run_validators

        findings = run_validators(entry, owner_values=list(owner_values) or [character_name])
        if findings:
            return CheckResult("E3", False, f"validadores: {[f.code for f in findings]}")
    return CheckResult("E3", True)


# --- E4 --------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def hidden_codex_shingles() -> frozenset[str]:
    """Shingles de 6 palavras dos docs `hidden`/`secret` do Codex (corpo + nome)."""
    import yaml

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "data", "codex")
    out: set[str] = set()
    for dirpath, _dirs, files in os.walk(root):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(dirpath, fname), encoding="utf-8") as fh:
                raw = fh.read()
            parts = raw.split("---", 2)
            if not raw.startswith("---") or len(parts) < 3:
                continue
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                continue
            if str(meta.get("visibility", "public")) in ("hidden", "secret"):
                out |= word_shingles(parts[2])
    return frozenset(out)


def check_no_hidden_leak(
    scenario: dict,
    *,
    hidden_shingles: Iterable[str] | None = None,
    state: dict | None = None,
) -> CheckResult:
    text = _public_text(scenario)
    hidden = frozenset(hidden_codex_shingles() if hidden_shingles is None else hidden_shingles)
    common = word_shingles(text) & hidden
    if common:
        return CheckResult("E4", False, f"shingle de doc hidden/secret: {sorted(common)[0]!r}")
    from services.secret_signatures import find_unrevealed

    hit = find_unrevealed(text, state or {})
    if hit:
        return CheckResult("E4", False, f"assinatura de segredo: {hit[0]}")
    from services.faction_gate import beat_leaks

    if any(beat_leaks(state or {}, t) for t in (scenario.get("beats") or [])) or beat_leaks(
        state or {}, str(scenario.get("climax") or "")
    ):
        return CheckResult("E4", False, "faction_gate.beat_leaks")
    return CheckResult("E4", True)


# --- E5 --------------------------------------------------------------------- #
def check_seeking_present(scenario: dict) -> CheckResult:
    seeking = str(scenario.get("seeking") or "").strip()
    if not 1 <= len(seeking) <= SEEKING_MAX_CHARS:
        return CheckResult("E5", False, f"seeking com {len(seeking)} caracteres")
    prologue = set(_words(scenario.get("prologue")))
    content = [w for w in _words(seeking) if len(w) >= 4 and w not in _CONTENT_STOPWORDS]
    if any(w in prologue for w in content):
        return CheckResult("E5", True)
    return CheckResult("E5", False, "nenhuma palavra de conteúdo de seeking no prólogo")


# --- E6 --------------------------------------------------------------------- #
def check_starts_at_edge(scenario: dict) -> CheckResult:
    text = fold(" ".join([str(scenario.get("prologue") or ""), *(scenario.get("beats") or [])]))
    for term in EDGE_FORBIDDEN:
        if term in text:
            return CheckResult("E6", False, f"termo proibido: {term}")
    return CheckResult("E6", True)


# --- E7 --------------------------------------------------------------------- #
def check_npc_cardinality(scenario: dict, menu: dict, *, template: bool = False) -> CheckResult:
    personal = 1 if scenario.get("personal_npc") else 0
    plot = 1 if scenario.get("plot_npc_id") else 0
    want_personal = 0 if template else 1
    want_plot = 1 if (menu.get("npcs") or []) else 0
    if personal != want_personal or plot != want_plot:
        return CheckResult(
            "E7",
            False,
            f"pessoal={personal} (esperado {want_personal}), trama={plot} (esperado {want_plot})",
        )
    return CheckResult("E7", True)


# --- agregado --------------------------------------------------------------- #
def run_all(
    scenario: dict,
    menu: dict,
    *,
    character_name: str,
    backstory: str = "",
    template: bool = False,
    personal_doc: object | None = None,
    **e2_kwargs: object,
) -> list[CheckResult]:
    """E1–E7. E3 só roda se houver documento do pool (`personal_doc`); senão é
    omitido (o template não tem NPC pessoal)."""
    results = [
        check_thread_linked(scenario, menu),
        check_plot_npc_valid(scenario, menu, **e2_kwargs),  # type: ignore[arg-type]
    ]
    if personal_doc is not None:
        results.append(
            check_personal_npc_private(
                personal_doc,
                character_name=character_name,
                backstory=backstory,
                seeking=str(scenario.get("seeking") or ""),
            )
        )
    results += [
        check_no_hidden_leak(scenario),
        check_seeking_present(scenario),
        check_starts_at_edge(scenario),
        check_npc_cardinality(scenario, menu, template=template),
    ]
    return results
