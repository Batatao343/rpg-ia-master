"""SPEC-372 R4/R5: forma do campo `tramas` e regras E19-E22 do lint de fauna.

Modulo proprio para manter `services/fauna_lint.py` pequeno. `lint_tramas(crit, refs)` e puro
dado o catalogo de tramas (injetavel nos testes). Importa `fauna_lint` so dentro das funcoes.
"""

from __future__ import annotations

from typing import Any

DESDE = ("tocada", "investigada", "revelada")
DEFAULT_DESDE = "tocada"  # string solta (D2)
MAX_TRAMAS = 2
MAX_LIGADAS = 0.25  # D4: fracao das nao-BOSS da regiao


def normalize_tramas(raw: Any) -> list[dict]:
    """Lista de `{id, desde}`; string solta vale `desde: tocada` (D1/D2). Ordem preservada."""
    out: list[dict] = []
    for t in raw or []:
        if isinstance(t, str):
            out.append({"id": t, "desde": DEFAULT_DESDE})
        elif isinstance(t, dict):
            out.append({"id": str(t.get("id") or ""), "desde": str(t.get("desde") or "")})
    return out


def tramas_form_ok(raw: Any) -> bool:
    """E1: lista de ids (string) ou de objetos `{id, desde}` (chaves exatas)."""
    if raw is None:
        return True
    if not isinstance(raw, list):
        return False
    return all(
        isinstance(t, str) or (isinstance(t, dict) and set(t) <= {"id", "desde"} and "id" in t)
        for t in raw
    )


def _forbidden_tokens(thr: Any) -> set[str]:
    from services import fauna_lint as fl
    from services import plot_threads as pt
    from services.secret_signatures import SECRET_SIGNATURES

    sigs = {k.casefold(): v for k, v in SECRET_SIGNATURES.items()}
    out: set[str] = set()
    for sid in thr.secret_ids:
        out |= fl.name_tokens(*sigs.get(str(sid).casefold(), []))
    for npc in thr.core:
        out |= fl.name_tokens(*pt.cast_names(npc))
    return out


def _entry_errs(cid: str, e: dict, refs: Any, threads: dict[str, Any]) -> list[str]:
    from services import fauna_lint as fl

    errs: list[str] = []
    links = normalize_tramas(e.get("tramas"))
    if (refs.bestiary.get(cid) or {}).get("boss"):
        return [f"E20 {cid}: BOSS nao tem tramas"]
    if len(links) > MAX_TRAMAS:
        errs.append(f"E20 {cid}: {len(links)} tramas (max {MAX_TRAMAS})")
    terr = set(fl.effective_territory(cid, e.get("ecologia") or {}, refs))
    for link in links:
        tid, desde = link["id"], link["desde"]
        thr = threads.get(tid)
        if thr is None or thr.region_id != refs.region:
            errs.append(f"E19 {cid}: trama {tid!r} nao existe na regiao {refs.region}")
            continue
        if desde not in DESDE:
            errs.append(f"E20 {cid}: desde {desde!r} fora de {DESDE}")
        if not terr & set(thr.locations):
            errs.append(f"E21 {cid}: territorio nao cruza os locais da trama {tid}")
        forb = _forbidden_tokens(thr)
        for k in fl.TEXT_KINDS:
            leaked = fl.leaked_tokens((e.get("sinais") or {}).get(k), forb)
            if leaked:
                errs.append(f"E22 {cid}: {k} contem token de segredo/nucleo de {tid} {leaked}")
    return errs


def lint_tramas(crit: dict, refs: Any, threads: dict[str, Any] | None = None) -> list[str]:
    """E19-E22 sobre as criaturas ligadas de uma regiao. `threads`: id -> PlotThread."""
    if threads is None:
        from services import plot_threads as pt

        threads = {t.id: t for t in pt.catalog().threads}
    errs: list[str] = []
    ligadas = 0
    non_boss = 0
    for cid in sorted(crit):
        e = crit[cid]
        if not isinstance(e, dict):
            continue
        if not (refs.bestiary.get(cid) or {}).get("boss"):
            non_boss += 1
        if not tramas_form_ok(e.get("tramas")) or not e.get("tramas"):
            continue
        ligadas += 1
        errs += _entry_errs(cid, e, refs, threads)
    if non_boss and ligadas > MAX_LIGADAS * non_boss:
        errs.append(f"E21: {ligadas}/{non_boss} nao-BOSS com tramas (> 25 %)")
    return errs
