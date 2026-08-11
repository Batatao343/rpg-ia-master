"""services/conflict_damage.py — pipeline de DANO -> Ferimentos (spec conflito-05).

Conclui a resolução iniciada em conflito-04: do "acerto confirmado" ao "Ferimento
localizado aplicado", na ORDEM FIXA da defesa (R8): dano×crítico → Imunidade/
Resistência/Vulnerabilidade → Proteção → Integridade → Vitalidade e Gravidade →
Ferimentos e efeitos secundários.

Opera sobre `target["vitalidade"]` e `target["ferimentos"]` (schema da
conflito-01). Reusa `Condition` para Sangramento (evita DoT paralelo).
"""
import random
import unicodedata
from typing import Dict, List, Optional

import gamedata

_ORD = {"leve": 1, "grave": 2, "critico": 3}
_ORD_INV = {1: "leve", 2: "grave", 3: "critico"}
DEFAULT_HIT_REGIONS = ("cabeca", "torso", "braco", "perna")
_KNOWN_REGION_ALIASES = {
    "cabeca": "cabeca",
    "craneo": "cabeca",
    "rosto": "cabeca",
    "torso": "torso",
    "peito": "torso",
    "abdomen": "torso",
    "braco": "braco",
    "braco esquerdo": "braco_esquerdo",
    "braco direito": "braco_direito",
    "mao": "mao",
    "perna": "perna",
    "perna esquerda": "perna_esquerda",
    "perna direita": "perna_direita",
    "pe": "pe",
}


