"""
migrate_lore_nova.py — Migra o lore reescrito de `lore_nova/*.txt` (Codex Omnia /
Valoria) para o Codex estruturado (`data/codex/**/*.md`) + `data/graph/entities.json`.

Spec: specs/SPEC-001-fase-2.5-codex-world-state.md §3 (tabela fonte → destino).

ATENÇÃO: rodar este script REGERA data/codex/ e data/graph/entities.json do zero.
Curadoria que SOBREVIVE à regeração (Fase 7.2):
  - `data/codex_overrides.yaml` — patches de frontmatter/corpo por id, aplicados
    no fim da geração (`apply_overrides`);
  - arquivos `.md` com `curated: true` no frontmatter — nunca apagados/reescritos
    (entidade correspondente vive em `entities_extra.json`);
  - `data/graph/edges.json`, `relation_types.json`, `entities_extra.json` e
    `components.json` — curados à mão, NUNCA tocados por este script.
Qualquer outra edição manual nos `.md` gerados é sobrescrita.

Uso:  uv run python scripts/migrate_lore_nova.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.content_validator import NPC_SECRET_LABELS  # noqa: E402 — lista compartilhada (7.3)

LORE_DIR = "lore_nova"
CODEX_DIR = os.path.join("data", "codex")
GRAPH_DIR = os.path.join("data", "graph")

# Palavras descartadas nos slugs (artigos/preposições) — "A LEGIÃO DE FERRO" -> legiao_ferro
_STOPWORDS = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "um", "uma"}

# Macro-regiões canônicas: slug (pós-stopwords) -> id final.
# Skallgard e o Ermo Branco são UM bloco no lore -> uma entidade `skallgard`
# (alias "Ermo Branco"); id bate com o world_map.json atual.
_LOCATION_OVERRIDES = {
    "ermo_branco": "skallgard",
    "skallgard_ermo_branco": "skallgard",
    "cemiterio_leviatas": "costa_negra",
    "ruinas_aethelgard": "aethelgard",
    "ruinas_submersas_aethelgard": "aethelgard",
    "imperio_ophidia": "ophidia",
}

# Ids explícitos por decisão de spec (§1 Convenção de IDs)
_NPC_ID_OVERRIDES = {
    "npc_lorde_protetor_valerius": "npc_valerius",
}

# Palavras-chave para resolver cabeçalhos "LOCAL: ..." e tags soltas -> location_id
_LOCATION_KEYWORDS = [
    ("skallgard", "skallgard"),
    ("ermo branco", "skallgard"),
    ("vorr", "skallgard"),
    ("nova arcadia", "nova_arcadia"),
    ("anel dourado", "nova_arcadia"),
    ("anel de ferro", "nova_arcadia"),
    ("anel de lama", "nova_arcadia"),
    ("pantano", "pantano_melancolia"),
    ("zhur", "deserto_zhur"),
    ("sussurros", "floresta_sussurros"),
    ("xylos", "selva_xylos"),
    ("aethelgard", "aethelgard"),
    ("ophidia", "ophidia"),
    ("leviatas", "costa_negra"),
    ("costa negra", "costa_negra"),
    ("costa oeste", "costa_negra"),
    ("montanhas afiadas", "montanhas_afiadas"),
    ("pradaria", "pradaria_ruinas"),
    ("brekmar", "brekmar"),
]

_SMALL_WORDS = {"de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "no", "na", "que", "sem", "sob", "com"}


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def slugify(text: str, drop_stopwords: bool = True) -> str:
    """Slug ascii minúsculo com _; remove artigos/preposições por padrão."""
    text = _strip_accents(text).lower()
    words = re.findall(r"[a-z0-9]+", text)
    if drop_stopwords:
        kept = [w for w in words if w not in _STOPWORDS]
        words = kept or words  # nunca devolve vazio
    return "_".join(words)


def smart_title(text: str) -> str:
    """'GRUM — TAVERNEIRO' -> 'Grum — Taverneiro' preservando conectivos minúsculos."""
    def fix_word(w: str, first: bool) -> str:
        lw = w.lower()
        if not first and lw in _SMALL_WORDS:
            return lw
        return lw[:1].upper() + lw[1:]

    parts = []
    for i, word in enumerate(text.split(" ")):
        if not word:
            continue
        # preserva pontuação colada (parênteses, travessão fica como token próprio)
        m = re.match(r"^(\W*)(.*?)(\W*)$", word, re.UNICODE)
        pre, core, post = m.groups()
        parts.append(pre + (fix_word(core, i == 0) if core else "") + post)
    return " ".join(parts)


def resolve_location(text: str) -> Optional[str]:
    plain = _strip_accents(text).lower()
    for keyword, loc_id in _LOCATION_KEYWORDS:
        if keyword in plain:
            return loc_id
    return None


@dataclass
class Block:
    categoria: str
    tags: List[str]
    title: str
    body: str
    section: str = ""  # cabeçalho ####/LOCAL: vigente quando o bloco começou


_DIVIDER_RE = re.compile(r"^\s*(#{4,}|={4,}|-{3,})\s*$")


def parse_categoria_blocks(path: str) -> List[Block]:
    """Divide um arquivo em blocos [CATEGORIA: X] / [TAGS: ...] / TÍTULO / corpo."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    blocks: List[Block] = []
    current_section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\[CATEGORIA:\s*(.+?)\]\s*$", line)
        if not m:
            # rastreia cabeçalhos de seção fora de blocos (#### NOME #### / LOCAL: X)
            if _DIVIDER_RE.match(line) and i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt and not nxt.startswith("["):
                    current_section = nxt
            elif line.strip().upper().startswith("LOCAL:"):
                current_section = line.strip()
            i += 1
            continue

        categoria = m.group(1).strip()
        block_section = current_section  # seção vigente QUANDO o bloco começou
        i += 1
        tags: List[str] = []
        if i < len(lines):
            mt = re.match(r"^\[TAGS:\s*(.+?)\]\s*$", lines[i])
            if mt:
                tags = [t.strip() for t in mt.group(1).split(",") if t.strip()]
                i += 1
        # título = primeira linha não vazia (pula notas de referência "(JÁ EM ...)")
        while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("(")):
            i += 1
        title = lines[i].strip() if i < len(lines) else ""
        i += 1
        # corpo até o próximo marcador de entrada — rastreando cabeçalhos
        # ####/==== de seção no meio do arquivo (valem para os blocos SEGUINTES).
        # BUG histórico (achado no playtest da Fase 5): parar SÓ em [CATEGORIA:
        # fazia o último bloco [CATEGORIA:] de creatures.txt (OS GIGANTES) engolir
        # TODOS os [CRIATURA:] seguintes até o EOF — o bestiário inteiro (incl. o
        # Verme-Primordial, segredo) vazava para um único doc público de 1600
        # linhas. Também parar em [CRIATURA:/MATERIAL:/ITEM: fecha o bloco no lugar
        # certo (esses marcadores nunca aparecem no CORPO de um [CATEGORIA:]).
        body_lines: List[str] = []
        while i < len(lines) and not re.match(r"^\[(CATEGORIA|CRIATURA|MATERIAL|ITEM):", lines[i]):
            stripped = lines[i].strip()
            if re.match(r"^(#{4,}|={4,})$", stripped) and i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt and not nxt.startswith("["):
                    current_section = nxt
            body_lines.append(lines[i])
            i += 1
        # remove lixo de fim de bloco (divisores + cabeçalho da PRÓXIMA seção)
        while body_lines:
            last = body_lines[-1].strip()
            if not last or _DIVIDER_RE.match(last):
                body_lines.pop()
            elif len(body_lines) >= 2 and _DIVIDER_RE.match(body_lines[-2].strip()):
                # linha de cabeçalho entre divisores (ex.: FACÇÕES DE SKALLGARD)
                body_lines.pop()
            else:
                break
        blocks.append(Block(categoria, tags, title, "\n".join(body_lines).strip(), block_section))
    return blocks


