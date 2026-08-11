"""Helpers determinísticos compartilhados após o cutover do conflito v2.

O motor de rodada vive em `services/conflict_orchestrator.py`; este módulo reteve
somente dados/condições, passivas de classe/item e Entropia/Carga do Abismo.
O antigo pipeline d20+AC/cooldowns foi removido pela spec conflito-13.
"""
import random
import re
from typing import Dict, List, Optional, Tuple

from gamedata import ARTIFACTS_DB, CLASSES

# Fase 4.2: nomes canônicos das condições de controle
_CONTROL_NAMES = {"stun": "Atordoado", "root": "Enredado", "fear": "Medo"}

_ATTR_ALIASES = {
    "strength": "str", "força": "str", "forca": "str",
    "dexterity": "dex", "destreza": "dex",
    "constitution": "con", "constituição": "con", "constituicao": "con",
    "intelligence": "int", "inteligência": "int", "inteligencia": "int",
    "wisdom": "wis", "sabedoria": "wis",
    "charisma": "cha", "carisma": "cha",
}


# --------------------------------------------------------------------------
# Atributos / dados
# --------------------------------------------------------------------------
def get_mod(score: int) -> int:
    return (int(score) - 10) // 2


def normalize_attr(attr: str) -> str:
    return _ATTR_ALIASES.get(str(attr).lower(), str(attr).lower())


def attr_mods(attributes: Dict) -> Dict[str, int]:
    """Mods normalizados (str/dex/con/int/wis/cha). Ausente -> 0.
    LEGADO — usado só pelo INIMIGO (attributes D&D). O jogador usa Virtudes."""
    out = {k: 0 for k in ("str", "dex", "con", "int", "wis", "cha")}
    for k, v in (attributes or {}).items():
        nk = normalize_attr(k)
        if nk in out:
            try:
                out[nk] = get_mod(v)
            except (TypeError, ValueError):
                pass
    return out


def virtude_mods(virtudes: Dict) -> Dict[str, int]:
    """spec conflito-01: mapeia as 5 Virtudes (0-5) para os mods legados que o
    motor antigo espera (str/dex/con/int/wis/cha). Ponte transicional até a
    fórmula 2d10+Virtude da conflito-04. mente cobre int E wis (sem Virtude
    dedicada de percepção)."""
    v = virtudes or {}
    return {
        "str": int(v.get("forca", 0) or 0),
        "dex": int(v.get("agilidade", 0) or 0),
        "con": int(v.get("corpo", 0) or 0),
        "int": int(v.get("mente", 0) or 0),
        "wis": int(v.get("mente", 0) or 0),
        "cha": int(v.get("carisma", 0) or 0),
    }


def actor_mods(actor: Dict) -> Dict[str, int]:
    """Mods de combate do ator. Jogador tem `virtudes` (Virtude->mod); inimigo/
    aliado legado tem `attributes` (D&D). NUNCA lê `attributes` do jogador (R8)."""
    if actor.get("virtudes"):
        return virtude_mods(actor["virtudes"])
    return attr_mods(actor.get("attributes", {}))


def early_game_damage_bonus(level: int) -> int:
    """Piso temporário de agência: +2 no nível 1–2, +1 no 3, zero no 4+.

    Baseline real 20260720-093014: personagens entravam no próximo conflito
    ainda feridos e demoravam rodadas demais para encerrar ameaças comuns. O
    bônus vale somente para dano causado pelo jogador e desaparece ao crescer.
    """
    current = max(1, int(level or 1))
    if current <= 2:
        return 2
    if current == 3:
        return 1
    return 0


def roll_dice_numeric(formula: str) -> Tuple[int, str]:
    """Soma todas as expressões NdM(+/-K) de `formula`. Retorna (total, detalhe)."""
    total = 0
    details: List[str] = []
    for m in re.finditer(r"(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?", str(formula)):
        count, sides = int(m.group(1)), int(m.group(2))
        rolls = [random.randint(1, sides) for _ in range(count)]
        sub = sum(rolls)
        if m.group(3) == "+":
            sub += int(m.group(4))
        elif m.group(3) == "-":
            sub -= int(m.group(4))
        total += sub
        details.append(f"{m.group(0)}={sub}{rolls}")
    return max(0, total), " ".join(details)


