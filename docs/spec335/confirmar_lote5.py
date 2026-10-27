"""SPEC-335 Lote 5 - confirma com as sementes 20-99 (320 lutas por braco) os deltas do protocolo.

    bash scripts/dev/py.sh docs/spec335/confirmar_lote5.py

Mesmo protocolo do lote (Carta isolada, level_req, encontro padrao), mas 80 sementes. Inclui dois
CONTROLES sinteticos (so dano, sem sustento) para separar "o braco base nao tem golpe" de "a Carta
e forte": se o controle tambem sobe, o delta e do braco base fino, nao da Carta.
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "cards"))
import sim  # noqa: E402

from services import cards  # noqa: E402

ALVOS = [
    ("trincheira", "med1_tri_pancada_de_cabo"),
    ("trincheira", "med1_tri_golpe_e_pulso"),
    ("trincheira", "med1_tri_pulso_emprestado"),
    ("boticario", "med1_bot_agulha_envenenada"),
    ("ferro", "med1_fer_cotovelo_de_aco"),
    ("ferro", "med1_fer_pinca_de_aco"),
    ("ferro", "med1_fer_ancora_de_ferro"),
    ("ferro", "med1_fer_cirurgia_no_ferro"),
]
SUB = {
    "trincheira": "cirurgiao_trincheira",
    "boticario": "boticario",
    "ferro": "cirurgiao_ferro",
}


def controle(cid: str, dano: int, sub: str, cat: str = "marcial") -> dict:
    return {
        "id": cid,
        "name": "Controle",
        "tipo": "ativa",
        "origem": "onda-1",
        "classe": "Médico de Campo",
        "subclasse": sub,
        "patamar": "avancado",
        "raridade": "incomum",
        "custo_entropia": 1,
        "custo_folego": 1,
        "frequencia": "turno",
        "virtude_permitida": ["mente"],
        "efeitos": [{"kind": "dano", "categoria_arma": cat, "dano_base": dano}],
        "descricao": "controle sintetico",
        "tier": 3,
        "level_req": 4,
        "apex": False,
        "onda": 1,
        "versao": 1,
    }


def rodar(card: dict, outros: set[str]) -> dict:
    base = cards._load_cards()
    saved = {i: base.pop(i) for i in outros - {card["id"]} if i in base}
    try:
        lvl = int(card["level_req"])
        return sim.simulate_batch([card], [lvl], ["padrao"], 4, list(range(20, 100)))[card["id"]]
    finally:
        base.update(saved)


def main() -> None:
    todas = {i for i in cards._load_cards() if i.startswith("med1_")}
    por_id = {}
    for sub in SUB.values():
        path = f"data/cards/posturas/medico_{sub}.json"
        for c in json.load(open(path, encoding="utf-8"))["cards"]:
            por_id[c["id"]] = c
    out: dict = {}
    for _sub, cid in ALVOS:
        out[cid] = rodar(por_id[cid], todas)
    # controles de so dano (`turno`, sem sustento), na MESMA subclasse e com o mesmo dano da Carta
    for cid, dano, cat, sub in [
        ("ctl_trincheira_dano3_leve", 3, "leve", "cirurgiao_trincheira"),
        ("ctl_boticario_dano3_leve", 3, "leve", "boticario"),
        ("ctl_ferro_dano4_marcial", 4, "marcial", "cirurgiao_ferro"),
    ]:
        c = controle(cid, dano, sub, cat)
        out[c["id"]] = rodar(c, todas)
    for cid, r in out.items():
        print(
            f"{cid}: uso {r['taxa_uso']:.0%} sem {r['vitoria_sem']} com {r['vitoria_com']} "
            f"delta {r['delta_pp']:+.1f} pp ({r['lutas_por_braco']} lutas) {r['bandeiras']}",
            flush=True,
        )
    with open(
        "docs/spec335/sim-lote5-confirmacao-sementes20-99.json", "w", encoding="utf-8", newline="\n"
    ) as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main()