# Clusters de reveal da timeline que o narrador público NÃO deve vazar (já protegidos em
# lore_nova/secrets.txt como `secret`). Cada cluster = (frase_inicial, frase_final): os
# parágrafos do que contém a inicial ATÉ o que contém a final (inclusive) viram `hidden`.
# Frases já em minúsculo e SEM acento (comparação contra `_strip_accents(...).lower()`).
# Curadoria explícita e revisável — como eras 6/7 não têm divisores `---` internos, a
# granularidade tem de ser por parágrafo, não por era inteira. Ver plano da ingestão.
_TIMELINE_HIDDEN_CLUSTERS = [
    # Era 5: o aprendiz destrói Aethelgard e vira o Arauto da Névoa
    ("em aethelgard, o aprendiz havia parado de subir",
     "que nunca mais consegue produzir linguagem"),
    # Era 5: despertar do Rei Subterrâneo (queda do Reino Anão)
    ("nas profundezas das montanhas afiadas, os anoes haviam descido longe demais",
     "algo que escolheu ficar onde voce nao pode mais voltar"),
    # Era 6: pacto Valerius <-> Daruun (consumir a família / Código de Ferro)
    ("daruun nao buscou valerius",
     "a primeira consequencia visivel do pacto"),
    # Era 7: despertar da Rede Carmesim sob Skallgard
    ("no norte, algo diferente estava acontecendo",
     "o que acontece se a chama se apagar"),
]