def resolve_damage_formula(formula: str, actor: Dict) -> Tuple[int, str]:
    """Substitui placeholders `str_mod`/`dex_mod`/... pelos mods reais e rola."""
    mods = actor_mods(actor)
    text = str(formula or "0")
    for key, val in mods.items():
        text = re.sub(rf"\b{key}_mod\b", str(val), text)
    # placeholders que sobraram (ex.: nivel) -> 0
    text = re.sub(r"\b[a-zA-Z_]+_mod\b", "0", text)
    if not re.search(r"\d+d\d+", text):
        # fórmula sem dados (só um número/buff) -> tenta inteiro
        n = re.search(r"-?\d+", text)
        v = int(n.group(0)) if n else 0
        return max(0, v), text
    return roll_dice_numeric(text)


# --------------------------------------------------------------------------
# Cura / recuperação de recurso (mecânica determinística; o engine não tinha)
# --------------------------------------------------------------------------








# --------------------------------------------------------------------------
# Condições / DoT
# --------------------------------------------------------------------------
def parse_condition(text: str, source: str = "") -> Dict:
    """
    Converte um efeito textual legado em Condition estruturada.
    Ex.: "Sangramento (3 dano/turno)"  -> dot=3, duration=3
         "+5 Dano por 3 turnos"        -> dot=0, duration=3 (buff)
         "Sofre 5 dano"                -> dot=0, duration=1 (efeito imediato)
    """
    t = str(text).strip()
    dot = 0
    duration = 3  # padrão razoável

    m_dot = re.search(r"(\d+)\s*dano\s*/\s*turno", t, re.IGNORECASE)
    if m_dot:
        dot = int(m_dot.group(1))

    m_dur = re.search(r"por\s+(\d+)\s*turno", t, re.IGNORECASE)
    if m_dur:
        duration = int(m_dur.group(1))
    elif re.search(r"\(\s*\d+\s*turno", t, re.IGNORECASE):
        m2 = re.search(r"\(\s*(\d+)\s*turno", t, re.IGNORECASE)
        duration = int(m2.group(1))

    # nome curto: parte antes do parêntese / número
    name = re.split(r"[(\d]", t, maxsplit=1)[0].strip(" +-") or t
    cond = {"name": name, "dot": dot, "duration": duration, "source": source}

    # Fase 4.2: fallback tipado p/ strings legadas — "+5 Dano por 3 turnos" vira
    # {stat: "damage", delta: 5} (lido por condition_modifiers). Habilidade nova
    # usa `effects` tipado direto; isto cobre só o acervo textual antigo.
    low = t.lower()
    m_stat = re.search(r"([+-]\s*\d+)\s*(dano|defesa|de\s*acerto|acerto)", low)
    if m_stat and not dot:
        delta = int(m_stat.group(1).replace(" ", ""))
        word = m_stat.group(2)
        cond["stat"] = ("damage" if "dano" in word
                        else "ac" if "defesa" in word else "attack")
        cond["delta"] = delta
    if re.search(r"atordoa", low):
        cond["control"] = "stun"
        cond["name"] = _CONTROL_NAMES["stun"]
    elif re.search(r"enredad|enraiza|agarrad", low):
        cond["control"] = "root"
        cond["name"] = _CONTROL_NAMES["root"]
    elif re.search(r"\bmedo\b|apavora|aterroriza", low):
        cond["control"] = "fear"
        cond["name"] = _CONTROL_NAMES["fear"]
    return cond


def class_passives(entity: Dict) -> List[Dict]:
    """Fase 4.2: passive_effects data-driven da classe (classes.json). [] p/ inimigos."""
    cname = entity.get("class_name")
    if not cname:
        return []
    return (CLASSES.get(cname) or {}).get("passive_effects") or []


def learned_passives(entity: Dict, *, abilities_db=None) -> List[Dict]:
    """Compatibilidade do agregador de passivas após o cutover.

    Passivas de Cartas usam o catálogo v4 e são resolvidas pelo motor de Cartas;
    aqui sobrevivem somente passivas de classe e item no vocabulário antigo.
    """
    return []


def item_passives(entity: Dict, *, artifacts_db=None) -> List[Dict]:
    """spec itens-vivos-e-luz (R1): passive_effects dos itens EQUIPADOS (slots).
    Mesmo vocabulário das passivas de classe/habilidade. Sem `equipment` (fichas
    antigas), cai no scan legado do inventário — igual a compute_player_combat_stats.
    Inimigo não tem equipment de jogador → [] na prática."""
    db = artifacts_db if artifacts_db is not None else ARTIFACTS_DB
    equipment = entity.get("equipment")
    if isinstance(equipment, dict):
        ids = [v for v in equipment.values() if v]
    else:
        ids = [e.get("id") if isinstance(e, dict) else e
               for e in (entity.get("inventory") or [])]
    out: List[Dict] = []
    for iid in ids:
        item = db.get(iid) or {}
        # só passivas TIPADAS (dict); legado tem strings de flavor (ex.: 'corda')
        out.extend(pe for pe in (item.get("mechanics") or {}).get("passive_effects") or []
                   if isinstance(pe, dict))
    return out