def _fold_region(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return " ".join(
        "".join(c for c in normalized if not unicodedata.combining(c))
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def anatomical_regions(target: dict) -> List[str]:
    """Regiões válidas da anatomia da ficha, com fallback humanoide fechado."""
    raw = (
        target.get("regioes_anatomicas")
        or target.get("hit_regions")
        or target.get("anatomia")
    )
    if isinstance(raw, dict):
        raw = raw.get("regioes") or raw.get("regions") or list(raw)
    if not isinstance(raw, (list, tuple)) or not raw:
        return list(DEFAULT_HIT_REGIONS)
    regions: List[str] = []
    for value in raw:
        folded = _fold_region(value)
        canonical = _KNOWN_REGION_ALIASES.get(folded, folded.replace(" ", "_"))
        if canonical and canonical not in regions:
            regions.append(canonical)
    return regions or list(DEFAULT_HIT_REGIONS)


def canonical_hit_region(target: dict, region: object) -> Optional[str]:
    folded = _fold_region(region)
    if not folded:
        return None
    candidate = _KNOWN_REGION_ALIASES.get(folded, folded.replace(" ", "_"))
    valid = set(anatomical_regions(target))
    # Fichas humanoides aceitam também as formas localizadas históricas.
    if tuple(anatomical_regions(target)) == DEFAULT_HIT_REGIONS:
        valid.update(_KNOWN_REGION_ALIASES.values())
    return candidate if candidate in valid else None


def is_valid_hit_region(target: dict, region: object) -> bool:
    return canonical_hit_region(target, region) is not None


def select_hit_region(target: dict, directed_region: object = None, *,
                      rng=None) -> str:
    """Seleciona região canônica. Direcionamento inválido cai no sorteio seguro."""
    directed = canonical_hit_region(target, directed_region)
    if directed is not None:
        return directed
    regions = anatomical_regions(target)
    rng = rng or random.Random()
    # Dublês de RNG antigos nem sempre respeitam os bounds recebidos; clamp
    # defensivo mantém a seleção total sem sacrificar a reprodutibilidade.
    index = max(0, min(len(regions) - 1, int(rng.randint(0, len(regions) - 1))))
    return regions[index]


# --------------------------------------------------------------------------
# Ferimentos localizados (R9)
# --------------------------------------------------------------------------
def combine_category(a: str, b: str) -> str:
    """Agravamento na mesma região (R9): Leve+Leve=Grave, Leve+Grave=Crítico,
    Grave+Leve=Crítico; teto em Crítico."""
    return _ORD_INV[min(3, _ORD.get(a, 1) + _ORD.get(b, 1))]


def _wound_spaces(target: dict) -> Dict[str, int]:
    if target.get("ferimento_espacos"):
        return target["ferimento_espacos"]
    corpo = (target.get("virtudes") or {}).get("corpo", 0)
    return gamedata.espacos_ferimento_para_corpo(corpo)


def apply_wound(target: dict, categoria: str, regiao: str) -> dict:
    """Cria/agrava um Ferimento na região. Mesma região agrava o existente;
    categoria cheia escala para a seguinte (R9). Retorna o Ferimento resultante."""
    fer = target.setdefault("ferimentos", {"leve": [], "grave": [], "critico": []})
    for c in ("leve", "grave", "critico"):
        fer.setdefault(c, [])

    existing_cat = existing_obj = None
    for c in ("critico", "grave", "leve"):
        for w in fer[c]:
            if w.get("regiao") == regiao:
                existing_cat, existing_obj = c, w
                break
        if existing_cat:
            break
    removed = None
    # Trauma adicional sobre um Crítico não "combina" removendo o anterior:
    # preserva a sequela e ocupa o próximo espaço crítico.
    if existing_cat == "critico":
        categoria = "critico"
    elif existing_cat:
        fer[existing_cat].remove(existing_obj)
        removed = (existing_cat, existing_obj)
        categoria = combine_category(existing_cat, categoria)

    espacos = _wound_spaces(target)
    while _ORD[categoria] < 3 and len(fer[categoria]) >= int(espacos.get(categoria, 99)):
        categoria = _ORD_INV[_ORD[categoria] + 1]

    capacity = max(0, int(espacos.get(categoria, 0) or 0))
    if len(fer[categoria]) >= capacity:
        if removed is not None:
            fer[removed[0]].append(removed[1])
        return {
            "categoria": categoria,
            "regiao": regiao,
            "suprimida": False,
            "aplicado": False,
        }

    wound = {
        "categoria": categoria,
        "regiao": regiao,
        "suprimida": False,
        "aplicado": True,
    }
    fer[categoria].append(wound)
    return wound


# --------------------------------------------------------------------------
# Resistência / Vulnerabilidade / Imunidade (R4)
# --------------------------------------------------------------------------
def net_resistance(sources: List[str]) -> int:
    """Compensa Resistência × Vulnerabilidade pela intensidade; fontes iguais não
    acumulam (R4). Retorna o modificador líquido de dano."""
    seen = set()
    res = vuln = 0
    for s in sources or []:
        if s in seen:
            continue  # fontes iguais não acumulam
        seen.add(s)
        m = gamedata.RESIST_MODIFIER.get(s, 0)
        if m < 0:
            res = min(res, m)      # mantém a mais forte (não soma ilimitado)
        elif m > 0:
            vuln = max(vuln, m)
    return res + vuln              # compensam-se pela intensidade


def _resist_modifier(target: dict, dtype: str, ignore_resistance: bool) -> int:
    if ignore_resistance:
        return 0
    r = (target.get("resistances") or {}).get(dtype)
    if not r:
        return 0
    sources = r if isinstance(r, list) else [r]
    return net_resistance(sources)


# --------------------------------------------------------------------------
# Pipeline principal (ordem fixa R8)
# --------------------------------------------------------------------------
def _active_defense(target: dict, use_shield: bool) -> Optional[dict]:
    """Armadura e escudo NÃO somam (R6): escolhe um por ataque Defensável."""
    if use_shield and target.get("shield"):
        return target["shield"]
    return target.get("armor")


def resolve_damage_and_wounds(target: dict, *, damage_base: int,
                              damage_type: str = "cortante", crit_mult: int = 1,
                              directed_region: Optional[str] = None,
                              ignore_resistance: bool = False,
                              use_shield: bool = False,
                              defensavel: bool = True,
                              rng=None) -> dict:
    """Resolve o dano na ORDEM FIXA (R8). Retorna a matemática completa (R9)."""
    log: List[str] = []
    secondary: List[dict] = []
    dtype = str(damage_type or "").lower()
    is_fisico = dtype in gamedata.DANO_FISICO
    region = select_hit_region(target, directed_region, rng=rng)

    # (1) dano + multiplicador de Crítico
    dano = int(damage_base) * int(crit_mult)
    log.append(f"dano {damage_base}×{crit_mult}={dano}")

    # (2) Imunidade / Resistência / Vulnerabilidade
    if not ignore_resistance and dtype in (target.get("immunities") or []):
        gamedata.sync_legacy_hp_aliases(target)
        return {"dano_final": 0, "excedente": 0, "imune": True, "wound": None,
                "protegido": False, "resultado": "imune", "secondary": [],
                "log": log + ["Imunidade: dano 0"],
                "vitalidade": int(target.get("vitalidade", 0)),
                "regiao": region}
    mod = _resist_modifier(target, dtype, ignore_resistance)
    if mod:
        dano = max(0, dano + mod)
        log.append(f"resist/vuln {mod:+d} -> {dano}")

    # (3) Proteção + (4) Integridade (armadura/escudo compatível, não Comprometida)
    protegido = False
    defense = _active_defense(target, use_shield)
    if defense and not defense.get("comprometida"):
        compativel = is_fisico or dtype in (defense.get("resist_tipos") or [])
        if compativel and (defensavel or not use_shield):
            protecao = int(defense.get("protecao", 0))
            if dtype == "perfurante":
                protecao = max(0, protecao - 1)   # R2
            absorbed = min(dano, protecao)
            if absorbed > 0:
                dano -= absorbed
                protegido = True
                log.append(f"Proteção -{absorbed} -> {dano}")
            # Integridade reduz dano adicional até reducoes_max (R5). Só armadura
            # com `reducoes_max` explícito gasta Integridade extra; escudo = 0.
            reducoes_max = int(defense.get("reducoes_max", 0))
            custo = 2 if dtype == "corrosivo" else 1   # Corrosivo custa 2× (R3)
            integ = int(defense.get("integridade_atual", 0))
            reduzido = 0
            while reduzido < reducoes_max and dano > 0 and integ >= custo:
                dano -= 1
                integ -= custo
                reduzido += 1
            if reduzido:
                log.append(f"Integridade -{reduzido} dano (gasta {reduzido * custo})")
            if protegido and dtype == "impactante" and integ > 0:
                integ -= 1                         # R2: Integridade extra
                log.append("Impactante: -1 Integridade extra")
            defense["integridade_atual"] = max(0, integ)
            if defense["integridade_atual"] <= 0 and not defense.get("comprometida"):
                defense["comprometida"] = True
                log.append("Armadura COMPROMETIDA (0 Integridade)")

    atravessou = dano > 0

    # Ígneo: +2 imediato se ≥1 atravessou (R3)
    if dtype == "igneo" and atravessou:
        dano += 2
        log.append("Ígneo +2")

    # (5) Vitalidade e Gravidade
    vit = int(target.get("vitalidade", target.get("hp", 0)) or 0)
    excedente = max(0, dano - vit)
    target["vitalidade"] = max(0, vit - dano)
    log.append(f"Vitalidade {vit} -> {target['vitalidade']} (excedente {excedente})")

    # (6) Ferimentos + efeitos secundários
    wound = None
    if excedente > 0:
        corpo = (target.get("virtudes") or {}).get("corpo", 0)
        categoria = gamedata.categoria_ferimento(corpo, excedente)
        if categoria:
            wound = apply_wound(target, categoria, region)
            suffix = "" if wound.get("aplicado", True) else " (capacidade cheia)"
            log.append(f"Ferimento {wound['categoria']} em {region}{suffix}")
            if dtype == "cortante":               # R2: Sangramento ao ferir
                _apply_sangramento(target, secondary)

    # flags sobrenaturais condicionadas a atravessar (R3)
    if atravessou:
        if dtype == "gelido":
            target["_gelido_next_attack"] = True
            secondary.append({"kind": "next_attack_advantage_vs_target"})
        elif dtype == "eletrico":
            target["_eletrico_next_attack"] = True
            secondary.append({"kind": "target_disadvantage_next_attack"})
        elif dtype == "abissal":
            target["exposto"] = True
            target["_abissal_ignore_resist_next"] = True
            secondary.append({"kind": "exposto"})
    if dtype == "arcano":
        secondary.append({"kind": "remove_temp_buff"})

    resultado = "imune" if False else ("sem_efeito" if dano == 0 and excedente == 0 and not protegido
                                       else "dano")
    gamedata.sync_legacy_hp_aliases(target)
    return {"dano_final": dano, "excedente": excedente, "imune": False,
            "wound": wound, "protegido": protegido, "resultado": resultado,
            "secondary": secondary, "vitalidade": target["vitalidade"],
            "regiao": region, "log": log}


def _apply_sangramento(target: dict, secondary: List[dict]) -> None:
    """Sangramento (Cortante, R2): 1 Vitalidade ao fim do próximo turno, NÃO
    acumula. Reaproveita o schema Condition (evita DoT paralelo)."""
    conds = target.setdefault("active_conditions", [])
    if any(str(c.get("name", "")).lower() == "sangramento" for c in conds):
        return
    cond = {"name": "Sangramento", "dot": 1, "duration": 1, "source": "cortante"}
    conds.append(cond)
    secondary.append({"kind": "apply_condition", "condition": cond})


# --------------------------------------------------------------------------
# Sacrifício de Vitalidade — Sangromante (R10)
# --------------------------------------------------------------------------
def sacrifice_vitality(target: dict, amount: int, *, region: str = "torso") -> dict:
    """Sangromante paga com Vitalidade até 0; déficit além vira Ferimento pelos
    próprios Limites de Gravidade. Armadura NÃO protege (sacrifício voluntário)."""
    vit = int(target.get("vitalidade", 0) or 0)
    deficit = max(0, int(amount) - vit)
    target["vitalidade"] = max(0, vit - int(amount))
    wound = None
    if deficit > 0:
        corpo = (target.get("virtudes") or {}).get("corpo", 0)
        categoria = gamedata.categoria_ferimento(corpo, deficit)
        if categoria:
            wound = apply_wound(target, categoria, region)
    gamedata.sync_legacy_hp_aliases(target)
    return {"vitalidade": target["vitalidade"], "deficit": deficit, "wound": wound}


# --------------------------------------------------------------------------
# Recuperação (R11) — Integridade + Ferimentos
# --------------------------------------------------------------------------
def recover_integrity(defense: dict, rest: str = "curto") -> None:
    """Descanso curto recupera metade da Integridade máx (arredonda p/ cima);
    longo recupera tudo. Sai de Comprometida se voltar acima de 0."""
    if not defense:
        return
    imax = int(defense.get("integridade_max", 0))
    if rest == "longo":
        defense["integridade_atual"] = imax
    else:
        cur = int(defense.get("integridade_atual", 0))
        defense["integridade_atual"] = min(imax, cur + -(-imax // 2))  # ceil(imax/2)
    if defense["integridade_atual"] > 0:
        defense["comprometida"] = False


def rest_treat_wounds(target: dict, rest: str = "curto", *,
                      has_kit: bool = False, is_medic: bool = False) -> dict:
    """R11: descanso curto/longo remove Leve; Grave precisa kit (suprime + agenda,
    1 carga); Crítico só o Médico com kit trata de fato (2 cargas), comum estabiliza."""
    fer = target.setdefault("ferimentos", {"leve": [], "grave": [], "critico": []})
    for c in ("leve", "grave", "critico"):
        fer.setdefault(c, [])
    kit_cargas = 0
    removidos = {"leve": 0, "grave": 0, "critico": 0}

    # Leve: removido grátis em descanso curto OU longo
    removidos["leve"] = len(fer["leve"])
    fer["leve"] = []

    if rest == "longo":
        # remove Graves suprimidos agendados; e trata o restante se houver kit
        antes = len(fer["grave"])
        fer["grave"] = [w for w in fer["grave"] if not w.get("suprimida")]
        removidos["grave"] += antes - len(fer["grave"])

    if has_kit:
        for w in fer["grave"]:
            if not w.get("suprimida"):
                w["suprimida"] = True
                kit_cargas += 1
        if is_medic:
            antes = len(fer["critico"])
            fer["critico"] = [w for w in fer["critico"] if False]  # tratado de fato
            tratados = antes - len(fer["critico"])
            removidos["critico"] += tratados
            kit_cargas += 2 * tratados
        else:
            for w in fer["critico"]:
                w["suprimida"] = True  # comum só estabiliza

    return {"removidos": removidos, "kit_cargas": kit_cargas}