@dataclass
class TimelineSection:
    era: int
    era_title: str
    seq: int          # índice da subseção dentro da era (1-based)
    body: str
    visibility: str   # "public" | "hidden"


def _split_paragraphs(era_body: List[str]) -> List[str]:
    """Parágrafos de uma era: linhas em branco e divisores `---` separam; divisor é descartado."""
    paras: List[str] = []
    cur: List[str] = []
    for ln in era_body:
        if _DIVIDER_RE.match(ln.strip()) or not ln.strip():
            if cur:
                paras.append("\n".join(cur).strip())
                cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append("\n".join(cur).strip())
    return [p for p in paras if p]


def parse_timeline(path: str) -> List[TimelineSection]:
    """Divide timeline_completa.txt em docs por era (`ERA N — …`) e visibilidade.

    Prosa, não formato `[CATEGORIA:]`. Preâmbulo antes de "ERA 0" é descartado. Dentro de
    cada era os parágrafos são agrupados em runs contíguos de mesma visibilidade — os
    trechos cobertos por `_TIMELINE_HIDDEN_CLUSTERS` viram `hidden`, o resto `public`.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    era_re = re.compile(r"^ERA\s+(\d+)\s+—\s+(.+?)\s*$")
    era_starts: List[Tuple[int, int, str]] = []  # (line_idx, era_num, era_title)
    for idx, line in enumerate(lines):
        m = era_re.match(line)
        if m:
            era_starts.append((idx, int(m.group(1)), m.group(2).strip()))

    sections: List[TimelineSection] = []
    for i, (start, era_num, era_title) in enumerate(era_starts):
        end = era_starts[i + 1][0] if i + 1 < len(era_starts) else len(lines)
        paras = _split_paragraphs(lines[start + 1:end])
        plains = [_strip_accents(p).lower() for p in paras]

        # marca parágrafos hidden por cluster (start_ph .. end_ph, inclusive)
        hidden = [False] * len(paras)
        for start_ph, end_ph in _TIMELINE_HIDDEN_CLUSTERS:
            active = False
            for j, plain in enumerate(plains):
                if not active and start_ph in plain:
                    active = True
                if active:
                    hidden[j] = True
                    if end_ph in plain:
                        break

        # emite runs contíguos de mesma visibilidade como 1 doc cada
        seq = 0
        run: List[str] = []
        run_hidden: Optional[bool] = None
        for p, h in zip(paras, hidden):
            if run_hidden is None or h == run_hidden:
                run.append(p)
                run_hidden = h
            else:
                seq += 1
                sections.append(TimelineSection(
                    era_num, era_title, seq, "\n\n".join(run),
                    "hidden" if run_hidden else "public"))
                run = [p]
                run_hidden = h
        if run:
            seq += 1
            sections.append(TimelineSection(
                era_num, era_title, seq, "\n\n".join(run),
                "hidden" if run_hidden else "public"))
    return sections


def parse_marker_entries(path: str, marker: str) -> List[Tuple[str, str, str, str]]:
    """Extrai entradas `[<marker>: Nome]` -> (nome, corpo, local_header, secao).

    Usado por creatures.txt ([CRIATURA:]) e items.txt ([MATERIAL:]/[ITEM:]).
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    entries: List[Tuple[str, str, str, str]] = []
    current_local = ""
    current_section = ""
    i = 0
    entry_re = re.compile(r"^\[" + marker + r":\s*(.+?)\]\s*(\[.*\])?\s*$")
    while i < len(lines):
        line = lines[i]
        if line.strip().upper().startswith("LOCAL:"):
            current_local = line.strip()
            current_section = ""
            i += 1
            continue
        msec = re.match(r"^=+\s*([^=]+?)\s*=+$", line.strip())
        if msec:
            current_section = msec.group(1).strip()
            i += 1
            continue
        m = entry_re.match(line)
        if not m:
            i += 1
            continue
        name = m.group(1).strip()
        suffix = (m.group(2) or "").strip()
        i += 1
        body_lines: List[str] = []
        while i < len(lines):
            nxt = lines[i]
            if (nxt.startswith("[") and re.match(r"^\[(CRIATURA|MATERIAL|ITEM|CATEGORIA)", nxt)) \
                    or nxt.strip().upper().startswith("LOCAL:") \
                    or re.match(r"^=+\s*[^=]+?\s*=+$", nxt.strip()) \
                    or _DIVIDER_RE.match(nxt):
                break
            body_lines.append(nxt)
            i += 1
        body = "\n".join(body_lines).strip()
        if suffix:
            body = f"{suffix}\n{body}"
        entries.append((name, body, current_local, current_section))
    return entries


