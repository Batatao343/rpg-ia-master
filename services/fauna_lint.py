"""SPEC-360 R4: lint deterministico do bloco de fauna (`data/bestiario/fauna/<regiao>.yaml`).

Fonte unica das regras E1-E18 (§3.4; E17/E18 = SPEC-370) e da cobertura R2. `lint_region(doc, refs)` e puro
(recebe as referencias prontas); `load_refs(regiao)` monta as referencias dos dados reais.
Chamado por `content_validator.validate_fauna()` e por `scripts/fauna/lint.py --regiao`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.encounter_manifest import _fold, _singular

ROOT = Path(__file__).resolve().parent.parent
FAUNA_DIR = ROOT / "data" / "bestiario" / "fauna"
FICHAS_DIR = ROOT / "data" / "bestiario" / "fichas"
LEXICO = ROOT / "data" / "bestiario" / "_lexico_sinais.txt"
CURADORIA = ROOT / "data" / "bestiario" / "curadoria_legado.yaml"

FICHA_STATUS = ("nova", "reinventada", "adotada")
ANTECEDENCIA = ("cedo", "imediato")
EFEITOS = ("mais", "menos", "some")
PRESSOES = ("guerra", "fome", "praga", "abismo")
REVISAO = ("pendente", "aprovada", "rejeitada")
FONTES = ("ficha", "legado")
SIGN_KINDS = ("rastro", "resto", "som", "cheiro", "marca")
TEXT_KINDS = (*SIGN_KINDS, "aproximacao", "rumor")
MAX_SIGN = 160
MAX_RUMOR = 120
MIN_SIGNS = 3
MAX_IMEDIATO = 0.30
MAX_IMEDIATO_HUB = 2  # E18 (SPEC-370 R6)
MIN_TROFICA = 0.60
MAX_JACCARD = 0.5
MIN_NAME_TOKEN = 4

ENTRY_KEYS = {
    "fonte",
    "ecologia",
    "sinais",
    "contra_jogo",
    "tramas",
    "autor",
    "revisor_fauna",
    "revisao",
}
ENTRY_REQUIRED = {"fonte", "ecologia", "sinais", "contra_jogo", "autor", "revisao"}
ECO_KEYS = {
    "horario",
    "estacoes",
    "territorio",
    "permanencia",
    "presas",
    "suprime",
    "foge_de",
    "reage",
}
SINAIS_KEYS = {"antecedencia", *TEXT_KINDS}
_STOP = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "e",
    "em", "na", "no", "nas", "nos", "que", "se", "com", "por", "para", "pela", "pelo", "como",
    "ao", "aos", "mais", "sem", "ja", "nao", "foi", "ha", "sua", "seu", "suas", "seus", "ela",
    "ele", "elas", "eles", "ou", "num", "numa", "entre", "ate", "so", "isso", "esta", "este",
}  # fmt: skip


@dataclass(frozen=True)
class Refs:
    region: str
    fichas: dict[str, dict] = field(default_factory=dict)
    familias: dict[str, str] = field(default_factory=dict)
    legacy: frozenset[str] = frozenset()
    bestiary: dict[str, dict] = field(default_factory=dict)  # id -> {name, regions, boss}
    region_nodes: frozenset[str] = frozenset()
    periods: tuple[str, ...] = ()
    seasons: tuple[str, ...] = ()
    weather_states: frozenset[str] = frozenset()
    adjacency: frozenset[str] = frozenset()
    vagos: tuple[str, ...] = ()
    leak_phrases: tuple[str, ...] = ()
    other_presas: dict[str, tuple[str, ...]] = field(default_factory=dict)
    hub: str = ""  # E18: no raiz com o id da regiao (chegada mais usada), "" se nao existir


# --------------------------------------------------------------------------- texto


def fold(text: Any) -> str:
    return _fold(str(text or ""))


def word_tokens(text: Any) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", fold(text)) if t]


def name_tokens(*texts: Any) -> set[str]:
    """Tokens (>= 4 letras, sem acento, singularizados) que um sinal nao pode conter (R5)."""
    out: set[str] = set()
    for text in texts:
        for t in word_tokens(str(text or "").replace("_", " ")):
            if len(t) >= MIN_NAME_TOKEN and not t.isdigit():
                out.add(_singular(t))
    return out


def leaked_tokens(text: Any, forbidden: set[str]) -> list[str]:
    return sorted({_singular(t) for t in word_tokens(text)} & forbidden)


def _content_tokens(text: Any) -> set[str]:
    return {_singular(t) for t in word_tokens(text) if t not in _STOP and len(t) >= 3}


def jaccard(a: Any, b: Any) -> float:
    ta, tb = _content_tokens(a), _content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def forbidden_for(cid: str, refs: Refs) -> set[str]:
    ficha = refs.fichas.get(cid) or {}
    name = ficha.get("nome") or (refs.bestiary.get(cid) or {}).get("name") or ""
    fam = refs.familias.get(str(ficha.get("familia") or ""), "")
    return name_tokens(name, cid, fam)


def effective_territory(cid: str, eco: dict, refs: Refs) -> list[str]:
    """Territorio autorado, ou o default: habitat da ficha / nos da regiao (legado)."""
    terr = list((eco or {}).get("territorio") or [])
    if terr:
        return terr
    ficha = refs.fichas.get(cid)
    if ficha:
        return [n for n in ficha.get("habitat") or [] if n in refs.region_nodes]
    return sorted(refs.region_nodes)


def _allowed_territory(cid: str, refs: Refs) -> set[str]:
    ficha = refs.fichas.get(cid)
    if ficha:
        return set(ficha.get("habitat") or []) & set(refs.region_nodes)
    regions = set((refs.bestiary.get(cid) or {}).get("regions") or [])
    return set(refs.region_nodes) if refs.region in regions else set()


# --------------------------------------------------------------------------- regras


def _e1_entry(cid: str, e: Any, refs: Refs) -> list[str]:
    errs: list[str] = []
    if not isinstance(e, dict):
        return [f"E1 {cid}: entrada nao e mapa"]
    unknown = set(e) - ENTRY_KEYS
    if unknown:
        errs.append(f"E1 {cid}: campo desconhecido {sorted(unknown)}")
    missing = ENTRY_REQUIRED - set(e)
    if missing:
        errs.append(f"E1 {cid}: faltam {sorted(missing)}")
    fonte = e.get("fonte")
    if fonte not in FONTES:
        errs.append(f"E1 {cid}: fonte {fonte!r} fora de {FONTES}")
    elif (fonte == "ficha") != (cid in refs.fichas):
        errs.append(f"E1 {cid}: fonte {fonte!r} nao bate com a ficha")
    if e.get("revisao") not in REVISAO:
        errs.append(f"E1 {cid}: revisao {e.get('revisao')!r} fora de {REVISAO}")
    if not isinstance(e.get("tramas", []), list) or not all(
        isinstance(t, str) for t in e.get("tramas") or []
    ):
        errs.append(f"E1 {cid}: tramas deve ser lista de ids")
    eco = e.get("ecologia")
    if not isinstance(eco, dict):
        errs.append(f"E1 {cid}: ecologia ausente")
        eco = {}
    unknown = set(eco) - ECO_KEYS
    if unknown:
        errs.append(f"E1 {cid}: ecologia com campo desconhecido {sorted(unknown)}")
    perm = eco.get("permanencia")
    if perm is not None and not (
        isinstance(perm, list)
        and len(perm) == 2
        and all(isinstance(x, int) and 1 <= x <= 30 for x in perm)
        and perm[0] <= perm[1]
    ):
        errs.append(f"E1 {cid}: permanencia deve ser [min, max] em dias (1..30)")
    for key in ("presas", "suprime", "foge_de", "territorio", "horario"):
        if key in eco and not isinstance(eco[key], list):
            errs.append(f"E1 {cid}: {key} deve ser lista")
    for r in eco.get("reage") or []:
        if not isinstance(r, dict) or set(r) != {"quando", "efeito"}:
            errs.append(f"E1 {cid}: reage {r!r} deve ter so quando/efeito")
            continue
        if r["efeito"] not in EFEITOS:
            errs.append(f"E1 {cid}: efeito {r['efeito']!r} fora de {EFEITOS}")
        q = str(r["quando"])
        if q == "carcaca_recente":
            continue
        kind, _, val = q.partition(":")
        if kind == "clima" and val in refs.weather_states:
            continue
        if kind == "pressao" and val in PRESSOES:
            continue
        errs.append(f"E1 {cid}: quando {q!r} invalido")
    sinais = e.get("sinais")
    if not isinstance(sinais, dict):
        errs.append(f"E1 {cid}: sinais ausente")
        sinais = {}
    unknown = set(sinais) - SINAIS_KEYS
    if unknown:
        errs.append(f"E1 {cid}: sinais com campo desconhecido {sorted(unknown)}")
    if sinais.get("antecedencia") not in ANTECEDENCIA:
        errs.append(f"E1 {cid}: antecedencia {sinais.get('antecedencia')!r} fora de {ANTECEDENCIA}")
    for k in TEXT_KINDS:
        v = sinais.get(k)
        if v is not None and not isinstance(v, str):
            errs.append(f"E1 {cid}: sinal {k} deve ser texto ou null")
    return errs


def _rules_entry(cid: str, e: dict, refs: Refs) -> list[str]:
    errs: list[str] = []
    eco = e.get("ecologia") or {}
    sinais = e.get("sinais") or {}
    hor = eco.get("horario") or []
    if not hor or not set(hor) <= set(refs.periods):
        errs.append(f"E2 {cid}: horario {hor!r} vazio ou fora de {list(refs.periods)}")
    est = eco.get("estacoes") or {}
    if not isinstance(est, dict):
        errs.append(f"E3 {cid}: estacoes deve ser mapa")
    else:
        for k, v in est.items():
            if k not in refs.seasons:
                errs.append(f"E3 {cid}: estacao {k!r} desconhecida")
            if not isinstance(v, (int, float)) or not 0 <= float(v) <= 3:
                errs.append(f"E3 {cid}: estacao {k} com valor {v!r} fora de [0, 3]")
    allowed = _allowed_territory(cid, refs)
    terr = eco.get("territorio") or []
    if not set(terr) <= allowed:
        errs.append(f"E4 {cid}: territorio {sorted(set(terr) - allowed)} fora do habitat/regiao")
    if not effective_territory(cid, eco, refs):
        errs.append(f"E4 {cid}: territorio efetivo vazio")
    for key in ("presas", "suprime", "foge_de"):
        for other in eco.get(key) or []:
            if other == cid:
                errs.append(f"E5 {cid}: {key} contem a propria criatura")
            elif other not in refs.bestiary:
                errs.append(f"E5 {cid}: {key} {other!r} nao existe no bestiario")
    both = set(eco.get("presas") or []) & set(eco.get("suprime") or [])
    if both:
        errs.append(f"E17 {cid}: {sorted(both)} em presas e suprime ao mesmo tempo")
    for sup in eco.get("suprime") or []:
        regions = set((refs.bestiary.get(sup) or {}).get("regions") or [])
        if refs.bestiary.get(sup) and not regions & ({refs.region} | set(refs.adjacency)):
            errs.append(f"E17 {cid}: suprime {sup} fora da regiao e das adjacentes")
    for prey in eco.get("presas") or []:
        b = refs.bestiary.get(prey) or {}
        if b.get("boss"):
            errs.append(f"E6 {cid}: presa {prey} e BOSS")
        regions = set(b.get("regions") or [])
        if b and not regions & ({refs.region} | set(refs.adjacency)):
            errs.append(f"E8 {cid}: presa {prey} fora da regiao e das adjacentes")
    present = [k for k in SIGN_KINDS if sinais.get(k)]
    if len(present) < MIN_SIGNS:
        errs.append(f"E9 {cid}: so {len(present)} tipos de sinal (minimo {MIN_SIGNS})")
    for k in ("aproximacao", "rumor"):
        if not str(sinais.get(k) or "").strip():
            errs.append(f"E9 {cid}: {k} obrigatorio")
    for k in TEXT_KINDS:
        v = sinais.get(k)
        if not v:
            continue
        limit = MAX_RUMOR if k == "rumor" else MAX_SIGN
        if len(str(v)) > limit:
            errs.append(f"E9 {cid}: {k} com {len(str(v))} chars (max {limit})")
        leaked = leaked_tokens(v, forbidden_for(cid, refs))
        if leaked:
            errs.append(f"E10 {cid}: {k} contem nome/id/familia {leaked}")
        fv = fold(v)
        for vago in refs.vagos:
            if vago and vago in fv:
                errs.append(f"E11 {cid}: {k} vago ({vago!r})")
        for phrase in refs.leak_phrases:
            if phrase and phrase in fv:
                errs.append(f"E16 {cid}: {k} contem frase de segredo ({phrase!r})")
    cj = str(e.get("contra_jogo") or "").strip()
    if not cj:
        errs.append(f"E13 {cid}: contra_jogo vazio")
    elif cid in refs.fichas and cj != str(refs.fichas[cid].get("contra_jogo") or "").strip():
        errs.append(f"E13 {cid}: contra_jogo difere da ficha")
    return errs


def lint_region(doc: Any, refs: Refs) -> list[str]:
    """Erros (texto 'Ennn id: motivo'). Lista vazia = regiao valida."""
    if not isinstance(doc, dict):
        return ["E1: arquivo nao e mapa"]
    errs: list[str] = []
    unknown = set(doc) - {"regiao", "criaturas"}
    if unknown:
        errs.append(f"E1: chaves desconhecidas {sorted(unknown)}")
    if doc.get("regiao") != refs.region:
        errs.append(f"E1: regiao {doc.get('regiao')!r} != {refs.region!r}")
    crit = doc.get("criaturas")
    if not isinstance(crit, dict) or not crit:
        return [*errs, "E1: criaturas vazio"]
    expected = set(refs.fichas) | set(refs.legacy)
    if set(crit) != expected:
        falta, sobra = sorted(expected - set(crit)), sorted(set(crit) - expected)
        errs.append(f"R2: cobertura difere (faltam {falta}; sobram {sobra})")
    for cid in sorted(crit):
        e1 = _e1_entry(cid, crit[cid], refs)
        errs += e1
        if isinstance(crit[cid], dict):
            errs += _rules_entry(cid, crit[cid], refs)
    entries = {c: e for c, e in crit.items() if isinstance(e, dict)}
    # E7: sem ciclo de tamanho 2 (inclui presas de outras regioes)
    presas = {c: set((e.get("ecologia") or {}).get("presas") or []) for c, e in entries.items()}
    for c, ps in refs.other_presas.items():
        presas.setdefault(c, set()).update(ps)
    for a in sorted(entries):
        for b in sorted(presas.get(a, ())):
            if a in presas.get(b, ()):
                errs.append(f"E7 {a}: ciclo de predacao com {b}")
    # E17: suprime sem ciclo de tamanho 2 (supressao e uma ordem, nao uma briga mutua)
    supr = {c: set((e.get("ecologia") or {}).get("suprime") or []) for c, e in entries.items()}
    for a in sorted(entries):
        for b in sorted(supr.get(a, ())):
            if a in supr.get(b, ()):
                errs.append(f"E17 {a}: ciclo de suprime com {b}")
    # E12: anti-reskin entre criaturas da regiao, por tipo de sinal
    ids = sorted(entries)
    for k in TEXT_KINDS:
        for i, a in enumerate(ids):
            ta = (entries[a].get("sinais") or {}).get(k)
            if not ta:
                continue
            for b in ids[i + 1 :]:
                tb = (entries[b].get("sinais") or {}).get(k)
                if tb and jaccard(ta, tb) >= MAX_JACCARD:
                    errs.append(f"E12 {a}: {k} parecido demais com o de {b}")
    # E14 / E15: proporcoes da regiao
    if entries:
        imediato = [
            c
            for c, e in entries.items()
            if (e.get("sinais") or {}).get("antecedencia") == "imediato"
        ]
        if len(imediato) > MAX_IMEDIATO * len(entries):
            errs.append(f"E14: {len(imediato)}/{len(entries)} com antecedencia imediato (> 30 %)")
        non_boss = [c for c in entries if not (refs.bestiary.get(c) or {}).get("boss")]
        preyed = {p for ps in presas.values() for p in ps}
        suppressed = {p for ps in supr.values() for p in ps}  # `suprime` conta como ligacao
        linked = [
            c for c in non_boss if presas.get(c) or supr.get(c) or c in preyed or c in suppressed
        ]
        if non_boss and len(linked) < MIN_TROFICA * len(non_boss):
            errs.append(
                f"E15: so {len(linked)}/{len(non_boss)} nao-BOSS com ligacao trofica (< 60 %)"
            )
        # E18: no maximo 2 `imediato` cujo territorio inclui o no de chegada da regiao
        if refs.hub:
            at_hub = [
                c
                for c in imediato
                if refs.hub in effective_territory(c, entries[c].get("ecologia") or {}, refs)
            ]
            if len(at_hub) > MAX_IMEDIATO_HUB:
                errs.append(
                    f"E18: {len(at_hub)} imediato no no de chegada {refs.hub} "
                    f"(max {MAX_IMEDIATO_HUB}): {sorted(at_hub)}"
                )
    return errs


# --------------------------------------------------------------------------- referencias reais


def _lexico_sections(path: Path = LEXICO) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = ""
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            out.setdefault(cur, [])
            continue
        out.setdefault(cur, []).append(fold(line))
    return out


def leak_phrases() -> tuple[str, ...]:
    """E16: frases de segredo. Fonte unica do validador de conteudo
    (`services.leak_phrases.all_phrases()`, SPEC-350), somadas as assinaturas de segredo
    canonicas e a secao `[vazamento]` do lexico."""
    phrases: set[str] = set(_lexico_sections().get("vazamento") or [])
    from services.leak_phrases import all_phrases
    from services.secret_signatures import SECRET_SIGNATURES

    phrases.update(fold(p) for p in all_phrases())
    for group in SECRET_SIGNATURES.values():
        phrases.update(fold(p) for p in group)
    return tuple(sorted(p for p in phrases if p))


def _yaml(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_refs(region: str, *, exclude_other: bool = False) -> Refs:
    import gamedata
    from encounter_budget import is_boss
    from services import world_calendar
    from services import world_pressures as wp
    from world_utils import PERIODS

    ficha_doc = _yaml(FICHAS_DIR / f"{region}.yaml") or {}
    fichas = {
        str(c["id"]): c for c in ficha_doc.get("criaturas") or [] if c.get("status") in FICHA_STATUS
    }
    bestiary_raw = gamedata.BESTIARY or {}
    bestiary = {
        k: {"name": v.get("name", ""), "regions": list(v.get("regions") or []), "boss": is_boss(v)}
        for k, v in bestiary_raw.items()
    }
    cur = _yaml(CURADORIA) or {}
    legacy = frozenset(
        k
        for k, v in cur.items()
        if isinstance(v, dict)
        and v.get("classe") == "valoria"
        and (bestiary.get(k, {}).get("regions") or [None])[0] == region
    )
    nodes = frozenset(
        loc["id"]
        for loc in gamedata.WORLD_MAP.get("locations", [])
        if loc.get("region_id") == region
    )
    weather = json.loads((ROOT / "data" / "weather.json").read_text(encoding="utf-8"))
    states: set[str] = set()
    for table in weather.values():
        if isinstance(table, dict):
            states.update((table.get("states") or {}).keys())
    other: dict[str, tuple[str, ...]] = {}
    if not exclude_other and FAUNA_DIR.exists():
        for path in sorted(FAUNA_DIR.glob("*.yaml")):
            if path.stem == region:
                continue
            doc = _yaml(path) or {}
            for c, e in (doc.get("criaturas") or {}).items():
                if isinstance(e, dict):
                    other[c] = tuple((e.get("ecologia") or {}).get("presas") or [])
    hub = next(
        (
            loc["id"]
            for loc in gamedata.WORLD_MAP.get("locations", [])
            if loc.get("id") == region and not loc.get("parent_id")
        ),
        "",
    )
    lex = _lexico_sections()
    return Refs(
        region=region,
        fichas=fichas,
        familias=dict(ficha_doc.get("familias_em_jogo") or {}),
        legacy=legacy,
        bestiary=bestiary,
        region_nodes=nodes,
        periods=tuple(PERIODS),
        seasons=tuple(world_calendar.SEASONS),
        weather_states=frozenset(states),
        adjacency=frozenset(wp.region_adjacency().get(region, [])),
        vagos=tuple(lex.get("vagos") or []),
        leak_phrases=leak_phrases(),
        other_presas=other,
        hub=hub,
    )


def lint_file(region: str) -> list[str]:
    path = FAUNA_DIR / f"{region}.yaml"
    if not path.exists():
        return [f"E1: {path.name} ausente"]
    return lint_region(_yaml(path), load_refs(region))


def covered_regions() -> list[str]:
    return sorted(p.stem for p in FAUNA_DIR.glob("*.yaml")) if FAUNA_DIR.exists() else []
