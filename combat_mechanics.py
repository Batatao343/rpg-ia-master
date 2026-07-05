"""
combat_mechanics.py
Núcleo DETERMINÍSTICO do combate — Python puro, sem IA.

A IA só identifica a ação (linguagem natural -> ability_id) e narra o resultado.
Tudo que é mecânica (iniciativa, dano, custos, cooldowns, condições/DoT, turno do
inimigo) é resolvido aqui, de forma testável offline e independente de quota.

Convenções:
- Funções mutam os dicts passados (player/enemy) e RETORNAM uma lista de logs
  mecânicos (strings curtas) que o narrador transforma em prosa.
- `active_conditions` segue o schema `Condition` (state.py):
  {"name": str, "dot": int, "duration": int, "source": str}
"""
import random
import re
from typing import Dict, List, Optional, Tuple

from gamedata import ARTIFACTS_DB, CLASSES

COOLDOWN_DEFAULT = 2  # turnos de recarga para habilidades com custo

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
    """Mods normalizados (str/dex/con/int/wis/cha). Ausente -> 0."""
    out = {k: 0 for k in ("str", "dex", "con", "int", "wis", "cha")}
    for k, v in (attributes or {}).items():
        nk = normalize_attr(k)
        if nk in out:
            try:
                out[nk] = get_mod(v)
            except (TypeError, ValueError):
                pass
    return out


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
    mods = attr_mods(actor.get("attributes", {}))
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
def _is_healing(ability: Dict) -> bool:
    """Cura = damage_type 'Cura'/'Heal'. (Fórmula negativa sozinha é ambígua: '-5 Dano
    Verdadeiro' é custo, não cura — por isso o tipo decide.)"""
    return str(ability.get("damage_type", "")).lower() in ("cura", "heal")


def roll_magnitude(formula: str, actor: Dict) -> Tuple[int, str]:
    """Igual a resolve_damage_formula, mas pelo VALOR ABSOLUTO (cura usa fórmula negativa)."""
    mods = attr_mods(actor.get("attributes", {}))
    text = str(formula or "0")
    for key, val in mods.items():
        text = re.sub(rf"\b{key}_mod\b", str(val), text)
    text = re.sub(r"\b[a-zA-Z_]+_mod\b", "0", text)
    text = text.replace("-", "")  # magnitude: ignora sinais (cura é positiva)
    if not re.search(r"\d+d\d+", text):
        n = re.search(r"\d+", text)
        v = int(n.group(0)) if n else 0
        return v, text
    return roll_dice_numeric(text)


def _heal(entity: Dict, amount: int) -> int:
    """Soma HP até o teto (max_hp). Retorna o quanto curou de fato."""
    if amount <= 0:
        return 0
    cur = int(entity.get("hp", 0))
    ceiling = int(entity.get("max_hp", cur + amount))
    new = min(ceiling, cur + amount)
    entity["hp"] = new
    return new - cur


def _apply_resource_recovery(player: Dict, conditions: List[str]) -> List[str]:
    """'Recupera N Estamina/Mana/Vigor' -> restaura o recurso (clampado ao máximo)."""
    logs: List[str] = []
    for c in conditions or []:
        m = re.search(r"recupera\s+(\d+)\s*(estamina|vigor|mana)", str(c), re.IGNORECASE)
        if not m:
            continue
        amount = int(m.group(1))
        field = "mana" if "mana" in m.group(2).lower() else "stamina"
        mx = int(player.get(f"max_{field}", player.get(field, 0) + amount))
        player[field] = min(mx, int(player.get(field, 0)) + amount)
        logs.append(f"{player.get('name','Herói')} recupera {amount} de {field} ({player[field]}/{mx})")
    return logs


