"""SPEC-349 — gera, a partir da ficha de identidade (fonte única), os derivados de uma região:

- ``data/codex/monsters/<id>.md`` (curated, R17) para fichas ``nova``/``reinventada``;
- ``docs/arte/bestiario-349/<regiao>.md`` (R19);
- entidades ``monster`` em ``data/graph/entities_extra.json``;
- campos de TEXTO dos slots reinventados/adotados em ``data/bestiary.json`` (R3: name,
  description, appearance, attacks[].name, action_hint, substitui_generico, codex_id) e
  ``appearance`` de toda ficha cujo id já exista no bestiário (R18).

Números, Cartas e ``tactical_profile.padrao`` NÃO saem daqui (Etapa 5). Uso:
``bash scripts/dev/py.sh scripts/bestiario/gerar_docs.py --regiao nova_arcadia``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import bestiary_lint as bl  # noqa: E402

CODEX_MONSTERS = ROOT / "data" / "codex" / "monsters"
ARTE_DIR = ROOT / "docs" / "arte" / "bestiario-349"
ENTITIES_EXTRA = ROOT / "data" / "graph" / "entities_extra.json"
BESTIARY = ROOT / "data" / "bestiary.json"

REGIOES_NOME = {"nova_arcadia": "Nova Arcádia"}
PALETA = {
    "nova_arcadia": (
        "**Nova Arcádia** — cidade em três anéis (Lama, Ferro, Dourado) sobre o pântano do campo "
        "de batalha final contra Malagor; lama oleosa, névoa, armaduras de várias eras afundadas. "
        "Luz e paleta: verde-oliva doente, cinza-lodo, névoa leitosa, pontos de Éter azul-pálido; "
        "fuligem e laranja de fundição no Anel de Ferro; obsidiana que não reflete nada no Dourado."
    )
}
HABITAT_NOME = {
    "nova_arcadia": "Nova Arcádia",
    "na_anel_dourado": "Anel Dourado",
    "na_anel_ferro": "Anel de Ferro",
    "na_anel_lama": "Anel de Lama",
}

# §0.1–§0.2 do BESTIARIO_VALORIA_ARTE.md (doc base não versionado, D9): copiado aqui.
ESTILO = """intricate etched illustration, dense fine-line crosshatching and stippled ink texture
under muted wash colour, like a hand-engraved plate; palette of umber, rust, ochre,
soot black, bruised violet and tarnished teal; low warm lantern light or cold ambient
light; no glossy digital render, no photorealism; dark medieval material culture
(hand-forged iron, leather, wool, rope, brass, copper); the creature is embedded in a
lived-in Valorian environment that tells a small story"""
EXCLUSOES = """no text, no logo, no watermark, no graphic gore, no sexualized presentation,
no photorealism, no firearms, no tricorn hats or frock coats, no likeness to
The Witcher, Warhammer, Lord of the Rings, Elden Ring, Bloodborne, Dark Souls or
Pirates of the Caribbean creatures, no tentacle-bearded ghost-captain archetype,
no caricature, no cute cartoon proportions"""
REGRAS = """- **Inquietante, não gore.** O horror vem do *errado*: articulações que dobram para o
  lado errado, olhos sábios demais, simetria impossível, silêncio, escala. Feridas
  podem aparecer, mas sem vísceras explícitas.
- **O Abismo não é fogo do inferno.** É entropia: ferrugem, dissolução, peso, silêncio,
  tempo quebrado, apodrecimento. Evite chifres-e-tridente, pele vermelha, asas de
  morcego genéricas.
- **Éter** é a magia residual do mundo. Visualmente: luz fria **azul-esverdeada ou
  violeta**, fosca, que parece "molhada", nunca neon. Éter cristalizado = cristal
  turvo que brilha por dentro.
- **Escala sempre legível.** Inclua uma referência humana, uma ferramenta, uma porta,
  para que o tamanho se leia (toda Composição abaixo traz uma).