def player_passives(entity: Dict, *, abilities_db=None) -> List[Dict]:
    """Passivas efetivas do JOGADOR: classe + aprendidas na árvore (R2) + itens
    equipados (spec itens-vivos-e-luz R1). Callsites de combate do jogador leem
    daqui; inimigos seguem em class_passives (inimigo não tem árvore nem slots)."""
    return (class_passives(entity)
            + learned_passives(entity, abilities_db=abilities_db)
            + item_passives(entity))


def condition_modifiers(entity: Dict) -> Dict[str, int]:
    """Fase 4.2: soma dos deltas das condições ativas por stat.

    Buff/debuff tipado ({stat, delta}) entra direto; `fear` embute -2 de acerto.
    """
    out = {"damage": 0, "ac": 0, "attack": 0, "save": 0}
    for c in entity.get("active_conditions", []) or []:
        stat = c.get("stat")
        if stat in out:
            try:
                out[stat] += int(c.get("delta", 0) or 0)
            except (TypeError, ValueError):
                pass
        if c.get("control") == "fear":
            out["attack"] -= 2
    return out


def has_control(entity: Dict, kind: str) -> bool:
    """Fase 4.2: True se há condição de controle ativa ("stun"/"root"/"fear")."""
    return any(c.get("control") == kind
               for c in entity.get("active_conditions", []) or [])


def is_condition_resisted(entity: Dict, cond_name: str) -> bool:
    """True se o nome da condição bate (substring) com um resist do alvo
    (racial 2.5b em `condition_resists` OU passiva de classe 4.2 trigger=resist)."""
    name = str(cond_name or "").lower()
    resists = [str(r).lower() for r in entity.get("condition_resists", []) or []]
    resists += [str(pe.get("name", "")).lower() for pe in player_passives(entity)
                if pe.get("trigger") == "resist"]
    return any(r and r in name for r in resists)


def apply_condition(entity: Dict, cond: Dict) -> str:
    """Anexa/atualiza uma condição no alvo. Refresca duração se já existir.

    Fase 2.5b: resists raciais (`entity["condition_resists"]`) anulam a condição
    por substring do nome (ex.: Anão da Fuligem ignora 'veneno')."""
    if is_condition_resisted(entity, cond.get("name", "")):
        return f"{entity.get('name','Alvo')} resiste a {cond.get('name','condição')} (trait racial)"
    conds = entity.setdefault("active_conditions", [])
    for c in conds:
        if c.get("name", "").lower() == cond.get("name", "").lower():
            c["duration"] = max(c.get("duration", 0), cond.get("duration", 0))
            c["dot"] = max(c.get("dot", 0), cond.get("dot", 0))
            return f"{entity.get('name','Alvo')}: condição {cond['name']} renovada"
    conds.append(dict(cond))
    return f"{entity.get('name','Alvo')}: ganha condição {cond['name']}"


def tick_conditions(entity: Dict, *, rng=None) -> List[str]:
    """Aplica DoT, decrementa duração, remove expiradas. Mutação in-place."""
    logs: List[str] = []
    survivors: List[Dict] = []
    name = entity.get("name", "Alvo")
    for c in entity.get("active_conditions", []) or []:
        dot = int(c.get("dot", 0) or 0)
        if dot > 0:
            if entity.get("vitalidade") is not None:
                from services.conflict_damage import resolve_damage_and_wounds
                dres = resolve_damage_and_wounds(
                    entity,
                    damage_base=dot,
                    damage_type=str(c.get("damage_type") or "cortante"),
                    ignore_resistance=True,
                    defensavel=False,
                    directed_region=None,
                    rng=rng,
                )
                logs.append(
                    f"{name} sofre {dot} de {c.get('name','condição')} "
                    f"(Vitalidade {dres['vitalidade']})")
            else:
                # Compatibilidade estrita com fichas anteriores ao cutover.
                entity["hp"] = max(0, int(entity.get("hp", 0)) - dot)
                logs.append(
                    f"{name} sofre {dot} de {c.get('name','condição')} "
                    f"(HP {entity['hp']})")
        c["duration"] = int(c.get("duration", 0)) - 1
        if c["duration"] > 0:
            survivors.append(c)
        else:
            logs.append(f"{name}: {c.get('name','condição')} terminou")
    entity["active_conditions"] = survivors
    if (entity.get("vitalidade") is None
            and int(entity.get("hp", 1)) <= 0
            and entity.get("status") == "ativo"):
        entity["status"] = "morto"
        logs.append(f"{name} sucumbe aos efeitos.")
    return logs


