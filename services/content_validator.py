"""
content_validator.py — Lint de conteúdo autoral (Fase 7.1).

Valida frontmatter, ids, referências, aliases, visibilidade e encoding de todo
o conteúdo do Codex (`data/codex/**/*.md`) e do grafo (`data/graph/*.json`).
Funções puras, zero LLM/rede; leem disco fresco (NÃO usam os caches do
graph_resolver). Spec: specs/fase-7.1-validadores-conteudo.md.

CLI: `uv run python scripts/validate_content.py` (exit 1 com qualquer ERRO).
O gate sobre os dados reais do repo é `tests/test_fase71.py::test_repo_content_sem_erros`.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

import yaml

from services.codex_loader import CODEX_DIR, parse_codex_file

GRAPH_DIR = os.path.join("data", "graph")
LORE_DIR = "lore_nova"
OVERRIDES_PATH = os.path.join("data", "codex_overrides.yaml")

Severity = Literal["error", "warning"]


@dataclass
class Finding:
    validator: str    # "frontmatter" | "ids" | "references" | "aliases" | "visibility" | "encoding"
    severity: Severity
    path: str         # arquivo onde foi achado (md/json)
    entity_id: str    # id envolvido ("" se não aplicável)
    message: str      # humano, em PT-BR


CODEX_TYPES = {
    "location", "faction", "npc", "race", "monster", "artifact",
    "items", "secret", "perspective", "world_story", "timeline",
    "npc_secret",  # Fase 7.3 — doc paralelo com a verdade oculta de um NPC
}
VISIBILITIES = {"public", "hidden", "secret"}

# Fase 7.3 — rótulos de parágrafo (`Rótulo: texto`) que marcam conteúdo SECRETO
# num doc de NPC. Normalizados (sem acento + casefold). O migrate script move
# esses parágrafos para `npcs/segredos/{id}_segredo.md` (visibility: hidden);
# o lint acusa ERRO se algum voltar a doc público de NPC (anti-regressão).
# "rumor verdadeiro": o rumor em si circula publicamente (rumors.txt); o que o
# doc de NPC marca é a CONFIRMAÇÃO de que é verdade — isso é spoiler, vai pro hidden.
NPC_SECRET_LABELS = frozenset({
    "historia real",
    "motivacao real",
    "o que ele esconde",
    "o que ela esconde",
    "segredo",
    "o pacto e seus efeitos",
    "rumor verdadeiro",
    "verdade",
    # Achados na auditoria da Etapa 4 (rótulos reais de lore_nova/npcs.txt que
    # carregam twist/verdade oculta — revisão manual de 2026-07-05):
    "a verdade",                        # Velha Magda: passado de sacerdotisa/Mão Sombria
    "identidade real",                  # Arauto da Névoa: é o aprendiz de Aethelgard
    "papel real",                       # Lady Aerwen: governa no lugar do marido perdido
    "o que nao diz",                    # Doutor Silas Vane: experimentos com a Praga
    "o segredo do barril",              # Grum: documento escondido na taverna
    "relacao com a guilda dos corvos",  # Silas Vane: acordo de corpos marcados
    "o que fazem com as memorias",      # Mercadores de Curiosidades: memórias consumidas
})

# Campos de frontmatter que, quando presentes, precisam ser lista de strings.
_LIST_FIELDS = ("tags", "aliases", "related_entities")

# Violações conhecidas e justificadas — (validator, entity_id). Ideal: vazia.
_LINT_WHITELIST: set[tuple[str, str]] = set()


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def _norm(text: str) -> str:
    """Normalização de alias/name/id para detectar colisão (casefold + sem acento)."""
    return _strip_accents(str(text)).casefold().strip()


def _codex_md_paths(codex_dir: str) -> List[str]:
    paths: List[str] = []
    for root, _dirs, files in os.walk(codex_dir):
        for fname in sorted(files):
            if fname.endswith(".md"):
                paths.append(os.path.join(root, fname))
    return paths


def _parse_codex(codex_dir: str) -> List[Tuple[str, dict, str]]:
    """(path, frontmatter, body) dos .md parseáveis — erro de parse é papel
    do validate_frontmatter; aqui arquivo quebrado é pulado em silêncio."""
    parsed: List[Tuple[str, dict, str]] = []
    for path in _codex_md_paths(codex_dir):
        try:
            frontmatter, body = parse_codex_file(path)
        except Exception:
            continue
        parsed.append((path, frontmatter, body))
    return parsed


def _read_graph_json(graph_dir: str, filename: str, default):
    path = os.path.join(graph_dir, filename)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merged_entities(graph_dir: str) -> Dict[str, dict]:
    """entities.json ∪ entities_extra.json lidos FRESCOS do disco (canônico vence)."""
    base = _read_graph_json(graph_dir, "entities.json", {})
    extra = _read_graph_json(graph_dir, "entities_extra.json", {})
    merged = dict(base)
    for eid, ent in extra.items():
        if eid not in merged:
            merged[eid] = ent
    return merged


# ---------------------------------------------------------------------------
# Validadores
# ---------------------------------------------------------------------------

def validate_frontmatter(codex_dir: str = CODEX_DIR) -> List[Finding]:
    """R1 — frontmatter completo, id == nome do arquivo, type/visibility canônicos."""
    findings: List[Finding] = []
    for path in _codex_md_paths(codex_dir):
        try:
            frontmatter, _body = parse_codex_file(path)
        except ValueError as exc:
            findings.append(Finding("frontmatter", "error", path, "", str(exc)))
            continue

        entity_id = str(frontmatter.get("id", ""))
        stem = os.path.splitext(os.path.basename(path))[0]
        if entity_id != stem:
            findings.append(Finding(
                "frontmatter", "error", path, entity_id,
                f"id '{entity_id}' diverge do nome do arquivo '{stem}'"))
        if frontmatter.get("type") not in CODEX_TYPES:
            findings.append(Finding(
                "frontmatter", "error", path, entity_id,
                f"type '{frontmatter.get('type')}' fora do conjunto canônico"))
        if frontmatter.get("visibility") not in VISIBILITIES:
            findings.append(Finding(
                "frontmatter", "error", path, entity_id,
                f"visibility '{frontmatter.get('visibility')}' inválida "
                f"(esperado public|hidden|secret)"))
        for campo in _LIST_FIELDS:
            if campo in frontmatter:
                valor = frontmatter[campo]
                if not isinstance(valor, list) or any(not isinstance(v, str) for v in valor):
                    findings.append(Finding(
                        "frontmatter", "error", path, entity_id,
                        f"campo '{campo}' precisa ser lista de strings"))
    return findings


def validate_ids(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> List[Finding]:
    """R2 — ids únicos no Codex; extra não conflita com canônico; components só
    referencia ids existentes."""
    findings: List[Finding] = []

    seen: Dict[str, str] = {}
    for path, frontmatter, _body in _parse_codex(codex_dir):
        entity_id = str(frontmatter.get("id", ""))
        if entity_id in seen:
            findings.append(Finding(
                "ids", "error", path, entity_id,
                f"id duplicado no Codex (também em {seen[entity_id]})"))
        else:
            seen[entity_id] = path

    base = _read_graph_json(graph_dir, "entities.json", {})
    extra = _read_graph_json(graph_dir, "entities_extra.json", {})
    extra_path = os.path.join(graph_dir, "entities_extra.json")
    for eid in extra:
        if eid in base:
            findings.append(Finding(
                "ids", "error", extra_path, eid,
                "id de entities_extra.json conflita com entities.json (canônico vence)"))

    merged = _merged_entities(graph_dir)
    components = _read_graph_json(graph_dir, "components.json", {})
    comp_path = os.path.join(graph_dir, "components.json")
    for eid in components:
        if eid.startswith("_"):
            continue
        if eid not in merged:
            findings.append(Finding(
                "ids", "error", comp_path, eid,
                "components.json referencia id que não existe nas entidades"))
    return findings


def validate_references(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> List[Finding]:
    """R3 — related_entities apontam para entidades; edges íntegras e dentro
    das constraints de relation_types.json."""
    findings: List[Finding] = []
    entities = _merged_entities(graph_dir)

    for path, frontmatter, _body in _parse_codex(codex_dir):
        entity_id = str(frontmatter.get("id", ""))
        related = frontmatter.get("related_entities") or []
        if not isinstance(related, list):
            continue  # frontmatter validator já acusa
        for ref in related:
            if ref not in entities:
                findings.append(Finding(
                    "references", "error", path, entity_id,
                    f"related_entities aponta para '{ref}', que não existe"))

    edges = _read_graph_json(graph_dir, "edges.json", [])
    relation_types = _read_graph_json(graph_dir, "relation_types.json", {})
    edges_path = os.path.join(graph_dir, "edges.json")
    seen_edge_ids: set = set()
    for edge in edges:
        edge_id = edge.get("id", "")
        if not edge_id:
            findings.append(Finding(
                "references", "error", edges_path, "",
                f"edge sem 'id': {edge}"))
        elif edge_id in seen_edge_ids:
            findings.append(Finding(
                "references", "error", edges_path, edge_id,
                "id de edge duplicado"))
        else:
            seen_edge_ids.add(edge_id)

        edge_type = edge.get("type")
        rel = relation_types.get(edge_type)
        if rel is None:
            findings.append(Finding(
                "references", "error", edges_path, edge_id,
                f"type '{edge_type}' não existe em relation_types.json"))

        for ponta in ("source", "target"):
            eid = edge.get(ponta)
            if eid not in entities:
                findings.append(Finding(
                    "references", "error", edges_path, edge_id,
                    f"{ponta} '{eid}' não existe nas entidades"))
            elif rel and ponta in rel:
                exigido = rel[ponta]
                real = entities[eid].get("type")
                if real != exigido:
                    findings.append(Finding(
                        "references", "error", edges_path, edge_id,
                        f"constraint de '{edge_type}': {ponta} '{eid}' precisa ser "
                        f"type '{exigido}', é '{real}'"))
    return findings


def validate_aliases(graph_dir: str = GRAPH_DIR) -> List[Finding]:
    """R4 — alias normalizado não repete entre entidades nem colide com
    name/id de OUTRA entidade."""
    findings: List[Finding] = []
    entities = _merged_entities(graph_dir)
    entities_path = os.path.join(graph_dir, "entities.json")

    # claves normalizadas -> dono (id) por origem name/id
    claimed: Dict[str, str] = {}
    for eid, ent in entities.items():
        claimed.setdefault(_norm(eid), eid)
        claimed.setdefault(_norm(ent.get("name", "")), eid)

    alias_owner: Dict[str, str] = {}
    for eid, ent in sorted(entities.items()):
        for alias in ent.get("aliases") or []:
            key = _norm(alias)
            if not key:
                continue
            dono = alias_owner.get(key)
            if dono and dono != eid:
                findings.append(Finding(
                    "aliases", "error", entities_path, eid,
                    f"alias '{alias}' duplicado com a entidade '{dono}'"))
                continue
            alias_owner[key] = eid
            outro = claimed.get(key)
            if outro and outro != eid:
                findings.append(Finding(
                    "aliases", "error", entities_path, eid,
                    f"alias '{alias}' colide com name/id da entidade '{outro}'"))
    return findings


def paragraph_label(paragraph: str) -> str:
    """Rótulo normalizado de um parágrafo (`Rótulo: texto` -> 'rotulo'); "" sem rótulo."""
    first = paragraph.strip().splitlines()[0] if paragraph.strip() else ""
    if ":" not in first:
        return ""
    return _norm(first.split(":", 1)[0])


def _secret_labels_in(body: str) -> List[str]:
    """Rótulos secretos presentes nos parágrafos de um corpo de doc de NPC."""
    achados: List[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        rotulo = paragraph_label(paragraph)
        if rotulo in NPC_SECRET_LABELS:
            achados.append(rotulo)
    return achados


def validate_visibility(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> List[Finding]:
    """R5 — type secret ⇒ visibility secret; doc public não referencia entidade/
    doc secret; visibility das entidades do grafo é canônica."""
    findings: List[Finding] = []
    entities = _merged_entities(graph_dir)

    # mapa id -> visibility (entidades do grafo + docs do Codex)
    vis_map: Dict[str, str] = {
        eid: ent.get("visibility", "public") for eid, ent in entities.items()
    }
    parsed = _parse_codex(codex_dir)
    for _path, frontmatter, _body in parsed:
        vis_map.setdefault(
            str(frontmatter.get("id", "")),
            frontmatter.get("visibility", "public"))

    for path, frontmatter, body in parsed:
        entity_id = str(frontmatter.get("id", ""))
        visibility = frontmatter.get("visibility", "public")
        if frontmatter.get("type") == "secret" and visibility != "secret":
            findings.append(Finding(
                "visibility", "error", path, entity_id,
                f"doc type 'secret' precisa de visibility 'secret', tem '{visibility}'"))
        # Fase 7.3 — segredo de NPC nunca é public; doc público de NPC não
        # pode conter parágrafo de rótulo secreto (vazaria ao narrador).
        if frontmatter.get("type") == "npc_secret" and visibility not in ("hidden", "secret"):
            findings.append(Finding(
                "visibility", "error", path, entity_id,
                f"doc 'npc_secret' precisa de visibility hidden/secret, tem '{visibility}'"))
        if frontmatter.get("type") == "npc" and visibility == "public":
            for rotulo in _secret_labels_in(body):
                findings.append(Finding(
                    "visibility", "error", path, entity_id,
                    f"doc público de NPC contém rótulo secreto '{rotulo}' — "
                    f"mover para o doc npc_secret (Fase 7.3)"))
        if visibility == "public":
            related = frontmatter.get("related_entities") or []
            if isinstance(related, list):
                for ref in related:
                    if vis_map.get(ref) == "secret":
                        findings.append(Finding(
                            "visibility", "error", path, entity_id,
                            f"doc public referencia '{ref}' (secret) — vaza a "
                            f"existência do segredo"))

    entities_path = os.path.join(graph_dir, "entities.json")
    for eid, ent in entities.items():
        vis = ent.get("visibility", "public")
        if vis not in VISIBILITIES:
            findings.append(Finding(
                "visibility", "error", entities_path, eid,
                f"visibility '{vis}' inválida no grafo (esperado public|hidden|secret)"))
    return findings


# Heurística de mojibake: UTF-8 lido como cp1252 e re-salvo gera pares tipo
# 'Ã©'/'Ã£'/'â€'. 'Ã' seguido de char em U+0080–U+00BF não ocorre em PT-BR
# legítimo ("SÃO" tem 'Ã' + letra maiúscula). AVISO, nunca ERRO (R6).
_MOJIBAKE_RE = re.compile("[ÃÂ][-¿]|â€")


def _default_encoding_paths(codex_dir: str = CODEX_DIR,
                            graph_dir: str = GRAPH_DIR,
                            lore_dir: str = LORE_DIR) -> List[str]:
    paths = _codex_md_paths(codex_dir)
    for base, ext in ((lore_dir, ".txt"), (graph_dir, ".json")):
        if os.path.isdir(base):
            for fname in sorted(os.listdir(base)):
                if fname.endswith(ext):
                    paths.append(os.path.join(base, fname))
    return paths


def validate_encoding(paths: Optional[List[str]] = None) -> List[Finding]:
    """R6 — UTF-8 estrito (ERRO); heurística de mojibake (AVISO)."""
    findings: List[Finding] = []
    for path in (paths if paths is not None else _default_encoding_paths()):
        with open(path, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(Finding(
                "encoding", "error", path, "",
                f"não decodifica como UTF-8: {exc}"))
            continue
        m = _MOJIBAKE_RE.search(text)
        if m:
            findings.append(Finding(
                "encoding", "warning", path, "",
                f"possível mojibake ('{m.group(0)}')"))
    return findings


# Tipos que registram entidade no grafo — doc `curated` desses tipos sem
# entrada em entities(.extra).json é curadoria incompleta (AVISO, R4 da 7.2).
_REGISTRABLE_TYPES = {"location", "faction", "npc", "race", "monster", "artifact"}


def validate_overrides(codex_dir: str = CODEX_DIR,
                       overrides_path: str = OVERRIDES_PATH,
                       graph_dir: str = GRAPH_DIR) -> List[Finding]:
    """Fase 7.2 — override órfão é ERRO; override em arquivo curated e doc
    curated registrável sem entidade são AVISO."""
    findings: List[Finding] = []
    overrides: dict = {}
    if os.path.isfile(overrides_path):
        with open(overrides_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            overrides = data

    parsed = _parse_codex(codex_dir)
    por_id = {str(fm.get("id", "")): (path, fm) for path, fm, _body in parsed}

    for override_id in overrides:
        if override_id not in por_id:
            findings.append(Finding(
                "overrides", "error", overrides_path, override_id,
                "override órfão: id não existe no Codex"))
        elif por_id[override_id][1].get("curated"):
            findings.append(Finding(
                "overrides", "warning", overrides_path, override_id,
                "override ignorado: arquivo é curated (100% manual)"))

    entities = _merged_entities(graph_dir)
    for path, frontmatter, _body in parsed:
        if not frontmatter.get("curated"):
            continue
        if frontmatter.get("type") not in _REGISTRABLE_TYPES:
            continue
        entity_id = str(frontmatter.get("id", ""))
        if entity_id not in entities:
            findings.append(Finding(
                "overrides", "warning", path, entity_id,
                "arquivo curated sem entidade em entities_extra.json/entities.json"))
    return findings


def validate_all(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR,
                 overrides_path: str = OVERRIDES_PATH) -> List[Finding]:
    """Roda todos os validadores; aplica whitelist; ordena por
    (severity, validator, path, entity_id) — erros primeiro."""
    findings: List[Finding] = []
    findings.extend(validate_frontmatter(codex_dir))
    findings.extend(validate_ids(codex_dir, graph_dir))
    findings.extend(validate_references(codex_dir, graph_dir))
    findings.extend(validate_aliases(graph_dir))
    findings.extend(validate_visibility(codex_dir, graph_dir))
    findings.extend(validate_overrides(codex_dir, overrides_path, graph_dir))
    if codex_dir == CODEX_DIR and graph_dir == GRAPH_DIR:
        findings.extend(validate_encoding())
    else:
        paths = _codex_md_paths(codex_dir)
        if os.path.isdir(graph_dir):
            paths += [os.path.join(graph_dir, f) for f in sorted(os.listdir(graph_dir))
                      if f.endswith(".json")]
        findings.extend(validate_encoding(paths))
    findings = [
        f for f in findings if (f.validator, f.entity_id) not in _LINT_WHITELIST
    ]
    findings.sort(key=lambda f: (f.severity, f.validator, f.path, f.entity_id))
    return findings