# --------------------------------------------------------------------------
# Condições / DoT
# --------------------------------------------------------------------------
def parse_condition(text: str, source: str = "") -> Dict:
    """
    Converte uma string de `player_abilities.json` em Condition estruturada.
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
    resists += [str(pe.get("name", "")).lower() for pe in class_passives(entity)
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


def tick_conditions(entity: Dict) -> List[str]:
    """Aplica DoT, decrementa duração, remove expiradas. Mutação in-place."""
    logs: List[str] = []
    survivors: List[Dict] = []
    name = entity.get("name", "Alvo")
    for c in entity.get("active_conditions", []) or []:
        dot = int(c.get("dot", 0) or 0)
        if dot > 0:
            entity["hp"] = max(0, int(entity.get("hp", 0)) - dot)
            logs.append(f"{name} sofre {dot} de {c.get('name','condição')} (HP {entity['hp']})")
        c["duration"] = int(c.get("duration", 0)) - 1
        if c["duration"] > 0:
            survivors.append(c)
        else:
            logs.append(f"{name}: {c.get('name','condição')} terminou")
    entity["active_conditions"] = survivors
    if int(entity.get("hp", 1)) <= 0 and entity.get("status") == "ativo":
        entity["status"] = "morto"
        logs.append(f"{name} sucumbe aos efeitos.")
    return logs


# --------------------------------------------------------------------------
# Iniciativa
# --------------------------------------------------------------------------
def roll_initiative(player: Dict, enemies: List[Dict],
                    allies: Optional[List[Dict]] = None) -> List[Dict]:
    """d20 + mod de destreza por combatente. Ordena desc. Lados: hero/ally/enemy.

    Fase 4.2: passiva `initiative_attr` (Arcanista) usa o melhor entre dex e o
    atributo declarado. Fase 4.5: aliados entram no lado 'ally'."""
    order: List[Dict] = []
    p_mods = attr_mods(player.get("attributes", {}))
    p_init = p_mods["dex"]
    for pe in class_passives(player):
        if pe.get("trigger") == "initiative_attr":
            p_init = max(p_init, p_mods.get(normalize_attr(pe.get("attr", "dex")), 0))
    order.append({"id": "player", "name": player.get("name", "Herói"),
                  "side": "hero", "init": random.randint(1, 20) + p_init})
    for a in allies or []:
        a_dex = attr_mods(a.get("attributes", {}))["dex"]
        order.append({"id": a.get("id", a.get("name", "?")), "name": a.get("name", "Aliado"),
                      "side": "ally", "init": random.randint(1, 20) + a_dex})
    for e in enemies:
        e_dex = attr_mods(e.get("attributes", {}))["dex"]
        order.append({"id": e.get("id", e.get("name", "?")), "name": e.get("name", "Inimigo"),
                      "side": "enemy", "init": random.randint(1, 20) + e_dex})
    order.sort(key=lambda x: x["init"], reverse=True)
    return order


# --------------------------------------------------------------------------
# Recursos / cooldowns
# --------------------------------------------------------------------------
def _resource_field(resource_type: str) -> Optional[str]:
    rt = str(resource_type or "").lower()
    if "estamina" in rt or "stamina" in rt or "vigor" in rt:
        return "stamina"
    if "mana" in rt:
        return "mana"
    return None


def is_on_cooldown(player: Dict, ability_id: str) -> bool:
    return int(player.get("ability_cooldowns", {}).get(ability_id, 0)) > 0


def spend_resources(player: Dict, ability_id: str, ability: Dict) -> Tuple[bool, str]:
    """Checa cooldown + custo; se ok, deduz recurso e arma o cooldown."""
    if is_on_cooldown(player, ability_id):
        turns = player["ability_cooldowns"][ability_id]
        return False, f"{ability.get('name', ability_id)} em recarga ({turns} turno(s))"

    cost = int(ability.get("cost", 0) or 0)
    field = _resource_field(ability.get("resource_type", "")) if cost > 0 else None
    if field and int(player.get(field, 0)) < cost:
        # Fase 4.2: Sangromante (hp_as_mana) paga a mana que falta com HP (rate HP = 1 mana)
        if field == "mana":
            pe = next((p for p in class_passives(player)
                       if p.get("trigger") == "hp_as_mana"), None)
            if pe:
                rate = int(pe.get("rate", 2) or 2)
                missing = cost - int(player.get("mana", 0))
                hp_cost = missing * rate
                if int(player.get("hp", 0)) > hp_cost:
                    paid_mana = int(player.get("mana", 0))
                    player["mana"] = 0
                    player["hp"] = int(player.get("hp", 0)) - hp_cost
                    player.setdefault("ability_cooldowns", {})[ability_id] = COOLDOWN_DEFAULT
                    return True, (f"Sacrifício de Sangue: paga {paid_mana} de mana e "
                                  f"{hp_cost} de HP (HP {player['hp']})")
        return False, f"Sem {field} para {ability.get('name', ability_id)} ({player.get(field,0)}/{cost})"

    if field and cost > 0:
        player[field] = int(player.get(field, 0)) - cost
        player.setdefault("ability_cooldowns", {})[ability_id] = COOLDOWN_DEFAULT
        return True, f"Gasta {cost} de {field}"
    return True, ""


def tick_cooldowns(player: Dict) -> None:
    cds = player.get("ability_cooldowns", {})
    for k in list(cds.keys()):
        cds[k] -= 1
        if cds[k] <= 0:
            del cds[k]


# --------------------------------------------------------------------------
# Stats de combate do player (centraliza a lógica antes em combat.py)
# --------------------------------------------------------------------------
def compute_player_combat_stats(player: Dict) -> Dict:
    """AC, bônus de ataque e atributo de ataque a partir do EQUIPAMENTO (Fase 4.3:
    só os slots contam — fim do auto-scan do inventário inteiro). Sem `equipment`
    (fichas antigas em memória/testes), cai no scan legado por compatibilidade."""
    mods = attr_mods(player.get("attributes", {}))
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

    # Fase 4.2: passivas data-driven da classe
    for pe in class_passives(player):
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


def _find_target(enemies: List[Dict], target: str) -> Optional[Dict]:
    t = str(target or "").lower()
    alive = [e for e in enemies if e.get("status") == "ativo"]
    for e in alive:
        if t and (t in e.get("name", "").lower() or t in str(e.get("id", "")).lower()):
            return e
    return alive[0] if alive else None


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


def _split_typed_effects(ability: Dict) -> Tuple[List[Dict], List[Dict]]:
    """(efeitos no PRÓPRIO conjurador, efeitos HOSTIS no alvo)."""
    selfs, hostiles = [], []
    for eff in ability.get("effects") or []:
        if not isinstance(eff, dict):
            continue
        if eff.get("kind") == "buff":
            selfs.append(eff)
        elif eff.get("kind") in ("debuff", "dot", "control"):
            hostiles.append(eff)
    return selfs, hostiles


def _apply_self_costs(player: Dict, conditions: List, logs: List[str]) -> None:
    """Custos textuais no conjurador: 'Sofre N dano' / 'Custa N HP'."""
    for c in conditions or []:
        m = re.search(r"(?:sofre|custa)\s+(\d+)\s*(?:de\s*)?(?:dano|hp)", str(c), re.IGNORECASE)
        if m:
            player["hp"] = max(0, int(player.get("hp", 0)) - int(m.group(1)))
            logs.append(f"{player.get('name','Herói')} paga {m.group(1)} de HP (HP {player['hp']})")


def damage_bonus(player: Dict, ability: Dict) -> Tuple[int, List[str]]:
    """Fase 4.2: bônus de dano de condições ativas + passivas (always / damage_type)."""
    notes: List[str] = []
    bonus = condition_modifiers(player)["damage"]
    if bonus:
        notes.append(f"{'+' if bonus >= 0 else ''}{bonus} de condições")
    dtype = str(ability.get("damage_type", "")).lower()
    for pe in class_passives(player):
        trig = pe.get("trigger")
        if trig == "always" and pe.get("stat") == "damage":
            d = int(pe.get("delta", 0) or 0)
            bonus += d
            notes.append(f"+{d} passiva")
        elif trig == "damage_type" and str(pe.get("damage_type", "")).lower() in dtype and dtype:
            d = int(pe.get("delta", 0) or 0)
            bonus += d
            notes.append(f"+{d} {pe.get('damage_type')}")
    return bonus, notes


def resolve_player_action(player: Dict, enemies: List[Dict], action: Dict,
                          abilities_db: Dict) -> List[str]:
    """
    action = {"ability_id", "target", "is_allowed", "reason"}.
    Gating -> recursos/cooldown -> ataque (d20 vs AC) -> dano (com save real) -> condições.
    Mutação in-place de player/enemies. Retorna logs mecânicos.
    """
    logs: List[str] = []

    if not action.get("is_allowed", True):
        logs.append(f"Ação falha: {action.get('reason', 'não é possível para esta classe.')}")
        return logs

    ability_id = action.get("ability_id") or "ataque_basico"
    ability = abilities_db.get(ability_id) or abilities_db.get("ataque_basico") or {
        "name": "Ataque Improvisado", "cost": 0, "resource_type": "Nenhum",
        "damage_formula": "1d4+str_mod", "conditions": [], "save_stat": None,
    }

    ok, msg = spend_resources(player, ability_id, ability)
    if msg:
        logs.append(msg)
    if not ok:
        return logs

    name = ability.get("name", ability_id)
    formula = ability.get("damage_formula", "0")
    conditions = ability.get("conditions", [])

    # CURA: soma HP no PRÓPRIO herói (não ataca o inimigo). Não precisa de alvo.
    if _is_healing(ability):
        heal, detail = roll_magnitude(formula, player)
        # "Ganha N HP Temporário" tratado como cura simples (sem pool separado).
        for c in conditions:
            mt = re.search(r"ganha\s+(\d+)\s*hp", str(c), re.IGNORECASE)
            if mt:
                heal += int(mt.group(1))
        # Fase 4.2: Médico (heal_bonus_low) — alvo abaixo do limiar cura mais.
        for pe in class_passives(player):
            if pe.get("trigger") == "heal_bonus_low":
                thr = float(pe.get("threshold", 0.25) or 0.25)
                if int(player.get("hp", 0)) < thr * max(1, int(player.get("max_hp", 1))):
                    heal += int(pe.get("delta", 5) or 5)
                    detail = f"{detail} +{pe.get('delta', 5)} triagem".strip()
        # custo textual ("Custa 4 HP" da Panaceia Negra) ANTES da cura
        _apply_self_costs(player, conditions, logs)
        done = _heal(player, heal)
        logs.append(f"{player.get('name','Herói')} usa {name}: recupera {done} de HP (HP {player.get('hp')}) [{detail}]")
        logs += _apply_resource_recovery(player, conditions)
        # buffs tipados embutidos na cura (ex.: Milagre de Campo: +2 Defesa)
        for eff in ability.get("effects") or []:
            if isinstance(eff, dict) and eff.get("kind") == "buff":
                cond = _condition_from_effect(eff, name)
                if cond:
                    logs.append(apply_condition(player, cond))
        # condições não-danosas (ex.: "Remove Sangramento")
        for c in conditions:
            mr = re.search(r"remove\s+([\wçãéõ ]+)", str(c), re.IGNORECASE)
            if mr:
                alvo = mr.group(1).strip().lower()
                before = player.get("active_conditions", []) or []
                player["active_conditions"] = [x for x in before if alvo not in x.get("name", "").lower()]
                if len(player["active_conditions"]) < len(before):
                    logs.append(f"{player.get('name','Herói')}: removeu {mr.group(1).strip()}")
        return logs

    target = _find_target(enemies, action.get("target", ""))
    if not target:
        logs.append("Não há alvo válido.")
        return logs

    pstats = compute_player_combat_stats(player)

    # Fase 4.2: effects tipado tem PRECEDÊNCIA sobre o parse textual das conditions
    # (evita dupla aplicação — a string vira só flavor/custos quando há effects).
    self_effs, hostile_effs = _split_typed_effects(ability)
    has_typed = bool(self_effs or hostile_effs)

    # Buff/sem dano direto: aplica efeitos e sai.
    is_offensive = bool(re.search(r"\d+d\d+", str(formula))) and str(ability.get("damage_type", "")).lower() != "buff"

    if not is_offensive:
        logs.append(f"{player.get('name','Herói')} usa {name}.")
        if has_typed:
            for eff in self_effs:
                cond = _condition_from_effect(eff, name)
                if cond:
                    logs.append(apply_condition(player, cond))
            # hostis de habilidade não-ofensiva (ex.: debuff puro) vão no alvo,
            # com save se a habilidade declarar (sucesso nega o efeito).
            if hostile_effs and target.get("status") == "ativo":
                resisted = False
                save_stat = ability.get("save_stat")
                if save_stat:
                    dc = 10 + max(pstats["attack"], 0)
                    stat = normalize_attr(save_stat)
                    save_mod = attr_mods(target.get("attributes", {})).get(stat, 0)
                    save_mod += int((target.get("racial_save_bonus") or {}).get(stat, 0))
                    save_mod += condition_modifiers(target)["save"]
                    roll = random.randint(1, 20) + save_mod
                    if roll >= dc:
                        resisted = True
                        logs.append(f"{target['name']} resiste a {name} (save {roll} vs CD {dc}).")
                if not resisted:
                    for eff in hostile_effs:
                        cond = _condition_from_effect(eff, name)
                        if cond:
                            logs.append(apply_condition(target, cond))
        else:
            for c in conditions:
                logs.append(apply_condition(player, parse_condition(c, source=name)))
        # custos ("Sofre 5 dano" / "Custa 5 HP") e recuperação de recurso
        _apply_self_costs(player, conditions, logs)
        logs += _apply_resource_recovery(player, conditions)
        return logs

    # Ataque ofensivo: d20 + atk vs AC do alvo (AC inclui condições do alvo — 4.2)
    atk_roll = random.randint(1, 20)
    total_atk = atk_roll + pstats["attack"]
    target_ac = int(target.get("defense", target.get("ac", 10))) + condition_modifiers(target)["ac"]
    crit = atk_roll == 20
    if total_atk < target_ac and not crit:
        logs.append(f"{player.get('name','Herói')} usa {name}: erra ({total_atk} vs AC {target_ac}).")
        _apply_self_costs(player, conditions, logs)  # custo pago mesmo errando
        return logs

    dmg, detail = resolve_damage_formula(formula, player)
    if crit:
        dmg *= 2

    # Fase 4.2: buffs ativos + passivas somam no dano — "+5 Dano" agora É +5.
    extra, notes = damage_bonus(player, ability)
    if extra:
        dmg = max(0, dmg + extra)
        detail = f"{detail} {' '.join(notes)}".strip()

    # Saving throw do alvo (mod real do atributo + condições) reduz dano pela metade.
    save_stat = ability.get("save_stat")
    if save_stat:
        dc = 10 + max(pstats["attack"], 0)
        stat = normalize_attr(save_stat)
        save_mod = attr_mods(target.get("attributes", {})).get(stat, 0)
        save_mod += int((target.get("racial_save_bonus") or {}).get(stat, 0))
        save_mod += condition_modifiers(target)["save"]
        save_roll = random.randint(1, 20) + save_mod
        if save_roll >= dc:
            dmg = dmg // 2
            logs.append(f"{target['name']} resiste (save {save_roll} vs CD {dc}): dano reduzido.")
        else:
            logs.append(f"{target['name']} falha no save ({save_roll} vs CD {dc}).")

    target["hp"] = max(0, int(target.get("hp", 0)) - dmg)
    hit_word = "CRÍTICO!" if crit else "acerta"
    logs.append(f"{player.get('name','Herói')} usa {name} e {hit_word} {target['name']}: {dmg} de dano (HP {target['hp']}) [{detail}]")

    # Custos no conjurador ("Custa 8 HP" da Hemorragia etc.) — pagos ao usar.
    _apply_self_costs(player, conditions, logs)

    # Lifesteal: "Cura metade do dano causado" / "drena vida" → cura o herói.
    if any(re.search(r"cura.*dano|drena.*vida|lifesteal|roubo? de vida", str(c), re.IGNORECASE)
           for c in conditions):
        got = _heal(player, dmg // 2)
        if got:
            logs.append(f"{player.get('name','Herói')} drena {got} de HP (HP {player.get('hp')})")
    # Cura fixa no conjurador ("Cura o conjurador em 5")
    for c in conditions:
        mflat = re.search(r"cura o conjurador em (\d+)$", str(c).strip(), re.IGNORECASE)
        if mflat:
            got = _heal(player, int(mflat.group(1)))
            if got:
                logs.append(f"{player.get('name','Herói')} recupera {got} de HP (HP {player.get('hp')})")

    # Buffs tipados no próprio conjurador (ex.: Coração de Forja: dano + buff)
    for eff in self_effs:
        cond = _condition_from_effect(eff, name)
        if cond:
            logs.append(apply_condition(player, cond))

    if target["hp"] <= 0:
        target["status"] = "morto"
        logs.append(f"{target['name']} cai derrotado.")
    else:
        if has_typed:
            for eff in hostile_effs:
                cond = _condition_from_effect(eff, name)
                if cond:
                    logs.append(apply_condition(target, cond))
        else:
            # legado: condições textuais no alvo vivo
            for c in conditions:
                if re.search(r"sofre\s+\d+\s*dano|custa\s+\d+|cura.*(dano|conjurador)|drena.*vida|lifesteal", c, re.IGNORECASE):
                    continue  # auto-dano / custo / lifesteal não viram condição do inimigo
                logs.append(apply_condition(target, parse_condition(c, source=name)))
        # Fase 4.2: Sombra da Corte (basic_attack_dot) — toda arma aplica veneno fraco.
        if ability_id == "ataque_basico":
            for pe in class_passives(player):
                if pe.get("trigger") == "basic_attack_dot":
                    cond = {"name": pe.get("name", "Veneno fraco"),
                            "dot": int(pe.get("dot", 1) or 1),
                            "duration": int(pe.get("duration", 2) or 2),
                            "source": "Toque da Víbora"}
                    logs.append(apply_condition(target, cond))
    return logs


# --------------------------------------------------------------------------
# Comportamento de inimigos (Fase 2.5b) — perfis determinísticos
#
# behavior = {"profile": "tatico"|"feroz"|"covarde"|"implacavel",
#             "flee_below": float 0..1, "pack_morale": bool}
# - tatico:     escolhe o melhor ataque para a situação; foge por moral
# - feroz:      maior dano sempre; FRENESI (+2 dano) com HP < 50%; nunca foge
# - covarde:    ataque mais seguro; foge cedo (HP baixo ou 1º aliado caído)
# - implacavel: rotaciona ataques; nunca foge (bosses, mortos-vivos, aberrações)
# --------------------------------------------------------------------------
PROFILES = ("tatico", "feroz", "covarde", "implacavel")
_DEFAULT_FLEE = {"tatico": 0.35, "covarde": 0.6}

# Palavras de condição reconhecidas na string de dano de um ataque de inimigo
# (ex.: "1d4+2 piercing + doença"). Viram Condition aplicada no player.
_ATTACK_CONDITIONS = {
    "veneno": 2, "doença": 2, "doenca": 2, "peste": 2, "sangramento": 2,
    "queimadura": 2, "esporos": 1, "melancolia": 0, "medo": 0,
    "enredado": 0, "atordoa": 0,
}


def get_behavior(enemy: Dict) -> Dict:
    """Behavior efetivo do inimigo, com defaults seguros (feroz = comportamento antigo)."""
    b = dict(enemy.get("behavior") or {})
    profile = str(b.get("profile", "")).lower()
    if profile not in PROFILES:
        profile = "feroz"
    b["profile"] = profile
    if "flee_below" not in b and profile in _DEFAULT_FLEE:
        b["flee_below"] = _DEFAULT_FLEE[profile]
    b.setdefault("pack_morale", False)
    return b


def _avg_damage(damage: str) -> float:
    """Dano médio esperado de uma fórmula 'NdM+K ...' (para escolha de ataque)."""
    total = 0.0
    for m in re.finditer(r"(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?", str(damage or "")):
        n, s = int(m.group(1)), int(m.group(2))
        total += n * (s + 1) / 2
        if m.group(3) == "+":
            total += int(m.group(4))
        elif m.group(3) == "-":
            total -= int(m.group(4))
    return total


def _attack_applies_condition(atk: Dict) -> bool:
    dmg = str(atk.get("damage", "")).lower()
    return any(w in dmg for w in _ATTACK_CONDITIONS)


def choose_enemy_attack(enemy: Dict, player_ac: int, rnd: int, player: Optional[Dict] = None) -> Dict:
    """Escolha determinística do ataque conforme o perfil (sem RNG)."""
    attacks = [a for a in (enemy.get("attacks") or []) if isinstance(a, dict)]
    if not attacks:
        return {"name": "Ataque", "bonus": int(enemy.get("attack_mod", 0) or 0), "damage": "1d6"}
    if len(attacks) == 1:
        return attacks[0]

    profile = get_behavior(enemy)["profile"]
    if profile == "feroz":
        return max(attacks, key=lambda a: _avg_damage(a.get("damage")))
    if profile == "implacavel":
        return attacks[(max(1, int(rnd)) - 1) % len(attacks)]
    if profile == "covarde":
        ranged = [a for a in attacks if "ranged" in str(a.get("type", "")).lower()]
        pool = ranged or attacks
        return max(pool, key=lambda a: int(a.get("bonus", 0) or 0))
    # tatico: abre com condição se o alvo ainda não tem nenhuma; senão,
    # AC alta -> maior bônus de acerto; AC baixa -> maior dano.
    if player is not None and not (player.get("active_conditions") or []):
        cond_atks = [a for a in attacks if _attack_applies_condition(a)]
        if cond_atks:
            return cond_atks[0]
    if int(player_ac) >= 15:
        return max(attacks, key=lambda a: int(a.get("bonus", 0) or 0))
    return max(attacks, key=lambda a: _avg_damage(a.get("damage")))


def check_morale(enemy: Dict, allies: Optional[List[Dict]] = None) -> Optional[str]:
    """
    Teste de moral no início do turno do inimigo. Retorna o log de fuga
    (e seta status='fugiu') ou None se ele continua lutando.

    feroz/implacavel NUNCA fogem — um urso-titã não conhece o conceito.
    """
    b = get_behavior(enemy)
    profile = b["profile"]
    if profile in ("feroz", "implacavel"):
        return None

    max_hp = max(1, int(enemy.get("max_hp", 1)))
    ratio = int(enemy.get("hp", 0)) / max_hp
    flee_below = float(b.get("flee_below", _DEFAULT_FLEE.get(profile, 0.35)))

    group = [a for a in (allies or []) if a.get("id") != enemy.get("id")]
    downed = [a for a in group if a.get("status") in ("morto", "fugiu")]

    reason = None
    if ratio < flee_below:
        reason = "ferido demais"
    elif profile == "covarde" and downed:
        reason = f"viu {downed[0].get('name', 'um aliado')} cair"
    elif profile == "tatico" and b.get("pack_morale") and group and len(downed) * 2 > len(group):
        reason = "o grupo quebrou"

    if not reason:
        return None
    # Fase 4.2: enredado não foge — quer, mas não consegue.
    if has_control(enemy, "root"):
        return f"{enemy.get('name','Inimigo')} tenta fugir ({reason}), mas está ENREDADO e não escapa."
    enemy["status"] = "fugiu"
    return f"{enemy.get('name','Inimigo')} FOGE do combate ({reason})."


def _apply_attack_conditions(atk: Dict, player: Dict) -> List[str]:
    """Condições embutidas na string de dano do ataque (ex.: '+ veneno') no player."""
    logs: List[str] = []
    dmg = str(atk.get("damage", "")).lower()
    for word, dot in _ATTACK_CONDITIONS.items():
        if word in dmg:
            cond = {"name": word.capitalize(), "dot": dot, "duration": 2,
                    "source": atk.get("name", "ataque")}
            logs.append(apply_condition(player, cond))
    return logs


def pick_target(enemy: Dict, targets: List[Dict]) -> Optional[Dict]:
    """Fase 4.5 (R4): escolha TÁTICA de alvo entre player + aliados, por perfil.

    tatico -> menor HP%; covarde -> menor defense; implacavel -> o player;
    feroz -> aleatório (sem memória de dano por round na v1)."""
    alive = [t for t in targets or []
             if int(t.get("hp", 0)) > 0 and t.get("status", "ativo") == "ativo"]
    if not alive:
        return None
    if len(alive) == 1:
        return alive[0]
    profile = get_behavior(enemy)["profile"]
    if profile == "implacavel":
        for t in alive:
            if t.get("side") == "hero" or "class_name" in t:
                return t
        return alive[0]
    if profile == "tatico":
        return min(alive, key=lambda t: int(t.get("hp", 1)) / max(1, int(t.get("max_hp", 1))))
    if profile == "covarde":
        return min(alive, key=lambda t: int(t.get("defense", 10)))
    return random.choice(alive)  # feroz


def _target_ac(target: Dict) -> int:
    """AC efetiva de um alvo do lado herói (player usa compute; aliado usa defense)."""
    if "class_name" in target:
        return compute_player_combat_stats(target)["ac"]
    return int(target.get("defense", 10)) + condition_modifiers(target)["ac"]


def resolve_ally_turn(ally: Dict, enemies: List[Dict], rnd: int = 1) -> List[str]:
    """Fase 4.5: turno de UM aliado — MESMO motor do inimigo, lado invertido.
    Perfil 2.5b decide o ataque; alvo = inimigo ativo de menor HP. Muta in-place."""
    logs: List[str] = []
    if int(ally.get("hp", 0)) <= 0 or ally.get("status", "ativo") != "ativo":
        return logs
    if has_control(ally, "stun"):
        return [f"{ally.get('name','Aliado')} está ATORDOADO e perde o turno."]
    alive = [e for e in enemies if e.get("status") == "ativo"]
    if not alive:
        return logs
    target = min(alive, key=lambda e: int(e.get("hp", 1)))
    atk = choose_enemy_attack(ally, int(target.get("defense", 10)), rnd)
    bonus = int(atk.get("bonus", 0) or 0) + condition_modifiers(ally)["attack"]
    roll = random.randint(1, 20)
    total = roll + bonus
    tgt_ac = int(target.get("defense", target.get("ac", 10))) + condition_modifiers(target)["ac"]
    crit = roll == 20
    if total < tgt_ac and not crit:
        logs.append(f"{ally['name']} ({atk.get('name','ataque')}) erra {target['name']} ({total} vs AC {tgt_ac}).")
        return logs
    dmg, detail = roll_dice_numeric(atk.get("damage", "1d6"))
    if crit:
        dmg *= 2
    dmg = max(0, dmg + condition_modifiers(ally)["damage"])
    target["hp"] = max(0, int(target.get("hp", 0)) - dmg)
    logs.append(f"{ally['name']} {'CRÍTICO!' if crit else 'acerta'} {target['name']} "
                f"com {atk.get('name','ataque')}: {dmg} de dano (HP {target['hp']}) [{detail}]")
    if target["hp"] <= 0:
        target["status"] = "morto"
        logs.append(f"{target['name']} cai derrotado.")
    return logs


def usable_enemy_abilities(enemy: Dict) -> List[Dict]:
    """Fase 4.6: habilidades MECÂNICAS do inimigo (dicts com id/custo/fórmula).
    Strings legadas (decorativas) são ignoradas. Filtra custo e cooldown."""
    out = []
    cds = enemy.get("ability_cooldowns") or {}
    for ab in enemy.get("abilities") or []:
        if not isinstance(ab, dict) or not ab.get("id"):
            continue
        if int(cds.get(ab["id"], 0) or 0) > 0:
            continue
        cost = int(ab.get("cost", 0) or 0)
        field = _resource_field(ab.get("resource_type", "")) if cost > 0 else None
        if field and int(enemy.get(field, 0)) < cost:
            continue
        out.append(ab)
    return out


def _pick_enemy_ability(enemy: Dict, target: Dict, rnd: int) -> Optional[Dict]:
    """Perfil decide QUANDO usar habilidade em vez de ataque básico (sem RNG)."""
    usable = usable_enemy_abilities(enemy)
    if not usable:
        return None
    profile = get_behavior(enemy)["profile"]
    if profile == "tatico":
        # abre com controle/efeito se o alvo ainda está limpo
        if not (target.get("active_conditions") or []):
            with_fx = [a for a in usable if a.get("effects") or a.get("conditions")]
            if with_fx:
                return with_fx[0]
        return None
    if profile == "feroz":
        best = max(usable, key=lambda a: _avg_damage(a.get("damage_formula")))
        return best if _avg_damage(best.get("damage_formula")) > 0 else None
    if profile == "covarde":
        deb = [a for a in usable
               if any(e.get("kind") in ("debuff", "control")
                      for e in (a.get("effects") or []) if isinstance(e, dict))]
        return deb[0] if deb else None
    # implacavel: rotação — habilidade nos rounds pares
    return usable[(rnd // 2) % len(usable)] if rnd % 2 == 0 else None


def _resolve_enemy_ability(enemy: Dict, ability: Dict, target: Dict,
                           is_player: bool) -> List[str]:
    """Resolve habilidade de inimigo com o MESMO vocabulário do player:
    custo/cooldown -> d20 vs AC (se tem dano) -> save reduz metade -> effects 4.2."""
    logs: List[str] = []
    name = ability.get("name", ability.get("id", "habilidade"))
    cost = int(ability.get("cost", 0) or 0)
    field = _resource_field(ability.get("resource_type", "")) if cost > 0 else None
    if field:
        enemy[field] = int(enemy.get(field, 0)) - cost
    cd = int(ability.get("cooldown", COOLDOWN_DEFAULT) or COOLDOWN_DEFAULT)
    enemy.setdefault("ability_cooldowns", {})[ability["id"]] = cd

    formula = str(ability.get("damage_formula", "0"))
    has_dmg = bool(re.search(r"\d+d\d+", formula))
    dmg = 0
    if has_dmg:
        atk_roll = random.randint(1, 20)
        bonus = int(enemy.get("attack_mod", 0) or 0) + condition_modifiers(enemy)["attack"]
        tgt_ac = _target_ac(target) if is_player else (
            int(target.get("defense", 10)) + condition_modifiers(target)["ac"])
        if atk_roll + bonus < tgt_ac and atk_roll != 20:
            logs.append(f"{enemy['name']} usa {name}: erra ({atk_roll + bonus} vs AC {tgt_ac}).")
            return logs
        dmg, detail = resolve_damage_formula(formula, enemy)
        if atk_roll == 20:
            dmg *= 2
    save_stat = ability.get("save_stat")
    resisted = False
    if save_stat:
        dc = 10 + max(int(enemy.get("attack_mod", 0) or 0), 0)
        stat = normalize_attr(save_stat)
        save_mod = attr_mods(target.get("attributes", {})).get(stat, 0)
        save_mod += int((target.get("racial_save_bonus") or {}).get(stat, 0))
        save_mod += condition_modifiers(target)["save"]
        roll = random.randint(1, 20) + save_mod
        if roll >= dc:
            resisted = True
            dmg //= 2
            logs.append(f"{target.get('name','Alvo')} resiste a {name} (save {roll} vs CD {dc}).")
    if has_dmg:
        target["hp"] = max(0, int(target.get("hp", 0)) - dmg)
        logs.append(f"{enemy['name']} usa {name} em {target.get('name','o alvo')}: "
                    f"{dmg} de dano (HP {target['hp']})")
    else:
        logs.append(f"{enemy['name']} usa {name}.")
    if int(target.get("hp", 1)) > 0 and not resisted:
        for eff in ability.get("effects") or []:
            if not isinstance(eff, dict):
                continue
            if eff.get("kind") == "buff":
                cond = _condition_from_effect(eff, name)
                if cond:
                    logs.append(apply_condition(enemy, cond))
            else:
                cond = _condition_from_effect(eff, name)
                if cond:
                    logs.append(apply_condition(target, cond))
    if int(target.get("hp", 1)) <= 0:
        if not is_player and target.get("status", "ativo") == "ativo":
            target["status"] = "morto"
            target["active"] = False
            logs.append(f"{target.get('name','O aliado')} CAI em combate.")
    return logs


def apply_boss_phase(enemy: Dict) -> Optional[str]:
    """Fase 4.6 (R5): threshold de HP% troca perfil/adiciona habilidades UMA vez.
    behavior.phases = [{below, profile?, add_abilities?[dicts], once_log?}]."""
    phases = (enemy.get("behavior") or {}).get("phases") or []
    if not phases:
        return None
    ratio = int(enemy.get("hp", 0)) / max(1, int(enemy.get("max_hp", 1)))
    cur = int(enemy.get("_phase", -1))
    for idx, ph in enumerate(phases):
        if idx > cur and ratio <= float(ph.get("below", 0) or 0):
            enemy["_phase"] = idx
            b = dict(enemy.get("behavior") or {})
            if ph.get("profile"):
                b["profile"] = ph["profile"]
            enemy["behavior"] = b
            for ab in ph.get("add_abilities") or []:
                if isinstance(ab, dict):
                    enemy.setdefault("abilities", []).append(dict(ab))
            return ph.get("once_log") or f"{enemy.get('name','O inimigo')} muda de postura!"
    return None


def resolve_enemy_turn(enemy: Dict, player: Dict,
                       allies: Optional[List[Dict]] = None, rnd: int = 1,
                       hero_side: Optional[List[Dict]] = None) -> List[str]:
    """Turno do inimigo: moral -> escolha de ataque por perfil -> d20 vs AC -> dano
    (+frenesi feroz, +condições do ataque). Muta enemy/player; retorna logs."""
    logs: List[str] = []
    if enemy.get("status") != "ativo":
        return logs

    # Fase 4.2: atordoado perde o turno (simetria com o player).
    if has_control(enemy, "stun"):
        return [f"{enemy.get('name','Inimigo')} está ATORDOADO e perde o turno."]

    # Fase 4.6: cooldowns do inimigo tickam; boss pode trocar de FASE (uma vez).
    tick_cooldowns(enemy)
    phase_log = apply_boss_phase(enemy)
    if phase_log:
        logs.append(f"⚠ {phase_log}")

    flee_log = check_morale(enemy, allies)
    if flee_log:
        return logs + [flee_log]

    # Fase 4.5 (R4): alvo tático entre player + aliados ativos (perfil decide).
    targets = [t for t in (hero_side or [player]) if t is not None]
    target = pick_target(enemy, targets) or player
    is_player = (target is player) or ("class_name" in target)

    # Fase 4.6 (R3): perfil decide se usa HABILIDADE em vez de ataque básico.
    ability = _pick_enemy_ability(enemy, target, rnd)
    if ability:
        return logs + _resolve_enemy_ability(enemy, ability, target, is_player)

    tgt_ac = _target_ac(target)
    atk = choose_enemy_attack(enemy, tgt_ac, rnd, target if is_player else None)
    bonus = int(atk.get("bonus", 0) or 0)
    # Fase 4.2: condições do inimigo modificam o acerto dele (fear = -2 embutido)
    bonus += condition_modifiers(enemy)["attack"]
    # Fase 6.5: clima é simétrico — inimigo também erra na chuva
    bonus += int(enemy.get("_env_attack_mod", 0) or 0)
    atk_roll = random.randint(1, 20)
    total = atk_roll + bonus
    crit = atk_roll == 20
    if total < tgt_ac and not crit:
        logs.append(f"{enemy['name']} ({atk.get('name','ataque')}) erra "
                    f"{target.get('name','o alvo')} ({total} vs AC {tgt_ac}).")
        return logs

    dmg, detail = roll_dice_numeric(atk.get("damage", "1d6"))
    if crit:
        dmg *= 2

    # FRENESI: feroz com HP < 50% bate mais forte — ele não recua, acelera.
    b = get_behavior(enemy)
    if b["profile"] == "feroz" and int(enemy.get("hp", 0)) * 2 < int(enemy.get("max_hp", 1)):
        dmg += 2
        detail = f"{detail} +2 frenesi"

    # Fase 4.2: buff/debuff de dano no inimigo (simetria)
    edmg = condition_modifiers(enemy)["damage"]
    if edmg:
        dmg = max(0, dmg + edmg)
        detail = f"{detail} {'+' if edmg >= 0 else ''}{edmg} condições"

    target["hp"] = max(0, int(target.get("hp", 0)) - dmg)
    hit = "CRÍTICO!" if crit else "acerta"
    logs.append(f"{enemy['name']} {hit} {target.get('name','o alvo')} com "
                f"{atk.get('name','ataque')}: {dmg} de dano (HP {target['hp']}) [{detail}]")
    if int(target.get("hp", 0)) > 0:
        logs += _apply_attack_conditions(atk, target)
        # Fase 4.2: Pastor de Pragas (melee_retaliate) — quem morde, prova o veneno.
        # (class_passives só devolve algo para o PLAYER — aliado não tem class_name.)
        atype = str(atk.get("type", "melee")).lower()
        if "melee" in atype or atype == "":
            for pe in class_passives(target):
                if pe.get("trigger") == "melee_retaliate":
                    ret, rdet = roll_dice_numeric(str(pe.get("formula", "1d4")))
                    if ret > 0:
                        enemy["hp"] = max(0, int(enemy.get("hp", 0)) - ret)
                        logs.append(f"{enemy['name']} sofre {ret} de {pe.get('name', 'retaliação')} "
                                    f"(HP {enemy['hp']}) [{rdet}]")
                        if enemy["hp"] <= 0 and enemy.get("status") == "ativo":
                            enemy["status"] = "morto"
                            logs.append(f"{enemy['name']} sucumbe à retaliação.")
    elif not is_player:
        # Fase 4.5 (R5): aliado caiu — vira baixa; o nó de combate decide evento.
        target["status"] = "morto"
        target["active"] = False
        logs.append(f"{target.get('name','O aliado')} CAI em combate.")
    return logs