# --------------------------------------------------------------------------
# Iniciativa
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Recursos / cooldowns
# --------------------------------------------------------------------------








# --------------------------------------------------------------------------
# Entropia + Carga do Abismo (spec refatoracao-sistema-classes, etapas 3/4)
#
# Config TIPADA por classe (entropy_trigger/special_rule/abyss) lida SÓ aqui —
# a IA nunca escolhe número nem decide se um gatilho disparou. Campos transitórios
# (prefixo "_") não persistem no save. Player sem classe das 5 → tudo no-op.
# --------------------------------------------------------------------------
_ABYSS_TIERS = ("nenhum", "leve", "moderado", "severo")

# spec fiacao-regras-orfas-classes (R1): chance BASE de o provocado atacar o
# provocador (escala com taunt_aggro_multiplier; teto 0.9).
# spec fiacao-regras-orfas-classes (R4): registro dado↔motor. TODO kind/trigger
# declarado nos dados de classe, itens ou Cartas precisa
# constar aqui — o teste anti-órfão compara e fica vermelho se um kind novo
# aparecer nos dados sem handler no motor. Manter JUNTO dos handlers.
_DOC_ONLY_SPECIAL_RULES = {
    # kinds informativos: a mecânica vive em outro lugar —
    # heal_abyss = efeito reduce_ally_abyss da purga_da_carga;
    # domain_decay = overrides de entropy_trigger por branch do Corruptor.
    "heal_abyss", "domain_decay",
}
HANDLED_KINDS: Dict[str, set] = {
    "entropy_trigger": {"on_damage_taken", "on_self_harm", "on_decay_nearby",
                        "on_channel", "on_ally_suffer"},
    "special_rule": {"taunt_scales_with_entropy", "blood_leak", "boiler"}
                    | _DOC_ONLY_SPECIAL_RULES,
    "consequence": {"insonia", "cicatriz", "transformacao", "dependencia", "recidiva"},
    "effect": {"buff", "debuff", "dot", "control", "heal", "reduce_ally_abyss"},
    "passive_trigger": {"always", "damage_type", "resist", "initiative_attr",
                        "heal_bonus_low", "melee_retaliate", "basic_attack_dot",
                        "hp_as_mana", "entropy_max_bonus", "entropy_on_kill",
                        "entropy_cost_reduction", "charge_discount", "carga_embrace",
                        # spec itens-vivos-e-luz: passivas de item
                        "perception", "light"},
}


def _abilities_db(explicit=None) -> Dict:
    if explicit is not None:
        return explicit
    from services.cards import all_cards
    return all_cards()


def _classes_db(explicit=None) -> Dict:
    return explicit if explicit is not None else CLASSES


def _branch_of(player: Dict, adb: Dict) -> Optional[str]:
    """Subclasse = primeira Carta conhecida com `subclasse`."""
    if player.get("subclass"):
        return str(player["subclass"])
    for cid in player.get("known_cards") or []:
        branch = (adb.get(cid) or {}).get("subclasse")
        if branch:
            return str(branch)
    return None


def entropy_config(player: Dict, *, classes_db=None, abilities_db=None) -> Dict:
    """Merge da entropy_trigger/special_rule/abyss da classe com overrides do branch.
    Fonte ÚNICA de números — nunca hardcode em callsite."""
    cdb = _classes_db(classes_db)
    adb = _abilities_db(abilities_db)
    cd = cdb.get(player.get("class_name", "")) or {}
    cfg = {
        "entropy_trigger": dict(cd.get("entropy_trigger") or {}),
        "special_rule": dict(cd.get("special_rule") or {}),
        "abyss": dict(cd.get("abyss") or {}),
    }
    branch = _branch_of(player, adb)
    if branch:
        overrides = ((cd.get("branches") or {}).get(branch) or {}).get("overrides") or {}
        for block, ov in overrides.items():
            if block in cfg and isinstance(ov, dict):
                cfg[block] = {**cfg[block], **ov}
    return cfg


def abyss_tier(player: Dict, *, classes_db=None) -> str:
    """'nenhum'|'leve'|'moderado'|'severo' a partir de abyss_charge + thresholds."""
    charge = int(player.get("abyss_charge", 0) or 0)
    thr = (entropy_config(player, classes_db=classes_db).get("abyss") or {}).get(
        "thresholds") or {"leve": 1, "moderado": 4, "severo": 7}
    tier = "nenhum"
    for name in ("leve", "moderado", "severo"):
        if charge >= int(thr.get(name, 10 ** 9)):
            tier = name
    return tier


def _tier_index(tier: str) -> int:
    return _ABYSS_TIERS.index(tier) if tier in _ABYSS_TIERS else 0


