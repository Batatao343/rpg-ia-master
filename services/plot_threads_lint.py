"""services/plot_threads_lint.py — lint puro do catálogo de tramas (SPEC-350 R2-R8, R15-R17).

`lint_plot_threads(data, refs)` devolve lista de mensagens (PT-BR); quem embrulha em
`Finding` é `content_validator.validate_plot_threads`. Zero LLM/rede. As referências
externas (ids do grafo, mapa, rumores, léxico...) chegam em `PlotRefs`, para o teste
usar fixtures sintéticas.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from itertools import islice

SIM_JACCARD_MAX = 0.35  # [BALANCEAR] limiar de near-duplicate entre fichas (R17c)
SECRET_WORD_MIN = 5

LEN_PERGUNTA = 160
LEN_RESUMO = 300
LEN_HOOK = 220
LEN_PAPEL = 120
LEN_DESEJO = 90
LEN_MEDO = 90
LEN_TOPICO = 60
LEN_REGISTRO = 60
LEN_FALA = 120

MIN_CORE = 2
MIN_BORDA = 2
MIN_DOORS = 3
MIN_DOOR_LOCATIONS = 2
MIN_THREADS_NOVA_ARCADIA = 5
MIN_THREADS_OTHER = 3

CHOSEN_ONE_TERMS = (
    "escolhid",
    "profeci",
    "predestin",
    "destinad",
    "sangue real",
    "herdeir",
    "unico que pode",
    "so voce",
    "marcado pelo destino",
)
_VOCE = re.compile(r"\bvoce\b")


def fold(text: object) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()
    return " ".join(stripped.split())


def _words(text: str, minlen: int) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", fold(text)) if len(w) >= minlen}


@dataclass
class PlotRefs:
    npc_ids: set[str] = field(default_factory=set)
    leader_ids: set[str] = field(default_factory=set)
    location_ids: set[str] = field(default_factory=set)
    faction_ids: set[str] = field(default_factory=set)
    rumor_ids: set[str] = field(default_factory=set)
    route_ids: set[str] = field(default_factory=set)
    secret_ids: set[str] = field(default_factory=set)
    archetypes: set[str] = field(default_factory=set)
    region_ids: set[str] = field(default_factory=set)
    posturas: set[str] = field(default_factory=set)
    banned_words: set[str] = field(default_factory=set)  # já dobrados
    secret_signatures: dict[str, list[str]] = field(default_factory=dict)
    leak_phrases: list[str] = field(default_factory=list)  # SPEC-348 LEAK_PHRASES (dobradas)
    secret_doc_visibility: dict[str, str] = field(default_factory=dict)  # doc id -> visibility
    secret_doc_text: dict[str, str] = field(default_factory=dict)  # doc id -> corpo
    public_doc_text: dict[str, str] = field(default_factory=dict)  # npc id -> corpo público
    secret_word_exceptions: set[str] = field(default_factory=set)
    name_owners: dict[str, set[str]] = field(default_factory=dict)  # nome dobrado -> ids
    npc_names: dict[str, list[str]] = field(default_factory=dict)  # npc id -> nome+aliases
    role_radicals: list[str] = field(default_factory=list)  # dobrados
    lore_reader: Callable[[str, int, int], str | None] | None = None


def plot_signature(sheet: dict, thread_index: dict, radicals: Iterable[str] = ()) -> tuple:
    """R17b: (radical do papel, link_kind principal, thread_id, tier) de uma ficha crua."""
    roles = sheet.get("threads") or [{}]
    first = roles[0] if isinstance(roles[0], dict) else {}
    tid = str(first.get("thread_id") or "")
    papel = fold(first.get("papel"))
    radical = next((r for r in radicals if r and r in papel), "")
    if not radical:
        radical = next((w for w in re.findall(r"[a-z]+", papel) if len(w) >= 4), papel[:12])
    link = ""
    thr = thread_index.get(tid) or {}
    npc_id = sheet.get("npc_id")
    for door in thr.get("portas") or []:
        if isinstance(door, dict) and door.get("anchor_npc_id") == npc_id:
            link = str(door.get("link_kind") or "")
            break
    return (radical, link, tid, str(sheet.get("tier") or ""))


def _public_fields(thr: dict, cast: dict) -> list[tuple[str, str]]:
    out = [
        (f"{thr.get('id')}.resumo_publico", str(thr.get("resumo_publico") or "")),
        (f"{thr.get('id')}.pergunta", str(thr.get("pergunta") or "")),
    ]
    for door in thr.get("portas") or []:
        if isinstance(door, dict):
            out.append((f"{door.get('id')}.hook_public", str(door.get("hook_public") or "")))
    return out


def _sheet_public_fields(nid: str, sheet: dict) -> list[tuple[str, str]]:
    voz = sheet.get("voz") if isinstance(sheet.get("voz"), dict) else {}
    out = [
        (f"{nid}.desejo", str(sheet.get("desejo") or "")),
        (f"{nid}.medo", str(sheet.get("medo") or "")),
        (f"{nid}.segredo_topico", str(sheet.get("segredo_topico") or "")),
        (f"{nid}.voz.registro", str(voz.get("registro") or "")),
        (f"{nid}.voz.fala", str(voz.get("fala") or "")),
    ]
    for r in sheet.get("threads") or []:
        if isinstance(r, dict):
            out.append((f"{nid}.papel[{r.get('thread_id')}]", str(r.get("papel") or "")))
    return out


def _too_long(errs: list[str], label: str, text: str, limit: int) -> None:
    if len(text) > limit:
        errs.append(f"{label}: {len(text)} caracteres (máx {limit})")


def _read_lore(refs: PlotRefs, ref: str) -> tuple[str | None, str]:
    """(texto do intervalo | None, motivo). Lê só o intervalo (islice)."""
    m = re.fullmatch(r"(lore_nova/[^:]+):(\d+)-(\d+)", ref)
    if not m:
        return None, "formato inválido (esperado lore_nova/<arq>:<a>-<b>)"
    path, a, b = m.group(1), int(m.group(2)), int(m.group(3))
    if a < 1 or b < a:
        return None, "intervalo inválido"
    if refs.lore_reader is not None:
        text = refs.lore_reader(path, a, b)
    else:
        try:
            with open(path, encoding="utf-8") as f:
                text = "".join(islice(f, a - 1, b))
        except OSError:
            text = None
    if text is None:
        return None, "arquivo inexistente"
    return text, ""


def lint_plot_threads(data: dict, refs: PlotRefs) -> list[str]:
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["catálogo não é um objeto JSON"]
    threads = [t for t in data.get("threads") or [] if isinstance(t, dict)]
    cast = {k: v for k, v in (data.get("cast") or {}).items() if isinstance(v, dict)}
    waves = [w for w in data.get("waves") or [] if isinstance(w, dict)]
    excluded = data.get("excluded") or {}
    tindex = {str(t.get("id")): t for t in threads}
    thread_ids = set(tindex)

    # --- R2-R6: tramas e portas -------------------------------------------------
    for thr in threads:
        tid = str(thr.get("id") or "")
        if tid and not re.fullmatch(r"tr_[a-z0-9_]+", tid):
            errs.append(f"{tid}: id de trama fora do padrão tr_<regiao>_<slug>")
        if thr.get("region_id") not in refs.region_ids:
            errs.append(f"{tid}: region_id inexistente '{thr.get('region_id')}'")
        _too_long(errs, f"{tid}.pergunta", str(thr.get("pergunta") or ""), LEN_PERGUNTA)
        _too_long(errs, f"{tid}.resumo_publico", str(thr.get("resumo_publico") or ""), LEN_RESUMO)
        core, borda = list(thr.get("core") or []), list(thr.get("borda") or [])
        if len(core) < MIN_CORE:
            errs.append(f"{tid}: core com {len(core)} NPC(s) (mín {MIN_CORE})")
        if len(borda) < MIN_BORDA:
            errs.append(f"{tid}: borda com {len(borda)} NPC(s) (mín {MIN_BORDA})")
        for nid in core + borda:
            if nid not in refs.npc_ids:
                errs.append(f"{tid}: NPC inexistente '{nid}'")
        for nid in borda:
            if nid in refs.npc_ids and nid not in cast:
                errs.append(f"{tid}: NPC de borda '{nid}' sem ficha em cast")
        if not thr.get("factions"):
            errs.append(f"{tid}: sem facção")
        for fid in thr.get("factions") or []:
            if fid not in refs.faction_ids:
                errs.append(f"{tid}: facção inexistente '{fid}'")
        if not thr.get("locations"):
            errs.append(f"{tid}: sem local")
        for lid in thr.get("locations") or []:
            if lid not in refs.location_ids:
                errs.append(f"{tid}: local inexistente '{lid}'")
        if not thr.get("rumor_ids"):
            errs.append(f"{tid}: sem rumor")
        for rid in thr.get("rumor_ids") or []:
            if rid not in refs.rumor_ids:
                errs.append(f"{tid}: rumor inexistente '{rid}'")
        for sid in thr.get("secret_ids") or []:
            if sid not in refs.secret_ids:
                errs.append(f"{tid}: segredo inexistente '{sid}'")
        for pos in thr.get("postura_afinidade") or []:
            if refs.posturas and pos not in refs.posturas:
                errs.append(f"{tid}: Postura inexistente '{pos}'")
        if len(thr.get("postura_afinidade") or []) > 2:
            errs.append(f"{tid}: postura_afinidade com mais de 2 chaves")

        # lore_refs + keyword
        lrefs = list(thr.get("lore_refs") or [])
        if not lrefs:
            errs.append(f"{tid}: sem lore_refs")
        kw = fold(thr.get("lore_keyword"))
        if lrefs and not kw:
            errs.append(f"{tid}: lore_keyword vazio")
        for ref in lrefs:
            text, why = _read_lore(refs, str(ref))
            if text is None:
                errs.append(f"{tid}: lore_ref '{ref}' {why}")
            elif kw and kw not in fold(text):
                errs.append(f"{tid}: lore_keyword '{kw}' ausente em '{ref}'")

        # portas
        doors = [d for d in thr.get("portas") or [] if isinstance(d, dict)]
        if len(doors) < MIN_DOORS:
            errs.append(f"{tid}: {len(doors)} porta(s) (mín {MIN_DOORS})")
        anchors = [d.get("anchor_npc_id") for d in doors]
        if len(set(anchors)) < len(anchors):
            errs.append(f"{tid}: portas com âncora repetida")
        if len({d.get("location_id") for d in doors}) < MIN_DOOR_LOCATIONS:
            errs.append(f"{tid}: portas em menos de {MIN_DOOR_LOCATIONS} locais distintos")
        for i, door in enumerate(doors, start=1):
            did = str(door.get("id") or "")
            if did != f"{tid}__p{i}":
                errs.append(f"{tid}: id de porta '{did}' deveria ser '{tid}__p{i}'")
            aid = door.get("anchor_npc_id")
            if aid not in refs.npc_ids:
                errs.append(f"{did}: âncora inexistente '{aid}'")
            if door.get("location_id") not in refs.location_ids:
                errs.append(f"{did}: local inexistente '{door.get('location_id')}'")
            _too_long(errs, f"{did}.hook_public", str(door.get("hook_public") or ""), LEN_HOOK)
            if not door.get("hook_public"):
                errs.append(f"{did}: hook_public vazio")
            if aid not in core and aid not in borda:
                errs.append(f"{did}: âncora '{aid}' fora de core/borda da trama")
            sheet = cast.get(str(aid))
            if aid in refs.leader_ids or aid in core:
                errs.append(f"{did}: âncora '{aid}' é núcleo/líder (R5)")
            elif sheet is None:
                errs.append(f"{did}: âncora '{aid}' sem ficha em cast")
            elif sheet.get("tier") not in ("borda", "ponte"):
                errs.append(f"{did}: âncora '{aid}' com tier '{sheet.get('tier')}' (R5)")
            for rid in door.get("rumor_ids") or []:
                if rid not in refs.rumor_ids:
                    errs.append(f"{did}: rumor inexistente '{rid}'")
            hint = door.get("quest_hint")
            if isinstance(hint, dict):
                kind, anc = hint.get("kind"), hint.get("anchor_id")
                if kind == "investigar_rumor" and anc not in refs.rumor_ids:
                    errs.append(f"{did}: quest_hint rumor inexistente '{anc}'")
                elif kind == "entregar_material" and anc not in refs.route_ids:
                    errs.append(f"{did}: quest_hint rota inexistente '{anc}'")
                elif kind == "escoltar" and anc != aid:
                    errs.append(f"{did}: quest_hint escoltar deve apontar a própria âncora")
                elif kind not in ("investigar_rumor", "entregar_material", "escoltar"):
                    errs.append(f"{did}: quest_hint.kind inválido '{kind}'")

        # R6 (nada de escolhido) nos textos de mundo
        world_texts = _public_fields(thr, cast)
        for label, text in world_texts:
            f = fold(text)
            hit = next((t for t in CHOSEN_ONE_TERMS if t in f), None)
            if hit or _VOCE.search(f):
                errs.append(
                    f"{label}: vocabulário de 'escolhido'/segundo pessoa ('{hit or 'voce'}')"
                )

    # --- R7: fichas -------------------------------------------------------------
    for nid, sheet in sorted(cast.items()):
        if nid not in refs.npc_ids:
            errs.append(f"cast: NPC inexistente '{nid}'")
        roles = [r for r in sheet.get("threads") or [] if isinstance(r, dict)]
        if not roles:
            errs.append(f"{nid}: ficha sem trama")
        for r in roles:
            if r.get("thread_id") not in thread_ids:
                errs.append(f"{nid}: trama inexistente '{r.get('thread_id')}'")
        if sheet.get("archetype") not in refs.archetypes:
            errs.append(f"{nid}: archetype inexistente '{sheet.get('archetype')}'")
        if sheet.get("home_location_id") not in refs.location_ids:
            errs.append(f"{nid}: home_location_id inexistente '{sheet.get('home_location_id')}'")
        for r in roles:
            _too_long(errs, f"{nid}.papel", str(r.get("papel") or ""), LEN_PAPEL)
        _too_long(errs, f"{nid}.desejo", str(sheet.get("desejo") or ""), LEN_DESEJO)
        _too_long(errs, f"{nid}.medo", str(sheet.get("medo") or ""), LEN_MEDO)
        _too_long(errs, f"{nid}.segredo_topico", str(sheet.get("segredo_topico") or ""), LEN_TOPICO)
        voz = sheet.get("voz") if isinstance(sheet.get("voz"), dict) else {}
        _too_long(errs, f"{nid}.voz.registro", str(voz.get("registro") or ""), LEN_REGISTRO)
        _too_long(errs, f"{nid}.voz.fala", str(voz.get("fala") or ""), LEN_FALA)
        is_new = sheet.get("fonte") == "spec350"
        doc = str(sheet.get("segredo_doc_id") or "")
        if (is_new or sheet.get("tier") == "borda") and not doc:
            errs.append(f"{nid}: segredo_doc_id obrigatório (borda ou NPC novo)")
        if doc:
            vis = refs.secret_doc_visibility.get(doc)
            if vis is None:
                errs.append(f"{nid}: segredo_doc_id inexistente '{doc}'")
            elif vis not in ("hidden", "secret"):
                errs.append(f"{nid}: doc de segredo '{doc}' não é oculto (visibility={vis})")
        if not sheet.get("fonte"):
            errs.append(f"{nid}: sem 'fonte'")

    # --- léxico proibido em qualquer texto -----------------------------------
    all_public: list[tuple[str, str]] = []
    for thr in threads:
        all_public += _public_fields(thr, cast)
    for nid, sheet in cast.items():
        all_public += _sheet_public_fields(nid, sheet)
    for label, text in all_public:
        bad = sorted(w for w in _words(text, 1) if w in refs.banned_words)
        if bad:
            errs.append(f"{label}: termo proibido do léxico de Valoria {bad}")

    # --- R16: vazamento -------------------------------------------------------
    for thr in threads:
        tid = str(thr.get("id"))
        sigs = [
            fold(p)
            for sid in thr.get("secret_ids") or []
            for p in refs.secret_signatures.get(sid, [])
        ]
        members = set(thr.get("core") or []) | set(thr.get("borda") or [])
        texts = list(_public_fields(thr, cast))
        for nid in members & set(cast):
            texts += _sheet_public_fields(nid, cast[nid])
        for label, text in texts:
            f = fold(text)
            for phrase in sigs:
                if phrase and phrase in f:
                    errs.append(f"{label}: vaza assinatura de segredo '{phrase}'")
    for label, text in all_public:
        f = fold(text)
        for phrase in refs.leak_phrases:
            if phrase and phrase in f:
                errs.append(f"{label}: contém LEAK_PHRASE '{phrase}'")
    for nid, body in sorted(refs.public_doc_text.items()):
        f = fold(body)
        for sigs_ in refs.secret_signatures.values():
            for phrase in sigs_:
                if fold(phrase) in f:
                    errs.append(f"doc público de {nid}: vaza assinatura de segredo '{phrase}'")
        for phrase in refs.leak_phrases:
            if phrase and phrase in f:
                errs.append(f"doc público de {nid}: contém LEAK_PHRASE '{phrase}'")
    for nid, sheet in sorted(cast.items()):
        doc = str(sheet.get("segredo_doc_id") or "")
        if doc not in refs.secret_doc_text:
            continue
        exclusive = (
            _words(refs.secret_doc_text[doc], SECRET_WORD_MIN)
            - _words(refs.public_doc_text.get(nid, ""), SECRET_WORD_MIN)
            - refs.secret_word_exceptions
        )
        sheet_words = set()
        for _label, text in _sheet_public_fields(nid, sheet):
            sheet_words |= _words(text, SECRET_WORD_MIN)
        leaked = sorted(exclusive & sheet_words)
        if leaked:
            errs.append(f"{nid}: ficha pública usa palavra exclusiva do segredo {leaked}")

    # --- R17: unicidade -------------------------------------------------------
    new_ids = sorted(n for n, s in cast.items() if s.get("fonte") == "spec350")
    for nid in new_ids:
        for name in refs.npc_names.get(nid, []):
            owners = refs.name_owners.get(fold(name), set()) - {nid}
            if owners:
                errs.append(f"{nid}: nome/alias '{name}' colide com {sorted(owners)}")
    sigs: dict[tuple, str] = {}
    for nid, sheet in sorted(cast.items()):
        s = plot_signature({**sheet, "npc_id": nid}, tindex, refs.role_radicals)
        if s in sigs:
            errs.append(f"{nid}: assinatura duplicada com {sigs[s]} {s}")
        else:
            sigs[s] = nid

    def sheet_tokens(sheet: dict) -> set[str]:
        voz = sheet.get("voz") if isinstance(sheet.get("voz"), dict) else {}
        text = " ".join(
            str(x or "")
            for x in (
                sheet.get("desejo"),
                sheet.get("medo"),
                sheet.get("segredo_topico"),
                voz.get("fala"),
            )
        )
        return _words(text, 3)

    toks = {n: sheet_tokens(s) for n, s in cast.items()}
    ids = sorted(toks)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            union = toks[a] | toks[b]
            if union and len(toks[a] & toks[b]) / len(union) >= SIM_JACCARD_MAX:
                errs.append(f"{a} e {b}: fichas quase iguais (Jaccard >= {SIM_JACCARD_MAX})")
    by_region: dict[tuple[str, str], list[str]] = {}
    for nid in new_ids:
        sheet = cast[nid]
        first = next((r for r in sheet.get("threads") or [] if isinstance(r, dict)), {})
        region = str((tindex.get(first.get("thread_id")) or {}).get("region_id") or "")
        rad = plot_signature({**sheet, "npc_id": nid}, tindex, refs.role_radicals)[0]
        by_region.setdefault((region, rad), []).append(nid)
    for (region, rad), group in sorted(by_region.items()):
        if len(group) > 1:
            errs.append(f"{region}: NPCs novos com o mesmo radical de papel '{rad}': {group}")

    # --- R8: cobertura ------------------------------------------------------
    in_thread = {
        r.get("thread_id")
        for s in cast.values()
        for r in s.get("threads") or []
        if isinstance(r, dict)
    }
    for nid in new_ids:
        if not any(r.get("thread_id") in thread_ids for r in cast[nid].get("threads") or []):
            errs.append(f"{nid}: NPC novo fora de qualquer trama")
    for thr in threads:
        if thr.get("id") not in in_thread:
            errs.append(f"{thr.get('id')}: trama sem ninguém no cast")
    for nid in excluded:
        if nid not in refs.npc_ids:
            errs.append(f"excluded: NPC inexistente '{nid}'")
    for w in waves:
        if w.get("status") != "done":
            continue
        for region in w.get("regions") or []:
            need = MIN_THREADS_NOVA_ARCADIA if region == "nova_arcadia" else MIN_THREADS_OTHER
            have = sum(1 for t in threads if t.get("region_id") == region)
            if have < need:
                errs.append(
                    f"onda {w.get('order')}: região {region} com {have} trama(s) (mín {need})"
                )
    return sorted(set(errs))
