"""SPEC-349 R1/§3.6: pré-preenche e valida ``data/bestiario/curadoria_legado.yaml``.

Heurística (marca cada entrada do ``data/bestiary.json``):
- ``valoria``: nome bate com doc ``monsters/`` do Codex / ``[CRIATURA:]``, ou ``faction`` é do
  grafo, ou ``origem == conflito-17`` (autoral de Valoria);
- ``generico``: nome com termo de ``[proibidos_nome]``;
- ``revisar``: o resto -> decidido em ``DECISOES`` abaixo (proposta de Terra; o revisor confirma).

Nenhum ``revisar`` sobrevive: o script falha se faltar decisão. Na dúvida, MANTER
(o dono proibiu apagar o que é de Valoria).

Uso:
``bash scripts/dev/py.sh scripts/bestiario/curadoria.py --write``.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from services import bestiary_lint as bl  # noqa: E402
from services.encounter_manifest import name_tokens  # noqa: E402

OUT = ROOT / "data" / "bestiario" / "curadoria_legado.yaml"
REVISOR = "opus-audit (independente) + coordenador"

# subclasse: unico | conceitual | generico ; (subclasse, motivo, evidencia)
U, C, G = "unico", "conceitual", "generico"
DECISOES: dict[str, tuple[str, str, str]] = {
    # --- genéricos de manual (reinventar no slot) ---
    "enemy_sentinela_ferro": (
        G,
        "Constructo genérico; o slot do Anel de Ferro pede corpo da Praga/Fornalha",
        "",
    ),
    "enemy_gargula_ferro": (G, "Gárgula é monstro de manual (proibido_nome)", ""),
    "enemy_elemental_fogo_poluido": (
        G,
        "Elemental é monstro de manual (proibido_nome); a Brasa Profunda é do Reino Subterrâneo e elemental no corpo: reinventar (coordenador 28/10)",
        "",
    ),
    "enemy_golem_lixo": (G, "Golem é monstro de manual (proibido_nome)", ""),
    "enemy_polvo_esgoto": (
        G,
        "Polvo de esgoto: clichê de ooze/horror aquático; o Polvo dos Destroços é da costa e sem física quebrada: reinventar (coordenador 28/10)",
        "",
    ),
    "enemy_mumia_de_po": (G, "Múmia é monstro de manual (proibido_nome)", ""),
    "enemy_djinn_menor": (G, "Djinn é monstro de manual (proibido_nome); marcador 'Menor'", ""),
    "enemy_verme_areia_jovem": (
        G,
        "Verme da areia: clichê; marcador 'Jovem'. A lore tem o Verme-de-Vidro para o slot",
        "lore_nova/creatures.txt:1140",
    ),
    "enemy_mimico_bau": (G, "Mímico é monstro de manual (proibido_nome)", ""),
    "enemy_basilisco_caverna": (G, "Basilisco é monstro de manual (proibido_nome)", ""),
    "enemy_troll_ponte": (G, "Troll de ponte: clichê de manual (proibido_nome)", ""),
    "enemy_wyvern_jovem": (G, "Wyvern é monstro de manual (proibido_nome); marcador 'Jovem'", ""),
    "enemy_morcego_vampiro": (
        G,
        "Vampiros são canon (Bebedores de Ferrugem), mas o morcego-vampiro gigante é de manual; o morcego segue genérico",
        "",
    ),
    "enemy_observador_menor": (G, "Observador/Gazer é monstro de manual (proibido_nome)", ""),
    "enemy_minotauro_esqueleto": (G, "Minotauro é monstro de manual (proibido_nome)", ""),
    "enemy_yeti": (G, "Yeti é monstro de manual (proibido_nome)", ""),
    "enemy_urso_coruja_mutante": (
        G,
        "Urso-coruja é o owlbear de manual; a lore tem Coruja-de-Osso/Urso-de-Espinha distintos",
        "",
    ),
    "enemy_esqueleto_mago": (
        G,
        "Esqueleto mago: clichê de manual; os mortos de Aethelgard são os Afogados",
        "",
    ),
    "enemy_golem_carne": (
        G,
        "Golem é monstro de manual (proibido_nome). ÂNCORA OBRIGATÓRIA na prosa: Silas Vane (npcs.txt:63; secrets.txt:26,134; rumors.txt:163)",
        "lore_nova/npcs.txt:63",
    ),
    "enemy_zumbi_blindado": (G, "Zumbi é monstro de manual (proibido_nome)", ""),
    "enemy_vinha_estranguladora": (
        G,
        "Planta assassina de manual; lore de Xylos usa Víbora-Flora/Hospedeiros",
        "",
    ),
    "enemy_lobo_sombrio": (
        G,
        "Lobo Sombrio (dire/shadow wolf): clichê sem ligação com a lore (lobos de Valoria: Vidro, Aurora, Pradaria)",
        "",
    ),
    "enemy_carniçal": (
        G,
        "Carniçal = ghoul de manual; Valoria tem a Carniça-Andante (outra criatura)",
        "",
    ),
    "enemy_goblin": (
        G,
        "Goblin canônico (Goblins Mineiros); slot reaproveita a criatura da lore em vez de monstro de manual genérico",
        "lore_nova/creatures.txt:348",
    ),
    "enemy_esqueleto": (G, "Esqueleto genérico sem região nem ligação com a lore", ""),
    # --- conceituais / únicos sem doc: manter ---
    "enemy_espectro_lamento": (
        C,
        "conceitual (espectro): perigo conceitual de Valoria, não se altera",
        "lore_nova/creatures.txt:140",
    ),
    # --- dono 28/10: os 5 ex-"duvida_dono" são genéricos (reinventar na onda da região) ---
    "enemy_sombra_espreitadora": (G, "dono 28/10: genérico", "0 hits em creatures.txt/codex"),
    "enemy_fantasma": (G, "dono 28/10: genérico", "lore_nova/creatures.txt:120"),
    "mon_quimera_cristal": (G, "dono 28/10: genérico", "data/bestiary.json:#"),
    "mon_ent_dormindo": (G, "dono 28/10: genérico", "data/bestiary.json:#"),
    "mon_jotun_cinza": (G, "dono 28/10: genérico", "data/bestiary.json:#"),
    "enemy_aranha_de_cristal": (
        G,
        "Chefe sem hit na lore; reinventar derivado de creatures.txt:1128",
        "lore_nova/creatures.txt:1128",
    ),
    "enemy_boss_general_escorpiao": (
        G,
        "Chefe sem nenhum hit na lore; reinventar ancorado no Escorpião-de-Cristal de Zhur",
        "data/codex/monsters/mon_escorpiao_de_cristal.md:1",
    ),
    "enemy_boss_arauto_nevoa": (U, "Arauto da Névoa é entidade da lore", "lore_nova/npcs.txt:95"),
    "enemy_gigante_gelo_norte": (
        U,
        "chefe do Norte; os Gigantes têm doc no Codex; dúvida -> manter",
        "data/codex/monsters/mon_gigantes.md:1",
    ),
    "enemy_necromante_renegado": (
        U,
        "necromantes amadores existem na lore do Anel de Lama/Pradaria; humano, dúvida -> manter",
        "lore_nova/creatures.txt:750",
    ),
    "enemy_esqueleto_legiao_antiga": (
        G,
        "Esqueleto genérico; o Afogado da Batalha (creatures.txt:630) já tem ficha mecânica, então não é adotável (D4): reinventar ancorado nos mortos da batalha",
        "lore_nova/creatures.txt:630",
    ),
    "enemy_assassino_cinzeu": (U, "Cinzéu é raça de Valoria", "lore_nova/creatures.txt:818"),
    "enemy_aranha_lobo": (
        G,
        "Aranha-lobo genérica; mon_aranha_de_pedra não passa em U9 (0 partes concretas no Codex), então reinventar",
        "lore_nova/creatures.txt:288",
    ),
    "enemy_bandido_capitao": (
        U,
        "humano, não é monstro de manual; dúvida -> manter",
        "0 hits em creatures.txt/codex (dúvida; manter)",
    ),
    "enemy_lobo_invernal": (
        G,
        "Lobo genérico de Skallgard; o Lobo-de-Vidro (creatures.txt:72) já tem ficha mecânica, então não é adotável (D4): reinventar com âncora na fauna do Norte",
        "lore_nova/creatures.txt:72",
    ),
    "enemy_bandido": (
        U,
        "humano, não é monstro de manual; dúvida -> manter",
        "lore_nova/creatures.txt:356",
    ),
    "enemy_hospedeiro_fungico": (
        U,
        "Hospedeiro é condição/povo de Valoria (colmeia de Xylos)",
        "lore_nova/creatures.txt:818",
    ),
    "enemy_garrick,_o_silenciador": (
        U,
        "nomeado do grafo (entities_extra)",
        "data/graph/entities_extra.json:843",
    ),
    "enemy_rato_peste_anel_lama": (
        U,
        "Peste e Anel de Lama são de Valoria; manter (par com Rato de Caldeira só avisa)",
        "lore_nova/creatures.txt:417",
    ),
    "mon_caranguejo_mare": (
        U,
        "criatura de lore costeira; tem doc no Codex (Caranguejo-Maré) e Caranguejeiro em creatures.txt",
        "data/codex/monsters/mon_caranguejo_mare.md:1",
    ),
}
# destino especial (adotar do Codex)
ADOCOES = {
    "enemy_horror_esgoto": "mon_coisa_do_esgoto",
    "enemy_goblin": "mon_goblins_mineiros",
    "enemy_verme_areia_jovem": "mon_verme_de_vidro",
    "enemy_vinha_estranguladora": "mon_serpente_cipo_constritora",
}
# dono 28/10: nenhuma dúvida pendente (os 5 viraram genéricos em DECISOES)
DUVIDA_DONO: dict[str, str] = {}


def _line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in line:
            return i
    return 0


def _codex_names() -> dict[tuple, str]:
    out = {}
    for p in glob.glob(str(ROOT / "data" / "codex" / "monsters" / "*.md")):
        m = re.search(r"^name: (.+)$", Path(p).read_text(encoding="utf-8"), re.M)
        if m:
            out[tuple(sorted(set(name_tokens(m.group(1)))))] = Path(p).stem
    return out


def _lore_names() -> dict[tuple, int]:
    out = {}
    for i, line in enumerate(
        (ROOT / "lore_nova" / "creatures.txt").read_text(encoding="utf-8").splitlines(), 1
    ):
        m = re.match(r"\[CRIATURA:\s*(.+?)\]", line)
        if m:
            out[tuple(sorted(set(name_tokens(m.group(1)))))] = i
    return out


def _faccoes() -> set[str]:
    ents = json.loads((ROOT / "data" / "graph" / "entities.json").read_text(encoding="utf-8"))
    ents = ents if isinstance(ents, list) else list(ents.values())
    return {e["id"] for e in ents if isinstance(e, dict) and e.get("type") == "faction"}


def _hits(termo: str) -> int:
    pat = bl._fold(termo)
    n = 0
    files = [
        ROOT / "lore_nova" / "creatures.txt",
        *map(Path, glob.glob(str(ROOT / "data" / "codex" / "monsters" / "*.md"))),
    ]
    for f in files:
        n += bl._fold(f.read_text(encoding="utf-8", errors="replace")).count(pat)
    return n


def build() -> dict[str, dict]:
    best = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
    docs, lore, facs = _codex_names(), _lore_names(), _faccoes()
    lex = bl.lexico()["proibidos_nome"]
    bpath = ROOT / "data" / "bestiary.json"
    out: dict[str, dict] = {}
    pendentes = []
    for cid, v in best.items():
        tk = tuple(sorted(set(name_tokens(v["name"]))))
        regiao = (v.get("regions") or ["-"])[0]
        base = {"regiao_onda": regiao, "revisor": REVISOR}
        if cid in ADOCOES:
            _, motivo, ev = DECISOES.get(
                cid,
                (
                    G,
                    "Ooze de manual; a Coisa-do-Esgoto é a criatura física da lore para o mesmo slot (R4/D4)",
                    "lore_nova/creatures.txt:798",
                ),
            )
            out[cid] = {
                "classe": "generico",
                "subclasse": G,
                "motivo": motivo,
                "evidencia": ev or f"data/codex/monsters/{ADOCOES[cid]}.md:1",
                "destino": f"adotar:{ADOCOES[cid]}",
                **base,
            }
        elif cid in DECISOES:
            sub, motivo, ev = DECISOES[cid]
            if ev.endswith(":#"):
                ev = f"{ev[:-1]}{_line_of(bpath, '"id": "' + cid + '"')}"
            generico = sub == G
            if generico and not ev:
                core = re.sub(r"\s*\(.*?\)", "", v["name"]).strip()
                ev = (
                    f"{_hits(core)} hits de '{core}' em creatures.txt/codex"
                    if _hits(core)
                    else "0 hits em creatures.txt/codex"
                )
            out[cid] = {
                "classe": "generico" if generico else "valoria",
                "subclasse": sub,
                "motivo": motivo,
                "evidencia": ev,
                "destino": "reinventar" if generico else "manter",
                **base,
            }
        elif tk in docs or tk in lore:
            ev = (
                f"lore_nova/creatures.txt:{lore[tk]}"
                if tk in lore
                else f"data/codex/monsters/{docs[tk]}.md:1"
            )
            out[cid] = {
                "classe": "valoria",
                "subclasse": U,
                "motivo": "criatura/povo existe na lore (creatures.txt/Codex)",
                "evidencia": ev,
                "destino": "manter",
                **base,
            }
        elif v.get("faction") in facs:
            out[cid] = {
                "classe": "valoria",
                "subclasse": U,
                "motivo": f"facção do grafo ({v['faction']})",
                "evidencia": f"data/graph/entities.json:{_line_of(ROOT / 'data/graph/entities.json', '"' + v['faction'] + '"')}",
                "destino": "manter",
                **base,
            }
        elif v.get("origem") == "conflito-17":
            out[cid] = {
                "classe": "valoria",
                "subclasse": U,
                "motivo": "autoral de Valoria (origem conflito-17); ambientação própria do mundo",
                "evidencia": f"data/bestiary.json:{_line_of(bpath, '"id": "' + cid + '"')}",
                "destino": "manter",
                **base,
            }
        elif bl._terms_in(v["name"], lex):
            pendentes.append(cid)
        else:
            pendentes.append(cid)
    for cid, why in DUVIDA_DONO.items():
        out[cid]["duvida_dono"] = True
        out[cid]["motivo_duvida"] = why
    if pendentes:
        raise SystemExit(f"entradas sem decisão (revisar): {pendentes}")
    return out


def resumo(cur: dict[str, dict]) -> str:
    c = Counter(v["subclasse"] for v in cur.values())
    ger = [k for k, v in cur.items() if v["classe"] == "generico"]
    return (
        f"{len(cur)} entradas · único={c[U]} conceitual={c[C]} genérico={c[G]}\ngenéricos: "
        + ", ".join(ger)
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    cur = build()
    print(resumo(cur))
    if args.write:
        header = "# SPEC-349 R1 - curadoria do legado (gerado por scripts/bestiario/curadoria.py; editar DECISOES lá).\n"
        OUT.write_text(
            header + yaml.safe_dump(cur, allow_unicode=True, sort_keys=False, width=200),
            encoding="utf-8",
        )
        print(f"escrito {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