def reset_entropy_turn(player: Dict) -> None:
    """Zera o contador de ativações do gatilho no turno (chamar no início do round)."""
    player["_entropy_trigger_turn"] = 0


def apply_entropy_trigger(player: Dict, event: Dict, logs: Optional[List[str]] = None,
                          *, classes_db=None, abilities_db=None) -> List[str]:
    """Aciona o gatilho da classe se `event["kind"]` casa. Soma Entropia (clamp em
    max_entropy) e Carga (charge_per, respeitando per_turn_cap por turno). Muta player.
    `event` = {"kind": ..., "amount"?: int, "decay_kind"?: str}."""
    logs = logs if logs is not None else []
    cfg = entropy_config(player, classes_db=classes_db, abilities_db=abilities_db)
    trig = cfg.get("entropy_trigger") or {}
    kind = trig.get("kind")
    if not kind or event.get("kind") != kind:
        return logs
    cap = int(trig.get("per_turn_cap", 10 ** 9) or 10 ** 9)
    used = int(player.get("_entropy_trigger_turn", 0) or 0)
    if used >= cap:
        return logs

    gain = 0
    if kind == "on_damage_taken":
        amount = int(event.get("amount", 0) or 0)
        div = max(1, int(trig.get("damage_divisor", 4) or 4))
        gain = max(int(trig.get("min_gain", 0) or 0), amount // div) if amount > 0 else 0
    elif kind == "on_self_harm":
        gain = int(event.get("amount", 0) or 0) * int(trig.get("gain_per_hp", 1) or 1)
    elif kind == "on_decay_nearby":
        want = str(trig.get("decay_kind", "any") or "any")
        got = str(event.get("decay_kind", "any") or "any")
        if want != "any" and got != "any" and want != got:
            return logs
        gain = int(trig.get("gain", 1) or 1)
    elif kind in ("on_channel", "on_ally_suffer"):
        gain = int(trig.get("gain", 1) or 1)
    if gain <= 0:
        return logs

    mx = int(player.get("max_entropy", 0) or 0)
    before = int(player.get("entropy", 0) or 0)
    player["entropy"] = min(mx, before + gain) if mx > 0 else before + gain
    gained = player["entropy"] - before
    charge_per = int(trig.get("charge_per", 0) or 0)
    # spec arvores-habilidade-classes: passiva charge_discount reduz a Carga ganha
    # por ativação do gatilho (piso 0 — o Abismo pode ser adiado, não enganado de graça).
    for pe in player_passives(player, abilities_db=abilities_db):
        if pe.get("trigger") == "charge_discount":
            charge_per = max(0, charge_per - int(pe.get("delta", 1) or 1))
    if charge_per:
        charge_before = int(player.get("abyss_charge", 0) or 0)
        passive_cap = trig.get("charge_cap")
        if passive_cap is None or charge_before < int(passive_cap):
            player["abyss_charge"] = charge_before + charge_per
            if passive_cap is not None:
                player["abyss_charge"] = min(
                    int(passive_cap), int(player["abyss_charge"])
                )
    player["_entropy_trigger_turn"] = used + 1
    if kind == "on_self_harm" and gained:
        player["_blood_entropy"] = int(player.get("_blood_entropy", 0) or 0) + gained
    logs.append(f"{player.get('name', 'Herói')}: +{gained} Entropia ({kind}); "
                f"Carga do Abismo {player.get('abyss_charge', 0)}")
    return logs


# --- Regras especiais (§3.5) -----------------------------------------------
def taunt_aggro_multiplier(player: Dict, *, classes_db=None) -> float:
    """Devoto: eficácia da provocação = 1 + min(cap, per_entropy*Entropia)."""
    sr = entropy_config(player, classes_db=classes_db).get("special_rule") or {}
    if sr.get("kind") != "taunt_scales_with_entropy":
        return 1.0
    per = float(sr.get("per_entropy", 0) or 0)
    cap = float(sr.get("cap", 0) or 0)
    return 1.0 + min(cap, per * int(player.get("entropy", 0) or 0))


def apply_blood_leak(player: Dict, logs: Optional[List[str]] = None,
                     *, classes_db=None) -> List[str]:
    """Sangromante: ao ser acertado, vaza leak_frac da Entropia de sangue não gasta."""
    logs = logs if logs is not None else []
    sr = entropy_config(player, classes_db=classes_db).get("special_rule") or {}
    if sr.get("kind") != "blood_leak":
        return logs
    blood = int(player.get("_blood_entropy", 0) or 0)
    frac = float(sr.get("leak_frac", 0) or 0)
    lost = int(round(blood * frac))
    if lost <= 0:
        return logs
    player["entropy"] = max(0, int(player.get("entropy", 0) or 0) - lost)
    player["_blood_entropy"] = blood - lost
    logs.append(f"{player.get('name', 'Herói')}: {lost} de Entropia de sangue vaza no golpe.")
    return logs


def arm_boiler(player: Dict, ability: Dict, *, classes_db=None) -> None:
    """Arcanista: ability marcada `cools` VAZA (desarma); qualquer outra ARMA a caldeira."""
    sr = entropy_config(player, classes_db=classes_db).get("special_rule") or {}
    if sr.get("kind") != "boiler":
        return
    if ability.get("cools"):
        player.pop("_cool_deadline", None)
    else:
        player["_cool_deadline"] = int(sr.get("cool_deadline", 3) or 3)


def tick_boiler(player: Dict, logs: Optional[List[str]] = None,
                *, classes_db=None, rng=None) -> List[str]:
    """Arcanista: decrementa o prazo da caldeira; estoura (auto-dano) se vencer
    sem vazão. Chamar 1x por round do Arcanista."""
    logs = logs if logs is not None else []
    sr = entropy_config(player, classes_db=classes_db).get("special_rule") or {}
    if sr.get("kind") != "boiler" or player.get("_cool_deadline") is None:
        return logs
    deadline = int(player.get("_cool_deadline", 0)) - 1
    if deadline <= 0:
        dmg, _det = roll_dice_numeric(str(sr.get("overload_damage", "2d6")))
        if player.get("vitalidade") is not None:
            from services.conflict_damage import resolve_damage_and_wounds
            dres = resolve_damage_and_wounds(
                player,
                damage_base=dmg,
                damage_type="arcano",
                ignore_resistance=True,
                defensavel=False,
                directed_region=None,
                rng=rng,
            )
            life_label = f"Vitalidade {dres['vitalidade']}"
        else:
            # Compatibilidade de testes/fichas pré-v4 somente.
            player["hp"] = max(0, int(player.get("hp", 0) or 0) - dmg)
            life_label = f"HP {player['hp']}"
        player.pop("_cool_deadline", None)
        logs.append(f"{player.get('name', 'Herói')}: a caldeira ESTOURA — "
                    f"{dmg} de auto-dano ({life_label}).")
    else:
        player["_cool_deadline"] = deadline
    return logs


def reduce_ally_abyss(medic: Dict, ally: Dict, amount: int,
                      *, cost: int = 2) -> Tuple[bool, str]:
    """R9 — Médico gasta Entropia p/ reduzir a Carga do Abismo de um ALIADO.
    Único da classe. Determinístico. Retorna (ok, log)."""
    if medic.get("class_name") != "Médico de Campo":
        return False, "Só o Médico de Campo purga a Carga alheia."
    if int(medic.get("entropy", 0) or 0) < cost:
        return False, "Sem Entropia para purgar a Carga."
    medic["entropy"] = int(medic.get("entropy", 0)) - cost
    before = int(ally.get("abyss_charge", 0) or 0)
    ally["abyss_charge"] = max(0, before - int(amount))
    return True, (f"{medic.get('name', 'Médico')} purga {before - ally['abyss_charge']} "
                  f"de Carga de {ally.get('name', 'aliado')}.")


# --- Consequências de Carga (§3.6) -----------------------------------------
def apply_scar(player: Dict, ability: Dict, logs: Optional[List[str]] = None,
               *, classes_db=None) -> List[str]:
    """Sangromante — Cicatriz: habilidade `peak` reduz max_hp PERMANENTE + soma Carga."""
    logs = logs if logs is not None else []
    ab = entropy_config(player, classes_db=classes_db).get("abyss") or {}
    if ab.get("consequence") != "cicatriz" or not ability.get("peak"):
        return logs
    loss = int((ab.get("params") or {}).get("scar_hp_loss", 3) or 3)
    if player.get("vitalidade") is not None or player.get("virtudes"):
        import gamedata
        player["vitalidade_max_penalty"] = (
            int(player.get("vitalidade_max_penalty", 0) or 0) + loss
        )
        gamedata.sync_vitality(player)
    else:
        # Ficha pré-v4 isolada: mantém o comportamento de leitura histórica.
        player["max_hp"] = max(1, int(player.get("max_hp", 1) or 1) - loss)
        player["hp"] = min(int(player.get("hp", 0) or 0), player["max_hp"])
    player["abyss_charge"] = int(player.get("abyss_charge", 0) or 0) + 1
    logs.append(f"{player.get('name', 'Herói')}: o golpe de pico deixa CICATRIZ "
                f"(−{loss} Vitalidade máx, Carga {player['abyss_charge']}).")
    return logs


def dependencia_cost(player: Dict, cost: int, *, classes_db=None) -> int:
    """Arcanista — Dependência: sem instrumento (weapon) + Carga >= moderado,
    o custo de Entropia sobe por no_instrument_cost_mult."""
    if cost <= 0:
        return cost
    ab = entropy_config(player, classes_db=classes_db).get("abyss") or {}
    if ab.get("consequence") != "dependencia":
        return cost
    has_weapon = bool((player.get("equipment") or {}).get("weapon"))
    if not has_weapon and _tier_index(abyss_tier(player, classes_db=classes_db)) >= _tier_index("moderado"):
        mult = float((ab.get("params") or {}).get("no_instrument_cost_mult", 1.0) or 1.0)
        return int(round(cost * mult))
    return cost


def apply_transformacao(player: Dict, logs: Optional[List[str]] = None,
                        *, classes_db=None, abilities_db=None) -> List[str]:
    """Corruptor — Transformação: por patamar, um debuff conforme o domínio (branch)."""
    logs = logs if logs is not None else []
    ab = entropy_config(player, classes_db=classes_db, abilities_db=abilities_db).get("abyss") or {}
    if ab.get("consequence") != "transformacao":
        return logs
    tier = abyss_tier(player, classes_db=classes_db)
    if tier == "nenhum":
        return logs
    branch = _branch_of(player, _abilities_db(abilities_db)) or "biologia"
    kind = ((ab.get("params") or {}).get("debuff") or {}).get(branch, "defense_penalty")
    mag = {"leve": 1, "moderado": 2, "severo": 3}.get(tier, 1)
    if kind == "save_penalty":
        cond = {"name": "Transformação (Vontade)", "dot": 0, "duration": 2,
                "stat": "save", "delta": -mag}
    elif kind == "extra_dot":
        cond = {"name": "Transformação (Podridão)", "dot": mag, "duration": 2}
    else:  # defense_penalty
        cond = {"name": "Transformação (Def)", "dot": 0, "duration": 2,
                "stat": "ac", "delta": -mag}
    msg = apply_condition(player, cond)
    # spec fiacao (R2): chamada a cada round do Corruptor — renovação silenciosa
    # (loga só quando a condição ENTRA, senão o log repete todo round).
    if "renovada" not in msg:
        logs.append(f"{player.get('name', 'Herói')}: Transformação ({kind}) "
                    f"do domínio {branch} [{tier}].")
    return logs


def apply_entropy_on_kill(player: Dict, dead_count: int,
                          logs: Optional[List[str]] = None) -> List[str]:
    """spec arvores-habilidade-classes: passiva entropy_on_kill — matar inimigo
    devolve Entropia (amount × mortos, clamp em max_entropy). Sem Carga (não é
    gatilho de classe — é colheita)."""
    logs = logs if logs is not None else []
    if dead_count <= 0:
        return logs
    amount = sum(int(pe.get("amount", 1) or 1) for pe in player_passives(player)
                 if pe.get("trigger") == "entropy_on_kill")
    if amount <= 0:
        return logs
    mx = int(player.get("max_entropy", 0) or 0)
    before = int(player.get("entropy", 0) or 0)
    player["entropy"] = min(mx, before + amount * dead_count) if mx > 0 else before
    gained = player["entropy"] - before
    if gained:
        logs.append(f"{player.get('name', 'Herói')}: +{gained} Entropia (colheita da morte)")
    return logs






def check_recidiva(player: Dict, logs: Optional[List[str]] = None,
                   *, classes_db=None) -> Tuple[List[str], Optional[Dict]]:
    """Médico — Recidiva: oculta até cruzar 'severo'; então UM colapso (condição
    forte + evento de crônica). Flag _recidiva_fired impede repetir."""
    logs = logs if logs is not None else []
    ab = entropy_config(player, classes_db=classes_db).get("abyss") or {}
    if ab.get("consequence") != "recidiva" or player.get("_recidiva_fired"):
        return logs, None
    collapse_at = (ab.get("params") or {}).get("collapse_at", "severo")
    if _tier_index(abyss_tier(player, classes_db=classes_db)) < _tier_index(collapse_at):
        return logs, None
    player["_recidiva_fired"] = True
    apply_condition(player, {"name": "Colapso", "dot": 0, "duration": 3,
                             "stat": "attack", "delta": -4})
    logs.append(f"{player.get('name', 'Médico')}: a Recidiva oculta ESTOURA — colapso.")
    event = {"type": "abyss_collapse", "actor_id": "player", "target_id": "player",
             "detail": f"A Carga oculta de {player.get('name', 'o Médico')} estourou em colapso",
             "payload": {}, "source": "combat"}
    return logs, event


# --------------------------------------------------------------------------
# Stats de combate do player (centraliza a lógica antes em combat.py)
# --------------------------------------------------------------------------
def compute_player_combat_stats(player: Dict) -> Dict:
    """AC, bônus de ataque e atributo de ataque a partir do EQUIPAMENTO (Fase 4.3:
    só os slots contam — fim do auto-scan do inventário inteiro). Sem `equipment`
    (fichas antigas em memória/testes), cai no scan legado por compatibilidade."""
    mods = actor_mods(player)
    best_atk_bonus = 0
    ac_bonus = 0
    attack_attr = "str"

    equipment = player.get("equipment")
    if isinstance(equipment, dict):
        equipped_ids = [v for v in equipment.values() if v]
    else:
        # legado: inventário de strings OU estruturado ({id, qty}) sem slots
        equipped_ids = [e.get("id") if isinstance(e, dict) else e
                        for e in (player.get("inventory") or [])]

    for item_id in equipped_ids:
        item = ARTIFACTS_DB.get(item_id)
        if not item:
            continue
        stats = item.get("combat_stats", {})
        if item.get("type") == "weapon":
            b = stats.get("attack_bonus", 0)
            if b > best_atk_bonus or (best_atk_bonus == 0 and "attribute" in stats):
                best_atk_bonus = max(best_atk_bonus, b)
                if "attribute" in stats:
                    attack_attr = normalize_attr(stats["attribute"])
        ac_bonus += stats.get("ac_bonus", 0)

    ac = 10 + mods["dex"] + ac_bonus
    attack = mods.get(attack_attr, 0) + best_atk_bonus + int(player.get("attack_bonus", 0) or 0)

    # Fase 4.2: passivas data-driven (classe + aprendidas na árvore — R2)
    for pe in player_passives(player):
        trig = pe.get("trigger")
        if trig == "always" and pe.get("stat") == "ac":
            ac += int(pe.get("delta", 0) or 0)
        elif trig == "always" and pe.get("stat") == "attack":
            attack += int(pe.get("delta", 0) or 0)
        elif trig == "party_active" and pe.get("stat") == "ac" and player.get("_party_active"):
            # Fase 4.5: Muralha Humana só com aliado AO LADO (flag setada no combate)
            ac += int(pe.get("delta", 0) or 0)
        elif trig == "unarmored_ac_con" and ac_bonus == 0:
            # Guardião: sem armadura, AC = 10 + Dex + Con
            ac = max(ac, 10 + mods["dex"] + mods["con"])
        elif trig == "carga_embrace" and pe.get("stat") in ("ac", "attack"):
            # abraçar o Abismo: patamar de Carga vira bônus (per_tier × tier)
            bonus = int(pe.get("per_tier", 1) or 1) * _tier_index(abyss_tier(player))
            if pe.get("stat") == "ac":
                ac += bonus
            else:
                attack += bonus

    # Fase 4.2: buffs/debuffs ativos (condições tipadas) — fear inclui -2 attack
    cmods = condition_modifiers(player)
    ac += cmods["ac"]
    attack += cmods["attack"]
    # Fase 6.5: clima (flag transitória setada pelo combate; simétrica)
    attack += int(player.get("_env_attack_mod", 0) or 0)

    return {
        "ac": ac,
        "attack": attack,
        "attack_attr": attack_attr,
    }




# --------------------------------------------------------------------------
# Resolução de turnos
# --------------------------------------------------------------------------
def _condition_from_effect(eff: Dict, source: str) -> Optional[Dict]:
    """Fase 4.2: effect tipado (schema 4.1) -> Condition. heal não vira condição."""
    kind = eff.get("kind")
    dur = int(eff.get("duration", 1) or 1)
    delta = int(eff.get("delta", 0) or 0)
    if kind == "dot":
        return {"name": source, "dot": max(0, delta), "duration": dur, "source": source}
    if kind in ("buff", "debuff"):
        stat = eff.get("stat")
        label = {"damage": "Dano", "ac": "Defesa", "attack": "Acerto", "save": "Save"}.get(stat, "")
        signed = f"+{delta}" if delta >= 0 else str(delta)
        return {"name": f"{source} ({signed} {label})".strip(), "dot": 0, "duration": dur,
                "source": source, "stat": stat, "delta": delta}
    if kind == "control":
        ckind = str(eff.get("control") or "stun")
        return {"name": _CONTROL_NAMES.get(ckind, ckind), "dot": 0, "duration": dur,
                "source": source, "control": ckind}
    return None