- **A corrupção fica no corpo.** Referência de acerto do dono: os Lycans da Praga dos
  Ossos — placas ósseas sobre músculo exposto. Anatomia concreta: material, partes, cor, luz."""


def _doc(regiao: str) -> dict:
    p = bl.FICHAS_DIR / f"{regiao}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _fam_nome(doc: dict, ficha: dict) -> str:
    return (doc.get("familias_em_jogo") or {}).get(ficha.get("familia"), ficha.get("familia", ""))


def _one_line(text: str) -> str:
    return " ".join(str(text or "").split())


# ------------------------------------------------------------------ Codex
def codex_md(doc: dict, f: dict) -> str:
    regiao = doc["regiao"]
    fam = f["familia"]
    tags = [regiao, fam]
    related = list(dict.fromkeys([regiao, *(f.get("related_entities") or f.get("habitat") or [])]))
    fm = {
        "id": f["id"],
        "type": "monster",
        "name": f["nome"],
        "aliases": [],
        "tags": tags,
        "visibility": "public",
        "curated": True,
        "related_entities": related,
    }
    head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).rstrip()
    body = [
        f"# {f['nome']}",
        "",
        f"Tipo: {_fam_nome(doc, f)} | Perigo: {f.get('perigo', 'Médio')}",
        _one_line(f["lore"]),
        "",
        f"Aparência: {_one_line(f['aparencia'])}",
        "",
        f"Como se luta: {_one_line(f['como_se_luta'])}",
        "",
    ]
    return f"---\n{head}\n---\n\n" + "\n".join(body)


# ------------------------------------------------------------------ Arte
def arte_md(doc: dict, fichas: list[dict]) -> str:
    regiao = doc["regiao"]
    # ondas 2+ trazem nome, paleta e nomes de habitat na própria ficha (SPEC-359)
    nome_reg = doc.get("nome_regiao") or REGIOES_NOME.get(regiao, regiao)
    out = [
        f"# Bestiário de Valoria — onda {doc.get('onda')}: {nome_reg} ({doc.get('spec', 'SPEC-349')})",
        "",
        "> Gerado por `scripts/bestiario/gerar_docs.py` a partir de "
        f"`data/bestiario/fichas/{regiao}.yaml` (fonte única). Não editar à mão.",
        "> Formato de `docs/arte/BESTIARIO_VALORIA_ARTE.md` §0.4: **Visual**, **Composição** e "
        "**Evitar** (obrigatório aqui — é a guarda anticlichê).",
        "",
        "## 0. Estilo (cole antes de qualquer prompt)",
        "",
        "```text",
        ESTILO,
        "```",
        "",
        "**Exclusões globais** (negative prompt):",
        "",
        "```text",
        EXCLUSOES,
        "```",
        "",
        "### Regras de horror em Valoria",
        "",
        REGRAS,
        "",
        "### Paleta e ambiente da região",
        "",
        _one_line(doc.get("paleta")) or PALETA.get(regiao, nome_reg),
        "",
    ]
    fams = list((doc.get("familias_em_jogo") or {}).keys())
    titulos = {
        "corpo_reescrito": "Corpos reescritos (Reescritos)",
        "besta_entropia": "Bestas da entropia (Bestas Tortas)",
        "humanoide_preco": "Humanoides que pagaram o preço (Cobrados)",
        "demonio_encarnado": "Crias de apetite (demônios encarnados)",
    }
    n = 1
    for fam in fams:
        grupo = [f for f in fichas if f["familia"] == fam]
        if not grupo:
            continue
        out += [f"## {n}. {titulos.get(fam, fam)}", ""]
        n += 1
        for f in grupo:
            hab_nome = {**HABITAT_NOME, **(doc.get("habitat_nome") or {})}
            hab = ", ".join(hab_nome.get(h, h) for h in f.get("habitat") or [])
            status = {"reinventada": " · slot reinventado", "adotada": " · adotada da lore"}.get(
                f.get("status"), ""
            )
            arte = f.get("arte") or {}
            out += [
                f"### {f['nome']}",
                f"`{_fam_nome(doc, f)} · {f.get('perigo', 'Médio')} · {nome_reg} ({hab}){status}`",
                "",
                f"**Visual:** {_one_line(arte.get('visual'))}",
                f"**Composição:** {_one_line(arte.get('composicao'))}",
                f"**Evitar:** {_one_line(arte.get('evitar'))}",
                "",
            ]
    insp = [(f, i) for f in fichas for i in (f.get("inspiracao") or [])]
    out += ["## Fontes de inspiração registradas (R12)", ""]
    if not insp:
        out.append(
            "Nenhuma inspiração externa registrada nesta onda: todas as criaturas partem de âncoras de `lore_nova/`."
        )
    for f, i in insp:
        out.append(
            f"- **{f['nome']}** — {i.get('fonte')} ({i.get('referencia')}): tomou *{i.get('tomou')}*; "
            f"distância: {i.get('distancia')}"
        )
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------ grafo + bestiário
def _dump_json(path: Path, data: dict, trailing_nl: bool) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text + ("\n" if trailing_nl else ""), encoding="utf-8", newline="\n")


def update_entities(doc: dict, fichas: list[dict]) -> int:
    raw = ENTITIES_EXTRA.read_text(encoding="utf-8")
    ents = json.loads(raw)
    n = 0
    for f in fichas:
        eid = f["id"]
        if eid in ents:
            if ents[eid].get("name") != f["nome"]:
                ents[eid]["name"] = f["nome"]
                n += 1
            continue
        ents[eid] = {
            "id": eid,
            "type": "monster",
            "name": f["nome"],
            "aliases": [],
            "tags": [doc["regiao"], "bestiario", f["familia"]],
            "visibility": "public",
            "components": {},
        }
        n += 1
    _dump_json(ENTITIES_EXTRA, ents, raw.endswith("\n"))
    return n


def update_bestiary(fichas: list[dict]) -> int:
    raw = BESTIARY.read_text(encoding="utf-8")
    best = json.loads(raw)
    n = 0
    for f in fichas:
        e = best.get(f["id"])
        if e is None:
            continue
        before = json.dumps(e, ensure_ascii=False)
        e["appearance"] = _one_line(f["aparencia"])[:300]
        if f.get("status") in ("reinventada", "adotada"):
            e["name"] = f["nome"]
            e["description"] = _one_line(f["description"])
            e["substitui_generico"] = f.get("substitui_generico") or ""
            if f.get("codex_id"):
                e["codex_id"] = f["codex_id"]
            else:
                e.pop("codex_id", None)  # reinventada: a identidade é a ficha, não um doc adotado
            for atk, nome in zip(e.get("attacks") or [], f.get("ataques") or [], strict=False):
                atk["name"] = nome
            prios = (e.get("tactical_profile") or {}).get("priorities") or []
            for prio, hint in zip(prios, f.get("acoes") or [], strict=False):
                prio["action_hint"] = hint
        if json.dumps(e, ensure_ascii=False) != before:
            n += 1
    _dump_json(BESTIARY, best, raw.endswith("\n"))
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regiao", required=True)
    args = ap.parse_args(argv)
    doc = _doc(args.regiao)
    fichas = [f for f in doc.get("criaturas") or [] if bl.is_nova(f)]

    CODEX_MONSTERS.mkdir(parents=True, exist_ok=True)
    n_codex = 0
    for f in fichas:
        if f.get("status") == "adotada":
            continue  # R4: o doc do Codex da criatura adotada não é tocado
        (CODEX_MONSTERS / f"{f['id']}.md").write_text(
            codex_md(doc, f), encoding="utf-8", newline="\n"
        )
        n_codex += 1
    ARTE_DIR.mkdir(parents=True, exist_ok=True)
    (ARTE_DIR / f"{args.regiao}.md").write_text(
        arte_md(doc, fichas), encoding="utf-8", newline="\n"
    )
    n_ent = update_entities(doc, fichas)
    n_best = update_bestiary(fichas)
    print(
        f"{len(fichas)} fichas · {n_codex} docs Codex · arte · {n_ent} entidades · {n_best} entradas do bestiário"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