# ---------------------------------------------------------------------------
# Escrita do Codex
# ---------------------------------------------------------------------------

def write_codex_file(folder: str, frontmatter: dict, body: str) -> str:
    os.makedirs(os.path.join(CODEX_DIR, folder), exist_ok=True)
    path = os.path.join(CODEX_DIR, folder, f"{frontmatter['id']}.md")
    _dump_md(path, frontmatter, body)
    return path


def _dump_md(path: str, frontmatter: dict, body: str) -> None:
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False, width=100).strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{fm}\n---\n\n{body}\n")


def _parse_md(path: str) -> Tuple[dict, str]:
    """(frontmatter, corpo) de um .md do Codex; frontmatter quebrado -> ({}, "")."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, ""
    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        return {}, ""
    return frontmatter, parts[2].strip()


# ---------------------------------------------------------------------------
# Segredos de NPC (Fase 7.3)
# ---------------------------------------------------------------------------

def split_npc_secrets(body: str) -> Tuple[str, str]:
    """Divide o corpo de um NPC em (publico, secreto) por rótulo de parágrafo.

    Parágrafo = bloco separado por linha em branco. Rótulo = texto antes do
    primeiro ':' na primeira linha do bloco, normalizado via _strip_accents +
    casefold, comparado contra NPC_SECRET_LABELS (content_validator — lista
    compartilhada com o lint anti-regressão). Sem rótulo (linha sem ':') =
    público. Título '# ...' fica no público.
    """
    publicos: List[str] = []
    secretos: List[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        if not paragraph.strip():
            continue
        first = paragraph.strip().splitlines()[0]
        rotulo = ""
        if ":" in first and not first.lstrip().startswith("#"):
            rotulo = _strip_accents(first.split(":", 1)[0]).casefold().strip()
        if rotulo in NPC_SECRET_LABELS:
            secretos.append(paragraph.strip())
        else:
            publicos.append(paragraph.strip())
    return "\n\n".join(publicos), "\n\n".join(secretos)


# ---------------------------------------------------------------------------
# Curadoria migration-safe (Fase 7.2)
# ---------------------------------------------------------------------------

OVERRIDES_PATH = os.path.join("data", "codex_overrides.yaml")


def is_curated(path: str) -> bool:
    """True se o frontmatter tem `curated: true` (delete loop pula o arquivo)."""
    try:
        frontmatter, _body = _parse_md(path)
    except Exception:
        return False
    return bool(frontmatter.get("curated"))


def load_overrides(path: str = OVERRIDES_PATH) -> dict:
    """Lê data/codex_overrides.yaml -> {id: patch}. Ausente/vazio -> {}."""
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _codex_paths_by_id(codex_dir: str) -> Dict[str, str]:
    """id -> path; write_codex_file garante nome do arquivo == id (lint 7.1 valida)."""
    mapping: Dict[str, str] = {}
    for root, _dirs, files in os.walk(codex_dir):
        for fname in files:
            if fname.endswith(".md"):
                mapping[fname[:-3]] = os.path.join(root, fname)
    return mapping


def apply_overrides(entities: Dict[str, dict], overrides: dict,
                    codex_dir: str = CODEX_DIR) -> List[str]:
    """Aplica patches nos .md gerados e no dict de entidades.

    Precedência: gerado < override. Arquivo `curated: true` nunca recebe
    override (lint 7.2 acusa AVISO). Retorna ids não encontrados no Codex
    (o main imprime; lint acusa como ERRO).
    """
    orfaos: List[str] = []
    paths = _codex_paths_by_id(codex_dir)
    for override_id in sorted(overrides):
        patch = overrides[override_id] or {}
        path = paths.get(override_id)
        if path is None:
            orfaos.append(override_id)
            continue
        frontmatter, body = _parse_md(path)
        if frontmatter.get("curated"):
            continue

        if "aliases" in patch:
            frontmatter["aliases"] = list(patch["aliases"])
        if "tags_extra" in patch:
            tags = list(frontmatter.get("tags") or [])
            for tag in patch["tags_extra"]:
                if tag not in tags:
                    tags.append(tag)
            frontmatter["tags"] = tags
        if "visibility" in patch:
            frontmatter["visibility"] = patch["visibility"]
        if "related_entities" in patch:
            frontmatter["related_entities"] = list(patch["related_entities"])
        if "append_body" in patch:
            body = f"{body}\n\n{str(patch['append_body']).strip()}"
        _dump_md(path, frontmatter, body)

        ent = entities.get(override_id)
        if ent is not None:
            if "aliases" in patch:
                ent["aliases"] = list(patch["aliases"])
            if "visibility" in patch:
                ent["visibility"] = patch["visibility"]
            if "tags_extra" in patch:
                etags = list(ent.get("tags") or [])
                for tag in patch["tags_extra"]:
                    slug = slugify(tag, drop_stopwords=False)
                    if slug not in etags:
                        etags.append(slug)
                ent["tags"] = etags
    return orfaos


def unique_id(base: str, taken: set, fallback_suffix: str = "") -> str:
    if base not in taken:
        return base
    if fallback_suffix and f"{base}_{fallback_suffix}" not in taken:
        return f"{base}_{fallback_suffix}"
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def main() -> Dict[str, dict]:
    # regenera do zero (idempotente por substituição total). Apaga só os .md —
    # rmtree do diretório falha no Windows/OneDrive (lock de sync).
    # Arquivos `curated: true` são manuais e sobrevivem (Fase 7.2).
    if os.path.isdir(CODEX_DIR):
        for root, _dirs, files in os.walk(CODEX_DIR):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                if is_curated(path):
                    continue
                os.remove(path)
    os.makedirs(GRAPH_DIR, exist_ok=True)

    entities: Dict[str, dict] = {}

    def register(entity_id: str, etype: str, name: str, tags: List[str],
                 visibility: str = "public", aliases: Optional[List[str]] = None) -> None:
        entities[entity_id] = {
            "id": entity_id,
            "type": etype,
            "name": name,
            "aliases": aliases or [],
            "tags": [slugify(t, drop_stopwords=False) for t in tags],
            "visibility": visibility,
            "components": {},
        }

    # --- locations.txt — 1 md por macro-região ---------------------------------
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "locations.txt")):
        raw = slugify(blk.tags[0]) if blk.tags else slugify(blk.title)
        loc_id = _LOCATION_OVERRIDES.get(raw, raw)
        name = smart_title(blk.title.split("—")[0].strip())
        aliases = []
        if loc_id == "skallgard":
            name = "Skallgard e o Ermo Branco"
            aliases = ["Skallgard", "Ermo Branco"]
        register(loc_id, "location", name, blk.tags, aliases=aliases)
        write_codex_file("locations", {
            "id": loc_id, "type": "location", "name": name,
            "aliases": aliases, "tags": blk.tags, "visibility": "public",
        }, f"# {blk.title}\n\n{blk.body}")

    # --- factions.txt — 1 md por fação ------------------------------------------
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "factions.txt")):
        fac_id = unique_id(slugify(blk.title), set(entities))
        name = smart_title(blk.title)
        region = resolve_location(blk.section or " ".join(blk.tags))
        related = [region] if region else []
        register(fac_id, "faction", name, blk.tags)
        write_codex_file("factions", {
            "id": fac_id, "type": "faction", "name": name, "aliases": [],
            "tags": blk.tags, "visibility": "public",
            "related_entities": related,
        }, f"# {blk.title}\n\n{blk.body}")

    # --- npcs.txt — 1 md por NPC (inclui demônios e dragões) --------------------
    # Fase 7.3: parágrafos de rótulo secreto (História real, Motivação real...)
    # saem do doc público e viram doc paralelo `npc_secret` com visibility hidden.
    n_npcs = n_npc_segredos = 0
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "npcs.txt")):
        short = blk.title.split("—")[0].strip()
        npc_id = _NPC_ID_OVERRIDES.get(
            f"npc_{slugify(short, drop_stopwords=False)}",
            f"npc_{slugify(short, drop_stopwords=False)}",
        )
        npc_id = unique_id(npc_id, set(entities))
        name = smart_title(short)
        extra_tags = list(blk.tags)
        if "DEMÔNIO" in blk.categoria:
            extra_tags.append("demonio")
        elif "DRAGÃO" in blk.categoria:
            extra_tags.append("dragao")
        region = resolve_location(" ".join(blk.tags) + " " + blk.section)
        register(npc_id, "npc", name, extra_tags)
        publico, secreto = split_npc_secrets(blk.body)
        write_codex_file("npcs", {
            "id": npc_id, "type": "npc", "name": name, "aliases": [],
            "tags": extra_tags, "visibility": "public",
            "related_entities": [region] if region else [],
        }, f"# {blk.title}\n\n{publico}")
        n_npcs += 1
        if secreto:
            # NÃO registra entidade (mesmo padrão de secrets/ e timeline/)
            write_codex_file(os.path.join("npcs", "segredos"), {
                "id": f"{npc_id}_segredo", "type": "npc_secret",
                "name": f"{name} — Segredos", "aliases": [],
                "tags": extra_tags, "visibility": "hidden",
                "related_entities": [npc_id],
            }, f"# {blk.title} — O QUE NÃO É DITO\n\n{secreto}")
            n_npc_segredos += 1
    print(f"NPCs: {n_npcs}, com doc de segredo: {n_npc_segredos}")

    # --- races.txt — 1 md por raça ----------------------------------------------
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "races.txt")):
        race_id = unique_id(f"race_{slugify(blk.title)}", set(entities))
        name = smart_title(blk.title.split("—")[0].strip())
        register(race_id, "race", name, blk.tags)
        write_codex_file("races", {
            "id": race_id, "type": "race", "name": name, "aliases": [],
            "tags": blk.tags, "visibility": "public",
        }, f"# {blk.title}\n\n{blk.body}")

    # --- creatures.txt — primordiais (blocos) + [CRIATURA:] --------------------
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "creatures.txt")):
        mon_id = unique_id(f"mon_{slugify(blk.title)}", set(entities))
        name = smart_title(blk.title)
        register(mon_id, "monster", name, blk.tags + ["primordial"])
        write_codex_file("monsters", {
            "id": mon_id, "type": "monster", "name": name, "aliases": [],
            "tags": blk.tags + ["primordial"], "visibility": "public",
        }, f"# {blk.title}\n\n{blk.body}")

    for name, body, local, section in parse_marker_entries(
            os.path.join(LORE_DIR, "creatures.txt"), "CRIATURA"):
        loc_id = resolve_location(local) or ""
        base = f"mon_{slugify(name, drop_stopwords=False)}"
        mon_id = unique_id(base, set(entities), fallback_suffix=loc_id)
        tags = [t for t in (loc_id, slugify(section, drop_stopwords=False)) if t]
        register(mon_id, "monster", name, tags)
        write_codex_file("monsters", {
            "id": mon_id, "type": "monster", "name": name, "aliases": [],
            "tags": tags, "visibility": "public",
            "related_entities": [loc_id] if loc_id else [],
        }, f"# {name}\n\n{body}")

    # --- items.txt — artefatos únicos viram entidade; resto agrupa por região ---
    grouped_items: Dict[str, List[str]] = {}
    for marker in ("MATERIAL", "ITEM"):
        for name, body, local, section in parse_marker_entries(
                os.path.join(LORE_DIR, "items.txt"), marker):
            loc_id = resolve_location(local) or "diversos"
            if marker == "ITEM" and "ARTEFATO" in body.split("\n", 1)[0].upper():
                body_rest = body.split("\n", 1)[1] if "\n" in body else ""
                art_id = unique_id(f"art_{slugify(name)}", set(entities), fallback_suffix=loc_id)
                register(art_id, "artifact", name, [loc_id, "artefato_unico"])
                write_codex_file("items", {
                    "id": art_id, "type": "artifact", "name": name, "aliases": [],
                    "tags": [loc_id, "artefato_unico"], "visibility": "public",
                    "related_entities": [loc_id] if loc_id != "diversos" else [],
                }, f"# {name} [ARTEFATO ÚNICO]\n\n{body_rest.strip()}")
            else:
                kind = "MATERIAL" if marker == "MATERIAL" else "ITEM"
                grouped_items.setdefault(loc_id, []).append(f"## [{kind}] {name}\n\n{body}")
    for loc_id, parts in grouped_items.items():
        write_codex_file("items", {
            "id": f"story_itens_{loc_id}", "type": "items", "name": f"Itens e materiais — {loc_id}",
            "aliases": [], "tags": [loc_id], "visibility": "public",
            "related_entities": [loc_id] if loc_id != "diversos" else [],
        }, "\n\n---\n\n".join(parts))

    # --- secrets.txt — 1 md por segredo, visibility: secret ---------------------
    used_secret_ids: set = set()
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "secrets.txt")):
        title_core = blk.title.split("—", 1)[-1].strip()
        sec_id = unique_id(f"secret_{slugify(title_core)[:60].rstrip('_')}", used_secret_ids | set(entities))
        used_secret_ids.add(sec_id)
        write_codex_file("secrets", {
            "id": sec_id, "type": "secret", "name": smart_title(title_core),
            "aliases": [], "tags": blk.tags, "visibility": "secret",
        }, f"# {blk.title}\n\n{blk.body}")

    # --- faction_perspectives.txt — 1 md por bloco, visibility: hidden ----------
    used_persp: set = set()
    fac_by_slug = {e["id"]: e for e in entities.values() if e["type"] == "faction"}
    for blk in parse_categoria_blocks(os.path.join(LORE_DIR, "faction_perspectives.txt")):
        fac_tag = next((t.split(":", 1)[1].strip() for t in blk.tags if t.lower().startswith("facção")), "")
        sobre = next((t.split(":", 1)[1].strip() for t in blk.tags if t.lower().startswith("sobre")), "")
        fac_id = slugify(fac_tag) if fac_tag else ""
        pid = unique_id(f"story_perspectiva_{fac_id or 'geral'}_{slugify(sobre, drop_stopwords=False) or 'geral'}", used_persp)
        used_persp.add(pid)
        write_codex_file(os.path.join("factions", "perspectivas"), {
            "id": pid, "type": "perspective", "name": smart_title(blk.title),
            "aliases": [], "tags": blk.tags, "visibility": "hidden",
            "related_entities": [fac_id] if fac_id in fac_by_slug else [],
        }, f"# {blk.title}\n\n{blk.body}")

    # --- rumors.txt / daily_life.txt — agrupados por região ---------------------
    for fname, folder, prefix, nome in (
        ("rumors.txt", "rumors", "story_rumores", "Rumores"),
        ("daily_life.txt", "world_story", "story_cotidiano", "Cotidiano"),
    ):
        grouped: Dict[str, List[str]] = {}
        for blk in parse_categoria_blocks(os.path.join(LORE_DIR, fname)):
            loc_id = resolve_location(" ".join(blk.tags)) or "diversos"
            grouped.setdefault(loc_id, []).append(
                f"## {blk.title}\n[TAGS: {', '.join(blk.tags)}]\n\n{blk.body}")
        for loc_id, parts in grouped.items():
            write_codex_file(folder, {
                "id": f"{prefix}_{loc_id}", "type": "world_story",
                "name": f"{nome} — {loc_id}", "aliases": [], "tags": [loc_id],
                "visibility": "public",
                "related_entities": [loc_id] if loc_id != "diversos" else [],
            }, "\n\n---\n\n".join(parts))

    # --- timeline_completa.txt — 1 md por subseção de era (NÃO registra entidade) ---
    timeline_path = os.path.join(LORE_DIR, "timeline_completa.txt")
    if os.path.isfile(timeline_path):
        used_timeline: set = set()
        for sec in parse_timeline(timeline_path):
            head_words = "_".join(sec.body.split()[:6])
            base = f"timeline_e{sec.era}_{sec.seq}_{slugify(head_words, drop_stopwords=False)}"[:70].rstrip("_")
            tid = unique_id(base, used_timeline)
            used_timeline.add(tid)
            body = sec.body
            if sec.seq == 1:
                body = f"# ERA {sec.era} — {sec.era_title}\n\n{body}"
            write_codex_file("timeline", {
                "id": tid, "type": "timeline",
                "name": f"Era {sec.era} — {smart_title(sec.era_title)} ({sec.seq})",
                "aliases": [], "tags": ["timeline", f"era_{sec.era}"],
                "visibility": sec.visibility,
            }, body)

    # --- curadoria migration-safe (Fase 7.2) --------------------------------------
    orfaos = apply_overrides(entities, load_overrides(), CODEX_DIR)
    for override_id in orfaos:
        print(f"⚠️ override órfão: '{override_id}' não existe no Codex gerado")

    # --- entities.json -----------------------------------------------------------
    with open(os.path.join(GRAPH_DIR, "entities.json"), "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)

    return entities


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ents = main()
    by_type: Dict[str, int] = {}
    for e in ents.values():
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    total_md = sum(len(files) for _, _, files in os.walk(CODEX_DIR))
    print(f"Entidades: {len(ents)} {by_type}")
    print(f"Arquivos de codex: {total_md}")
