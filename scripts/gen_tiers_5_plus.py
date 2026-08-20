"""Autoria reproduzível do lote de 80 Cartas tardias e metadata de progressão."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "data" / "cards"
CLASSES_PATH = ROOT / "data" / "classes.json"
LEVEL_BY_TIER = {5: 9, 6: 12, 7: 15, 8: 18, 9: 20}
PATAMAR = {5: "epico_i", 6: "epico_ii", 7: "lendario", 8: "mitico", 9: "apice"}
PREFIX = {
    "Devoto do Abismo": "dev", "Sangromante": "san", "Corruptor": "cor",
    "Arcanista Cinzento": "arc", "Médico de Campo": "med",
}
TRUNK = {
    "Devoto do Abismo": ["Juramento de Cinza", "Linha Inamovível", "Vigília do Convite", "Coração da Muralha"],
    "Sangromante": ["Cláusula Rubra", "Reserva de Dor", "Preço Antecipado", "Última Moeda de Sangue"],
    "Corruptor": ["Colheita da Ruína", "Pacto de Ferrugem", "Jardim Decomposto", "Entropia Compartilhada"],
    "Arcanista Cinzento": ["Válvula Mestra", "Geometria da Fenda", "Caldeira Fria", "Teorema do Estouro"],
    "Médico de Campo": ["Triagem Impossível", "Pulso de Reserva", "Protocolo da Última Luz", "Juramento de Retorno"],
}
BRANCH_NAMES = {
    "consagrado": ["Liturgia da Cicatriz", "Selo de Vigília", "Altar Ambulante", "Consagração do Vazio"],
    "zeloso": ["Ciúme da Escuridão", "Interposição Fervorosa", "Ninguém Além de Mim", "Amor que Devora"],
    "enlutado": ["Réquiem de Ferro", "Luto Vigilante", "Nome dos Perdidos", "Procissão sem Fim"],
    "exposto": ["Palco de Cicatrizes", "Aplauso Cruel", "Dor em Evidência", "Testemunho Escarlate"],
    "avaro": ["Cofre de Sangue", "Juro Composto", "Cobrança Final", "Fortuna Rubra"],
    "silencioso": ["Corte sem Eco", "Economia Perfeita", "Dívida Invisível", "Última Assinatura"],
    "biologia": ["Ecologia da Febre", "Anticorpo Traidor", "Carne em Estações", "Gênese da Podridão"],
    "alma": ["Liturgia do Desalento", "Vontade Oca", "Coro da Renúncia", "Eclipse Interior"],
    "inorganica": ["Catedral de Ferrugem", "Fratura Mineral", "Pó dos Impérios", "Idade do Colapso"],
    "calibrado": ["Equação de Combate", "Margem Exata", "Pressão Nominal", "Constante Impossível"],
    "descoberto": ["Falha Deliberada", "Sobrecarga Errante", "Raio sem Gaiola", "Acidente Perfeito"],
    "improvisador": ["Nota à Margem", "Versão dos Vencedores", "Arquivo Vivo", "Última Página"],
    "cirurgiao_trincheira": ["Triagem de Guerra", "Dose Necessária", "Corte Limpo", "Hospital de Uma Pessoa"],
    "boticario": ["Dor Compartilhada", "Pulso Solidário", "Luto Clínico", "Coração de Todos"],
    "cirurgiao_ferro": ["Protocolo Absoluto", "Remédio ou Ruína", "Cirurgia de Fé", "Milagre Imperdoável"],
}


def _effect(kind: str, value: int, index: int) -> dict:
    if kind == "dano":
        return {"kind": "dano", "categoria_arma": "versatil",
                "dano_base": max(6, value), "dano_tipo": "abissal"}
    effect = {"kind": kind, "valor": value, "duracao": 2 + index % 2}
    if kind == "aplicar_condicao":
        effect["condicao"] = "exposto"
    return effect


def _card(*, cid: str, name: str, classe: str, branch: str, tier: int,
          tipo: str, kind: str, value: int, index: int, apex: bool = False) -> dict:
    return {
        "id": cid, "name": name, "tipo": tipo, "origem": "tiers-5-plus",
        "classe": classe, "subclasse": branch, "patamar": PATAMAR[tier],
        "tier": tier, "level_req": LEVEL_BY_TIER[tier], "apex": apex,
        "custo_entropia": 7 if apex else 2 + tier // 2,
        "frequencia": "descanso_longo" if apex else ("cena" if tier >= 7 else "turno"),
        "virtude_permitida": ["mente", "agilidade", "forca", "carisma", "corpo"],
        "efeito": _effect(kind, value, index),
        "papel": f"tier-{tier}-{tipo}-{kind}-{index}",
        "descricao": f"{name} converte risco acumulado em uma decisão mecânica de fim de campanha.",
        "contrapartida": ("Exige Entropia alta e descanso longo; a Carga permanece."
                           if apex else "Consome Entropia e respeita a frequência da Carta."),
    }


def build_cards(classes: dict) -> list[dict]:
    result = []
    trunk_kinds = ["dano", "buff_defesa", "vantagem", "utilitaria"]
    trunk_types = ["ativa", "reacao", "passiva", "utilitaria"]
    branch_kinds = ["dano", "contra_ataque", "aplicar_condicao"]
    branch_types = ["ativa", "reacao", "passiva"]
    for classe, class_data in classes.items():
        prefix = PREFIX[classe]
        for index, (tier, name) in enumerate(zip((5, 6, 7, 8), TRUNK[classe])):
            result.append(_card(
                cid=f"{prefix}_t{tier}_tronco", name=name, classe=classe, branch="",
                tier=tier, tipo=trunk_types[index], kind=trunk_kinds[index],
                value=7 + tier, index=index,
            ))
        for branch_index, branch in enumerate(class_data["branches"]):
            names = BRANCH_NAMES[branch]
            for index, tier in enumerate((5, 7, 8)):
                result.append(_card(
                    cid=f"{prefix}_{branch}_t{tier}", name=names[index], classe=classe,
                    branch=branch, tier=tier, tipo=branch_types[index],
                    kind=branch_kinds[(index + branch_index) % 3],
                    value=8 + tier + branch_index, index=branch_index * 4 + index,
                ))
            result.append(_card(
                cid=f"{prefix}_{branch}_apice", name=names[3], classe=classe,
                branch=branch, tier=9, tipo="ativa", kind=branch_kinds[branch_index % 3],
                value=18 + branch_index, index=branch_index, apex=True,
            ))
    assert len(result) == 80
    return result


def main() -> None:
    classes = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))
    existing_by_branch: dict[tuple[str, str], list[str]] = {}
    trunk_by_class: dict[str, list[str]] = {}
    for path in sorted(CARDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for card in data.get("cards", []):
            if (card.get("classe") in PREFIX and card.get("tipo") != "virtude"
                    and card.get("origem") != "tiers-5-plus"):
                level = {"inicial": 1, "avancado": 4, "superior": 7}.get(card.get("patamar"), 1)
                tier = {"inicial": 2 if card.get("subclasse") else 1,
                        "avancado": 3, "superior": 4}.get(card.get("patamar"), 1)
                card["tier"], card["level_req"], card["apex"] = tier, level, False
                changed = True
                key = (card["classe"], str(card.get("subclasse") or ""))
                existing_by_branch.setdefault(key, []).append(card["id"])
                if not card.get("subclasse"):
                    trunk_by_class.setdefault(card["classe"], []).append(card["id"])
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for classe, class_data in classes.items():
        normal_gain = int((class_data.get("level_gains") or {}).get("entropy", 0) or 0)
        base = int((class_data.get("base_stats") or {}).get("entropy", 0) or 0)
        class_data["late_entropy_curve"] = {
            "gains": {str(level): (1 if level in (12, 15, 18, 20) else 0)
                      for level in range(11, 21)},
            "cap": base + 9 * normal_gain + 4,
        }
        for branch_id, branch in class_data["branches"].items():
            identity = str(branch.get("identity", "")).rstrip(".").lower()
            branch["playstyle"] = f"Especialização {identity}, com decisões de setup e frequência."
            branch["tradeoff"] = "Poder concentrado aumenta o custo de Entropia e não remove a Carga do Abismo."
            branch["preview_card_ids"] = (
                existing_by_branch.get((classe, branch_id), [])[:2]
                or trunk_by_class.get(classe, [])[:2]
            )
    CLASSES_PATH.write_text(json.dumps(classes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = {"schema_version": 1, "source": "tiers-5-plus", "cards": build_cards(classes)}
    (CARDS_DIR / "tiers_5_plus.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
