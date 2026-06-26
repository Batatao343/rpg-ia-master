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

from gamedata import ARTIFACTS_DB

COOLDOWN_DEFAULT = 2  # turnos de recarga para habilidades com custo

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
    return {"name": name, "dot": dot, "duration": duration, "source": source}


def apply_condition(entity: Dict, cond: Dict) -> str:
    """Anexa/atualiza uma condição no alvo. Refresca duração se já existir."""
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
def roll_initiative(player: Dict, enemies: List[Dict]) -> List[Dict]:
    """d20 + mod de destreza por combatente. Ordena desc. Lados: hero/enemy."""
    order: List[Dict] = []
    p_dex = attr_mods(player.get("attributes", {}))["dex"]
    order.append({"id": "player", "name": player.get("name", "Herói"),
                  "side": "hero", "init": random.randint(1, 20) + p_dex})
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
    """AC, bônus de ataque e atributo de ataque, considerando itens do ARTIFACTS_DB."""
    mods = attr_mods(player.get("attributes", {}))
    best_atk_bonus = 0
    ac_bonus = 0
    attack_attr = "str"
    for item_id in player.get("inventory", []) or []:
        item = ARTIFACTS_DB.get(item_id)
        if not item:
            continue
        stats = item.get("combat_stats", {})
        if item.get("type") == "weapon":
            b = stats.get("attack_bonus", 0)
            if b > best_atk_bonus:
                best_atk_bonus = b
                if "attribute" in stats:
                    attack_attr = normalize_attr(stats["attribute"])
        ac_bonus += stats.get("ac_bonus", 0)
    return {
        "ac": 10 + mods["dex"] + ac_bonus,
        "attack": mods.get(attack_attr, 0) + best_atk_bonus + int(player.get("attack_bonus", 0) or 0),
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
        done = _heal(player, heal)
        logs.append(f"{player.get('name','Herói')} usa {name}: recupera {done} de HP (HP {player.get('hp')}) [{detail}]")
        logs += _apply_resource_recovery(player, conditions)
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

    # Buff/sem dano direto: aplica condições no próprio player e sai.
    is_offensive = bool(re.search(r"\d+d\d+", str(formula))) and str(ability.get("damage_type", "")).lower() != "buff"

    if not is_offensive:
        logs.append(f"{player.get('name','Herói')} usa {name}.")
        for c in conditions:
            logs.append(apply_condition(player, parse_condition(c, source=name)))
        # efeito de auto-dano ("Sofre 5 dano")
        for c in conditions:
            m = re.search(r"sofre\s+(\d+)\s*dano", c, re.IGNORECASE)
            if m:
                player["hp"] = max(0, int(player.get("hp", 0)) - int(m.group(1)))
                logs.append(f"{player.get('name','Herói')} sofre {m.group(1)} de dano (HP {player['hp']})")
        # recuperação de recurso ("Recupera 10 Estamina")
        logs += _apply_resource_recovery(player, conditions)
        return logs

    # Ataque ofensivo: d20 + atk vs AC do alvo
    atk_roll = random.randint(1, 20)
    total_atk = atk_roll + pstats["attack"]
    target_ac = int(target.get("defense", target.get("ac", 10)))
    crit = atk_roll == 20
    if total_atk < target_ac and not crit:
        logs.append(f"{player.get('name','Herói')} usa {name}: erra ({total_atk} vs AC {target_ac}).")
        return logs

    dmg, detail = resolve_damage_formula(formula, player)
    if crit:
        dmg *= 2

    # Saving throw do alvo (mod real do atributo) reduz dano pela metade.
    save_stat = ability.get("save_stat")
    if save_stat:
        dc = 10 + max(pstats["attack"], 0)
        save_mod = attr_mods(target.get("attributes", {})).get(normalize_attr(save_stat), 0)
        save_roll = random.randint(1, 20) + save_mod
        if save_roll >= dc:
            dmg = dmg // 2
            logs.append(f"{target['name']} resiste (save {save_roll} vs CD {dc}): dano reduzido.")
        else:
            logs.append(f"{target['name']} falha no save ({save_roll} vs CD {dc}).")

    target["hp"] = max(0, int(target.get("hp", 0)) - dmg)
    hit_word = "CRÍTICO!" if crit else "acerta"
    logs.append(f"{player.get('name','Herói')} usa {name} e {hit_word} {target['name']}: {dmg} de dano (HP {target['hp']}) [{detail}]")

    # Lifesteal: condição "Cura metade do dano causado" / "drena vida" → cura o herói.
    if any(re.search(r"cura.*dano|drena.*vida|lifesteal|roubo? de vida", str(c), re.IGNORECASE)
           for c in conditions):
        got = _heal(player, dmg // 2)
        if got:
            logs.append(f"{player.get('name','Herói')} drena {got} de HP (HP {player.get('hp')})")

    if target["hp"] <= 0:
        target["status"] = "morto"
        logs.append(f"{target['name']} cai derrotado.")
    else:
        # condições só em alvo vivo (e que não resistiu totalmente já tratado acima)
        for c in conditions:
            if re.search(r"sofre\s+\d+\s*dano|cura.*dano|drena.*vida|lifesteal", c, re.IGNORECASE):
                continue  # auto-dano / lifesteal não viram condição do inimigo
            logs.append(apply_condition(target, parse_condition(c, source=name)))
    return logs


def resolve_enemy_turn(enemy: Dict, player: Dict) -> List[str]:
    """IA simples: 1º ataque do inimigo vs AC do player; aplica dano."""
    logs: List[str] = []
    if enemy.get("status") != "ativo":
        return logs

    pstats = compute_player_combat_stats(player)
    attacks = enemy.get("attacks") or []
    atk = attacks[0] if attacks and isinstance(attacks[0], dict) else {
        "name": "Ataque", "bonus": int(enemy.get("attack_mod", 0) or 0), "damage": "1d6",
    }
    bonus = int(atk.get("bonus", 0) or 0)
    atk_roll = random.randint(1, 20)
    total = atk_roll + bonus
    crit = atk_roll == 20
    if total < pstats["ac"] and not crit:
        logs.append(f"{enemy['name']} ({atk.get('name','ataque')}) erra ({total} vs AC {pstats['ac']}).")
        return logs

    dmg, detail = roll_dice_numeric(atk.get("damage", "1d6"))
    if crit:
        dmg *= 2
    player["hp"] = max(0, int(player.get("hp", 0)) - dmg)
    hit = "CRÍTICO!" if crit else "acerta"
    logs.append(f"{enemy['name']} {hit} com {atk.get('name','ataque')}: {dmg} de dano (HP {player['hp']}) [{detail}]")
    return logs
