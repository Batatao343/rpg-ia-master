"""SPEC-349 Etapas 5/6: gera mecânica e baralho de cada região a partir de ficha + mecânica.

Uso:
    bash scripts/dev/py.sh scripts/bestiario/gerar_mecanica.py --regiao nova_arcadia
    bash scripts/dev/py.sh scripts/bestiario/gerar_mecanica.py --todas

Fontes (nada de número vem da prosa):

- ``data/bestiario/fichas/<regiao>.yaml``: identidade, padrão, telegrafo, assinatura;
- ``data/bestiario/mecanica/<regiao>.yaml``: Cartas (nome, texto, efeitos no vocabulário da
  SPEC-330), dicas de perfil e fases dos chefes; Virtudes só quando a tabela não serve;
- ``data/bestiario/mecanica/_ajustes.yaml``: ajustes numéricos da arena (``corpo``, ``dano``),
  cada um com motivo (R26/Etapa 7: "cada ajuste é registrado").

Escreve:

- ``data/cards/criaturas/<regiao>.json``: Cartas próprias (``origem: bestiario-349``);
- ``data/bestiary.json``: entradas novas (shape ``conflito-17``) e, nos slots reinventados, só
  ``cartas``/``cartas_autorais``/``tactical_profile.padrao|assinatura`` (R3: o resto fica);
- ``data/cards/inimigos/_decks.json``: só a chave ``fases`` (chefes, R16).

Vitalidade e espaços de Ferimento vêm da tabela de Corpo (``gamedata``). Idempotente.

Atalhos de efeito (``e``): ``"d:leve:perfurante"`` = dano (categoria de arma),
``"a:2:cortante"`` = dano em área, ``"c:cego:1"`` = condição por N rodadas; o resto é o dict
cru da gramática.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import gamedata  # noqa: E402

try:
    from yaml import CSafeLoader as _Loader
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as _Loader

# campos de chefe do gerador `scripts/migrate_bestiary_v4.py` (SPEC-287/290/295): 2 ações por
# rodada e Vitalidade que escala com o nível do encontro; os testes de produto exigem ambos.
SOBREVIVENCIA_CHEFE = 12
ACOES_CHEFE = 2

TYPE_BY_CAT = {"lacaio": "Minion", "padrao": "Standard", "elite": "Elite", "chefe": "BOSS"}
FASE_KEYS = ("ate_vitalidade_pct", "baralho_extra", "padrao", "assinatura", "narracao")
ARMA = {"leve": 3, "marcial": 4, "versatil": 6, "pesada": 8}
DADO = {"lacaio": "1d6", "padrao": "1d8", "elite": "2d6", "chefe": "3d8"}

# Tabela de Virtudes [forca, agilidade, corpo, mente, carisma] por categoria + papel + escala.
VIRT_BASE = {
    "lacaio": [2, 2, 2, 1, 1],
    "padrao": [3, 2, 3, 2, 1],
    "elite": [4, 2, 4, 2, 2],
    "chefe": [4, 3, 5, 3, 3],
}
VIRT_PAPEL = {
    "bruto_de_linha": (1, 0, 0, 0, 0),
    "batedor_rapido": (0, 1, -1, 0, 0),
    "guarda_protetor": (0, 0, 1, 0, 0),
    "controlador": (0, 0, 0, 1, 0),
    "emboscador": (0, 1, 0, 0, 0),
    "artilharia": (-1, 0, 0, 1, 0),
    "drenador": (0, 0, 0, 1, 0),
    "quebra_defesa": (1, 0, 0, 0, 0),
    "perseguidor_marca": (0, 1, 0, 0, 0),
    "saqueador": (0, 1, 0, 0, 1),
    "suporte": (0, 0, 0, 1, 1),
    "sacrificial": (0, 0, -1, 0, 0),
    "tanque_reativo": (0, -1, 1, 0, 0),
}
VIRT_ESCALA = {
    "miuda": (-1, 0, -1, 0, 0),
    "pequena": (0, 0, 0, 0, 0),
    "humana": (0, 0, 0, 0, 0),
    "grande": (1, 0, 1, 0, 0),
    "enorme": (1, -1, 1, 0, 0),
}


def _slug(text: str) -> str:
    raw = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", raw)).strip("_")


def creature_slug(cid: str) -> str:
    return re.sub(r"^(mon|enemy)_", "", cid)


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:  # LF em tudo (.gitattributes)
        fh.write(text)


def _load_yaml(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader) or {}


_CARD_ALIAS = {
    "name": "n",
    "descricao": "t",
    "efeitos": "e",
    "frequencia": "f",
    "palavras_chave": "pc",
    "custo_folego": "fol",
    "custo_entropia": "ent",
}
_MEC_ALIAS = {
    "virtudes": "v",
    "nao_foge": "nf",
    "resistencias": "res",
    "vulnerabilidades": "vul",
    "imunidades": "imu",
}


def norm_mec(mec: dict) -> dict:
    """Aceita as chaves longas (formato da onda 1) e as curtas."""
    out = {_MEC_ALIAS.get(k, k): v for k, v in mec.items()}
    if "ataque" in out and "dado" not in out:
        out["dado"] = out["ataque"].get("dano")
    cartas = []
    for c in out.get("cartas") or []:
        cartas.append({_CARD_ALIAS.get(k, k): v for k, v in c.items()})
    out["cartas"] = cartas
    return out


# --------------------------------------------------------------------------
# Efeitos e Cartas
# --------------------------------------------------------------------------
def expand_effect(eff, dano_adj: int = 0) -> dict:
    """Atalho ``"d:leve:perfurante"`` / ``"a:2:cortante"`` / ``"c:cego:1"`` -> dict da gramática."""
    if isinstance(eff, dict):
        out = copy.deepcopy(eff)
        if dano_adj and out.get("kind") == "dano" and out.get("dano_base") is not None:
            out["dano_base"] = max(1, int(out["dano_base"]) + dano_adj)
        return out
    parts = str(eff).split(":")
    head = parts[0]
    if head == "d":
        arma = parts[1]
        out = {
            "kind": "dano",
            "categoria_arma": arma,
            "dano_base": max(1, ARMA[arma] + dano_adj),
        }
        if len(parts) > 2:
            out["dano_tipo"] = parts[2]
        return out
    if head == "a":
        out = {"kind": "dano", "alvo": "inimigos", "dano_base": max(1, int(parts[1]) + dano_adj)}
        if len(parts) > 2:
            out["dano_tipo"] = parts[2]
        return out
    if head == "c":
        return {"kind": "aplicar_condicao", "condicao": parts[1], "duracao": int(parts[2])}
    raise ValueError(f"atalho de efeito desconhecido: {eff!r}")


def card_id(cid: str, spec: dict, sig_id: str | None) -> str:
    if spec.get("id"):
        return str(spec["id"])
    if spec.get("sig") and sig_id:
        return sig_id
    return f"cri_{creature_slug(cid)}_{_slug(spec['n'])}"


def build_card(cid: str, spec: dict, sig_id: str | None, *, oculta: bool, dano_adj: int) -> dict:
    from services import card_effects as fx
    from services.card_budget_fit import fit_orcamento

    efeitos = [expand_effect(e, dano_adj) for e in spec["e"]]
    card: dict = {
        "id": card_id(cid, spec, sig_id),
        "name": spec["n"],
        "origem": "bestiario-349",
        "classe": "Inimigo",
        "subclasse": cid,
        "tipo": "ativa",
        "patamar": "inicial",
        "custo_entropia": int(spec.get("ent", 0)),
        "frequencia": spec.get("f", "turno"),
        "virtude_permitida": [],
        "efeito": efeitos[0],
    }
    if len(efeitos) > 1:
        card["efeitos"] = efeitos
    if spec.get("pc"):
        card["palavras_chave"] = spec["pc"]
    if spec.get("fol") is not None:
        card["custo_folego"] = int(spec["fol"])
    card["descricao"] = spec["t"]
    card["oculta"] = oculta
    card["efeito"] = fx.primary_effect(card) or efeitos[0]  # o principal é o que o motor lê
    return fit_orcamento(card)


def cartas_da_criatura(
    f: dict, mec: dict, dano_adj: int, sig_adj: int = 0
) -> tuple[list[dict], list[dict]]:
    """``(todas, iniciais)``; as de ``baralho_extra`` de fase ficam fora do baralho inicial."""
    cid = f["id"]
    sig_id = f["mecanica_assinatura"]["carta"]
    so_fase = {c for fs in mec.get("fases") or [] for c in (fs.get("baralho_extra") or [])}
    todas: list[dict] = []
    for i, spec in enumerate(mec["cartas"]):
        id_card = card_id(cid, spec, sig_id)
        # a 1ª Carta é o ataque básico (a que a IA joga com `off`); o ajuste de dano vale
        # nela e na assinatura
        adj = (dano_adj if i == 0 else 0) + ((dano_adj + sig_adj) if spec.get("sig") else 0)
        if id_card in so_fase:  # Cartas de fase seguem a assinatura (o chefe 'on' as joga)
            adj = dano_adj + sig_adj
        oculta = bool(spec.get("sig")) or id_card in so_fase or bool(spec.get("oculta"))
        todas.append(build_card(cid, spec, sig_id, oculta=oculta, dano_adj=adj))
    iniciais = [c for c in todas if c["id"] not in so_fase]
    return todas, iniciais


# --------------------------------------------------------------------------
# Virtudes e perfil
# --------------------------------------------------------------------------
def clamp(v: int) -> int:
    return max(0, min(5, v))


def virtudes_de(f: dict, mec: dict, ajuste_corpo: int, ajuste_forca: int = 0) -> list[int]:
    if mec.get("v"):
        v = [int(x) for x in mec["v"]]
    else:
        v = list(VIRT_BASE[f["categoria"]])
        pap = VIRT_PAPEL.get(f["papel_tatico"], (0,) * 5)
        esc = VIRT_ESCALA.get((f.get("anatomia") or {}).get("escala"), (0,) * 5)
        v = [x + p + e for x, p, e in zip(v, pap, esc, strict=True)]
    v[2] += ajuste_corpo
    if f["categoria"] == "chefe":  # invariante de produto: chefe com mais Vitalidade que lacaio
        v[2] = max(2, v[2])
    spill = 0
    if v[2] > 5:
        spill, v[2] = v[2] - 5, 5
    elif v[2] < 0:
        spill, v[2] = v[2], 0
    v[0] += spill + ajuste_forca  # o que o Corpo não absorve vai para a Força
    return [clamp(x) for x in v]


def _primeira_frase(texto: str, limite: int = 150) -> str:
    s = " ".join(str(texto or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m else s
    return s if len(s) <= limite else s[: limite - 1].rstrip() + "…"


def nao_foge(f: dict, mec: dict) -> bool:
    if "nf" in mec:
        return bool(mec["nf"])
    return (
        f["categoria"] == "chefe"
        or f["arquetipo"] == "morto_vivo_implacavel"
        or f["papel_tatico"] == "sacrificial"
    )


def priorities(f: dict, mec: dict) -> list[dict]:
    dicas = mec.get("dicas") or []
    nf = nao_foge(f, mec)
    if dicas:
        fugir = dicas[0]
    elif nf:
        fugir = "Não recua nem se rende; segue até cair."
    else:
        fugir = "Recua e foge quando a luta vira risco de morte."
    sempre = dicas[1] if len(dicas) > 1 else _primeira_frase(f.get("comportamento", ""))
    return [
        {
            "trigger": "muito_ferido",
            "tipo": "obrigatorio",
            "action_hint": fugir,
            "resistance": "absoluta" if nf else "flexivel",
            "blocks": [],
        },
        {
            "trigger": "sempre",
            "tipo": "obrigatorio",
            "action_hint": sempre,
            "resistance": "flexivel",
            "blocks": [],
        },
    ]


def _assinatura(f: dict) -> dict:
    return {
        "carta": f["mecanica_assinatura"]["carta"],
        "a_cada_n": int(f["a_cada_n"]),
        "telegrafo": f["telegrafo"],
    }


def dano_dado(f: dict, mec: dict, dano_adj: int) -> str:
    if mec.get("dado"):
        return str(mec["dado"])
    cat = f["categoria"]
    if dano_adj >= 2:
        return {"lacaio": "1d8", "padrao": "2d6", "elite": "2d8", "chefe": "3d10"}[cat]
    if dano_adj <= -2:
        return {"lacaio": "1d4", "padrao": "1d6", "elite": "1d8", "chefe": "2d8"}[cat]
    return DADO[cat]


def entrada_nova(f: dict, mec: dict, cartas: list[dict], aj: dict) -> dict:
    forca, agil, corpo, mente, carisma = virtudes_de(
        f, mec, int(aj.get("corpo", 0)), int(aj.get("forca", 0))
    )
    virtudes = {
        "forca": forca,
        "agilidade": agil,
        "corpo": corpo,
        "mente": mente,
        "carisma": carisma,
    }
    vit = gamedata.vitalidade_para_corpo(corpo)
    ids = [c["id"] for c in cartas]
    app = str(f["aparencia"]).strip()
    assert len(app) <= 300, f["id"]
    atk = cartas[0]
    conjura = any(
        (e.get("dano_tipo") in {"arcano", "abissal", "elemental"})
        for c in cartas
        for e in (c.get("efeitos") or [c["efeito"]])
    )  # content_validator: dano de conjurador exige ataque à distância
    ataque_tipo = "ranged" if f["papel_tatico"] == "artilharia" or conjura else "melee"
    chefe = (
        {"vitalidade_por_nivel_encontro": SOBREVIVENCIA_CHEFE, "acoes_por_rodada": ACOES_CHEFE}
        if f["categoria"] == "chefe"
        else {}
    )
    return {
        "id": f["id"],
        "name": f["nome"],
        "description": f["description"],
        "type": TYPE_BY_CAT[f["categoria"]],
        "categoria": f["categoria"],
        "arquetipo": f["arquetipo"],
        "attributes": {
            "str": min(20, 8 + 2 * forca),
            "dex": min(20, 8 + 2 * agil),
            "con": min(20, 8 + 2 * corpo),
            "int": min(20, 8 + 2 * mente),
            "wis": 10,
            "cha": min(20, 8 + 2 * carisma),
        },
        "attacks": [
            {
                "name": atk["name"],
                "type": ataque_tipo,
                "damage": dano_dado(f, mec, int(aj.get("dano", 0))),
            }
        ],
        "abilities": [f["mecanica_assinatura"]["frase"]],
        "loot": [f"Vestígio de {f['nome']}"],
        "regions": [f["regiao"]],
        "origem": "bestiario-349",
        "onda": int(f.get("onda", 1)),
        "familia_valoria": f["familia"],
        "appearance": app,
        "cartas_autorais": ids,
        "virtudes": virtudes,
        "max_vitalidade": vit,
        "vitalidade": vit,
        "ferimento_espacos": gamedata.espacos_ferimento_para_corpo(corpo),
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "resistances": mec.get("res") or {},
        "vulnerabilities": mec.get("vul") or [],
        "immunities": mec.get("imu") or [],
        "cartas": ids,
        **({"faction": f["faccao"]} if f.get("faccao") else {}),
        **chefe,
        "tactical_profile": {
            "priorities": priorities(f, mec),
            "padrao": list(f["padrao"]),
            "assinatura": _assinatura(f),
        },
    }


def atualizar_slot(entry: dict, f: dict, cartas: list[dict]) -> dict:
    """R3: o slot troca só as Cartas próprias e ganha padrão/assinatura; resto intacto."""
    ids = [c["id"] for c in cartas]
    entry["cartas"] = ids
    entry["cartas_autorais"] = ids
    tp = entry.setdefault("tactical_profile", {})
    tp["padrao"] = list(f["padrao"])
    tp["assinatura"] = _assinatura(f)
    return entry


# --------------------------------------------------------------------------
# Região
# --------------------------------------------------------------------------
def regioes() -> list[str]:
    base = ROOT / "data" / "bestiario" / "mecanica"
    return sorted(p.stem for p in base.glob("*.yaml") if not p.stem.startswith("_"))


def ajustes() -> dict:
    p = ROOT / "data" / "bestiario" / "mecanica" / "_ajustes.yaml"
    return (_load_yaml(p).get("ajustes") or {}) if p.exists() else {}


def gerar(regiao: str, *, escrever: bool = True) -> dict:
    ficha_doc = _load_yaml(ROOT / "data" / "bestiario" / "fichas" / f"{regiao}.yaml")
    mec_path = ROOT / "data" / "bestiario" / "mecanica" / f"{regiao}.yaml"
    mec_doc = _load_yaml(mec_path).get("criaturas") or {}
    aj_all = ajustes()
    best_path = ROOT / "data" / "bestiary.json"
    best = json.loads(best_path.read_text(encoding="utf-8"))
    decks_path = ROOT / "data" / "cards" / "inimigos" / "_decks.json"
    decks = json.loads(decks_path.read_text(encoding="utf-8"))

    all_cards: list[dict] = []
    fases: dict[str, list[dict]] = {}
    faltam: list[str] = []
    for f in ficha_doc["criaturas"]:
        if f.get("status") == "retro":
            continue
        f = {**f, "regiao": regiao, "onda": f.get("onda", ficha_doc.get("onda", 1))}
        cid = f["id"]
        mec = mec_doc.get(cid)
        if mec is None:
            faltam.append(cid)
            continue
        mec = norm_mec(mec)
        aj = aj_all.get(cid) or {}
        todas, iniciais = cartas_da_criatura(f, mec, int(aj.get("dano", 0)), int(aj.get("sig", 0)))
        all_cards += todas
        if f["status"] == "nova":
            best[cid] = entrada_nova(f, mec, iniciais, aj)
        else:
            atualizar_slot(best[cid], f, iniciais)
        if mec.get("fases"):
            fases[cid] = mec["fases"]

    if faltam:
        print(f"[{regiao}] sem mecânica: {len(faltam)} -> {faltam[:5]}...", file=sys.stderr)
    if escrever:
        cards_path = ROOT / "data" / "cards" / "criaturas" / f"{regiao}.json"
        cards_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_meta": f"SPEC-349: Cartas próprias das criaturas de {regiao} (gerado por "
            "scripts/bestiario/gerar_mecanica.py a partir de data/bestiario/mecanica/).",
            "cards": all_cards,
        }
        _write(cards_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        _write(best_path, json.dumps(best, ensure_ascii=False, indent=2))
        dec_fases = decks.setdefault("fases", {})
        for cid, fs in fases.items():
            dec_fases[cid] = [{k: fz[k] for k in FASE_KEYS if k in fz} for fz in fs]
        _write(decks_path, json.dumps(decks, ensure_ascii=False, indent=2) + "\n")
    return {"regiao": regiao, "cartas": len(all_cards), "fases": sorted(fases), "faltam": faltam}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regiao")
    ap.add_argument("--todas", action="store_true")
    a = ap.parse_args()
    for r in regioes() if a.todas else [a.regiao or "nova_arcadia"]:
        print(gerar(r))
