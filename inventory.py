"""
inventory.py
Inventário estruturado + slots de equipamento — Python puro, sem IA (Fase 4.3).

Inventário: List[{"id": str, "qty": int, "display_name"?: str}]. Ids resolvem no
ARTIFACTS_DB; item não-resolvível vira `item_desconhecido` preservando o nome em
display_name (save antigo não perde nada — nomes livres nunca deram stats mesmo).

Equipamento: player["equipment"] = {"weapon": id|None, "armor": id|None,
"accessory": id|None}. O motor de combate lê SÓ os slots (fim do auto-scan).

Convenção: funções retornam cópias (inventário novo), nunca mutam o recebido.
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from gamedata import ARTIFACTS_DB

UNKNOWN_ID = "item_desconhecido"
SLOTS = ("weapon", "armor", "accessory")

# tipos de item que empilham (consumíveis/materiais/moeda); equipamento não
_STACKABLE_TYPES = {"consumable", "potion", "material", "currency"}
# tipos aceitos por slot
_SLOT_TYPES = {
    "weapon": {"weapon"},
    "armor": {"armor", "shield"},
    "accessory": {"accessory", "ring", "amulet", "trinket"},
}


def _fold(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def resolve_item_name(name: str) -> Optional[str]:
    """Nome livre -> id canônico (id direto, ou match de nome case/acento-insensitive)."""
    if not name:
        return None
    if name in ARTIFACTS_DB:
        return name
    folded = _fold(name)
    for iid, item in ARTIFACTS_DB.items():
        if _fold(item.get("name", "")) == folded or _fold(iid) == folded:
            return iid
    return None


def is_stackable(item_id: str) -> bool:
    item = ARTIFACTS_DB.get(item_id) or {}
    if "stackable" in item:
        return bool(item["stackable"])
    return str(item.get("type", "")).lower() in _STACKABLE_TYPES


def item_display(entry: Dict) -> str:
    """Nome exibível SEMPRE do ARTIFACTS_DB (nunca title() sobre id — bug 4.3)."""
    iid = entry.get("id", "")
    if iid == UNKNOWN_ID:
        return entry.get("display_name") or "Item desconhecido"
    item = ARTIFACTS_DB.get(iid)
    return item.get("name", iid) if item else (entry.get("display_name") or iid)


def make_entry(id_or_name: str, qty: int = 1) -> Dict:
    iid = resolve_item_name(id_or_name)
    if iid:
        return {"id": iid, "qty": max(1, int(qty))}
    return {"id": UNKNOWN_ID, "qty": max(1, int(qty)),
            "display_name": str(id_or_name)}


def add_item(inv: List[Dict], id_or_name: str, qty: int = 1) -> List[Dict]:
    """Adiciona empilhando quando stackable (desconhecidos empilham por display_name)."""
    out = [dict(e) for e in inv or []]
    entry = make_entry(id_or_name, qty)
    for e in out:
        same = (e.get("id") == entry["id"]
                and e.get("display_name") == entry.get("display_name"))
        if same and (is_stackable(entry["id"]) or entry["id"] == UNKNOWN_ID):
            e["qty"] = int(e.get("qty", 1)) + entry["qty"]
            return out
    out.append(entry)
    return out


def remove_item(inv: List[Dict], item_id: str, qty: int = 1) -> Tuple[List[Dict], bool]:
    """Decrementa/remove. False se não tinha quantidade suficiente (inv intocado)."""
    out = [dict(e) for e in inv or []]
    for i, e in enumerate(out):
        if e.get("id") == item_id or item_display(e) == item_id:
            have = int(e.get("qty", 1))
            if have < qty:
                return inv, False
            if have == qty:
                out.pop(i)
            else:
                e["qty"] = have - qty
            return out, True
    return inv, False


def get_qty(inv: List[Dict], item_id: str) -> int:
    return sum(int(e.get("qty", 1)) for e in inv or [] if e.get("id") == item_id)


def has_item(inv: List[Dict], item_id: str) -> bool:
    return get_qty(inv, item_id) > 0


def find_in_inventory(inv: List[Dict], ref: str) -> Optional[str]:
    """Referência livre ('poção', id, nome) -> id de um item PRESENTE no inventário."""
    if not ref:
        return None
    rid = resolve_item_name(ref)
    if rid and has_item(inv, rid):
        return rid
    folded = _fold(ref)
    for e in inv or []:
        if folded and folded in _fold(item_display(e)):
            return e.get("id")
    return None


# ---------------------------------------------------------------------------
# Equipamento (slots)
# ---------------------------------------------------------------------------
def ensure_equipment(player: Dict) -> Dict:
    eq = dict(player.get("equipment") or {})
    for s in SLOTS:
        eq.setdefault(s, None)
    return eq


def slot_for(item_id: str) -> Optional[str]:
    itype = str((ARTIFACTS_DB.get(item_id) or {}).get("type", "")).lower()
    for slot, types in _SLOT_TYPES.items():
        if itype in types:
            return slot
    return None


def equip(player: Dict, item_id: str) -> Tuple[Dict, Optional[str]]:
    """Equipa item DO INVENTÁRIO no slot do tipo dele. Erro -> player intocado."""
    iid = resolve_item_name(item_id) or item_id
    if not has_item(player.get("inventory") or [], iid):
        return player, f"'{item_id}' não está no inventário."
    slot = slot_for(iid)
    if not slot:
        return player, f"'{item_display(make_entry(iid))}' não é equipável."
    p = dict(player)
    eq = ensure_equipment(p)
    eq[slot] = iid
    p["equipment"] = eq
    return p, None


def unequip(player: Dict, slot: str) -> Tuple[Dict, Optional[str]]:
    if slot not in SLOTS:
        return player, f"Slot inválido: {slot}"
    p = dict(player)
    eq = ensure_equipment(p)
    eq[slot] = None
    p["equipment"] = eq
    return p, None


# ---------------------------------------------------------------------------
# Uso em combate (Fase 4.3 R4) — resolução 100% Python
# ---------------------------------------------------------------------------
def use_item_in_combat(player: Dict, item_ref: str) -> Tuple[Dict, List[str]]:
    """Consome 1 unidade e aplica o efeito mecânico. Retorna (player, logs).

    Efeitos suportados: `mechanics.heal` ("2d4+2"), `mechanics.effects` (lista
    tipada 4.2 — buffs no próprio usuário) e o legado `active_ability.effect`
    com "Recupera XdY+Z HP". Item fora do inventário/efeito nenhum -> log de
    falha, turno NÃO consumido pelo chamador (ok=False implícito no log)."""
    import combat_mechanics as cm

    inv = player.get("inventory") or []
    iid = find_in_inventory(inv, item_ref)
    if not iid or iid == UNKNOWN_ID:
        return player, [f"Não há '{item_ref}' utilizável no inventário."]
    item = ARTIFACTS_DB.get(iid) or {}
    if str(item.get("type", "")).lower() not in ("consumable", "potion"):
        return player, [f"{item.get('name', iid)} não é consumível."]

    mech = item.get("mechanics") or {}
    heal_formula = mech.get("heal")
    if not heal_formula:
        legacy = ((mech.get("active_ability") or {}).get("effect")) or ""
        m = re.search(r"recupera\s+(\d+d\d+(?:\s*\+\s*\d+)?)\s*hp", str(legacy), re.IGNORECASE)
        if m:
            heal_formula = m.group(1)
    effects = [e for e in (mech.get("effects") or []) if isinstance(e, dict)]

    if not heal_formula and not effects:
        return player, [f"{item.get('name', iid)} não tem efeito utilizável em combate."]

    p = dict(player)
    logs: List[str] = []
    new_inv, ok = remove_item(inv, iid, 1)
    if not ok:
        return player, [f"Não há '{item_ref}' no inventário."]
    p["inventory"] = new_inv

    if heal_formula:
        amount, detail = cm.roll_dice_numeric(str(heal_formula))
        cur = int(p.get("hp", 0))
        ceiling = int(p.get("max_hp", cur + amount))
        p["hp"] = min(ceiling, cur + amount)
        logs.append(f"{p.get('name','Herói')} usa {item.get('name', iid)}: "
                    f"recupera {p['hp'] - cur} de HP (HP {p['hp']}) [{detail}]")
    for eff in effects:
        if eff.get("kind") == "buff":
            cond = cm._condition_from_effect(eff, item.get("name", iid))
            if cond:
                logs.append(cm.apply_condition(p, cond))
    return p, logs


# ---------------------------------------------------------------------------
# Backfill de saves antigos (R7)
# ---------------------------------------------------------------------------
def backfill_inventory(player: Dict) -> Dict:
    """List[str] -> List[{id, qty}] + equipment default (melhor arma/armadura,
    reproduzindo o auto-equip antigo UMA vez). Idempotente."""
    p = dict(player)
    inv = p.get("inventory") or []
    if inv and all(isinstance(e, dict) for e in inv):
        structured = [dict(e) for e in inv]
    else:
        structured = []
        for e in inv:
            if isinstance(e, dict):
                structured.append(dict(e))
            else:
                structured = add_item(structured, str(e), 1)
    p["inventory"] = structured

    if not p.get("equipment"):
        eq = {s: None for s in SLOTS}
        best = {"weapon": -1, "armor": -1}
        for e in structured:
            item = ARTIFACTS_DB.get(e.get("id", "")) or {}
            stats = item.get("combat_stats") or {}
            slot = slot_for(e.get("id", ""))
            if slot == "weapon" and int(stats.get("attack_bonus", 0) or 0) > best["weapon"]:
                best["weapon"] = int(stats.get("attack_bonus", 0) or 0)
                eq["weapon"] = e["id"]
            elif slot == "armor" and int(stats.get("ac_bonus", 0) or 0) > best["armor"]:
                best["armor"] = int(stats.get("ac_bonus", 0) or 0)
                eq["armor"] = e["id"]
            elif slot == "accessory" and eq["accessory"] is None:
                eq["accessory"] = e["id"]
        p["equipment"] = eq
    return p
