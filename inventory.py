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


def resolve_item_name(name: str) -> str | None:
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


def is_unique(item_id: str) -> bool:
    """Fase 6.2: item único — existe UM no mundo (flag em artifacts.json)."""
    return bool((ARTIFACTS_DB.get(item_id) or {}).get("unique"))


def is_stackable(item_id: str) -> bool:
    item = ARTIFACTS_DB.get(item_id) or {}
    if "stackable" in item:
        return bool(item["stackable"])
    return str(item.get("type", "")).lower() in _STACKABLE_TYPES


def item_display(entry: dict) -> str:
    """Nome exibível SEMPRE do ARTIFACTS_DB (nunca title() sobre id — bug 4.3)."""
    iid = entry.get("id", "")
    if iid == UNKNOWN_ID:
        return entry.get("display_name") or "Item desconhecido"
    item = ARTIFACTS_DB.get(iid)
    return item.get("name", iid) if item else (entry.get("display_name") or iid)


def make_entry(id_or_name: str, qty: int = 1) -> dict:
    iid = resolve_item_name(id_or_name)
    if iid:
        return {"id": iid, "qty": max(1, int(qty))}
    return {"id": UNKNOWN_ID, "qty": max(1, int(qty)),
            "display_name": str(id_or_name)}


def add_item(inv: list[dict], id_or_name: str, qty: int = 1) -> list[dict]:
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


def remove_item(inv: list[dict], item_id: str, qty: int = 1, *,
                display_name: str | None = None) -> tuple[list[dict], bool]:
    """Consome `qty` ATRAVÉS de todas as entradas do mesmo item (não-empilháveis
    vivem em entradas separadas). Soma insuficiente -> (inv original, False), sem
    mutar nada. `display_name` desambigua itens livres (`item_desconhecido`)."""
    qty = max(1, int(qty or 1))
    matches = [
        i for i, e in enumerate(inv or [])
        if (e.get("id") == item_id or item_display(e) == item_id)
        and (display_name is None or e.get("display_name") == display_name)
    ]
    if sum(int(inv[i].get("qty", 1)) for i in matches) < qty:
        return inv, False
    # entradas sem display_name primeiro, depois ordem da lista
    matches.sort(key=lambda i: (bool(inv[i].get("display_name")), i))
    out = [dict(e) for e in inv]
    left = qty
    drop = set()
    for i in matches:
        if left <= 0:
            break
        have = int(out[i].get("qty", 1))
        take = min(have, left)
        left -= take
        if take == have:
            drop.add(i)
        else:
            out[i]["qty"] = have - take
    return [e for i, e in enumerate(out) if i not in drop], True


def get_qty(inv: list[dict], item_id: str) -> int:
    return sum(int(e.get("qty", 1)) for e in inv or [] if e.get("id") == item_id)


def has_item(inv: list[dict], item_id: str) -> bool:
    return get_qty(inv, item_id) > 0


def find_in_inventory(inv: list[dict], ref: str) -> str | None:
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


def find_entry_in_inventory(inv: list[dict], ref: str) -> dict | None:
    """Como `find_in_inventory`, mas devolve a ENTRADA ({id, qty, display_name?}) —
    itens livres precisam do display_name para não confundir `item_desconhecido`."""
    if not ref:
        return None
    rid = resolve_item_name(ref)
    if rid:
        for e in inv or []:
            if e.get("id") == rid:
                return dict(e)
    folded = _fold(ref)
    for e in inv or []:
        if folded and folded in _fold(item_display(e)):
            return dict(e)
    return None


def resolve_flavor_item(name: str) -> dict:
    """Entrada SEGURA para nome livre vindo do LLM (sabor de criação/narração):
    só itens comuns resolvem; raro+ ou único vira `item_desconhecido` (sem claim,
    sem bônus). Usa a mesma escala de raridade da economia."""
    iid = resolve_item_name(name)
    if iid:
        item = ARTIFACTS_DB.get(iid) or {}
        rarity = str(item.get("rarity", "comum")).lower()
        if not is_unique(iid) and rarity in _COMMON_RARITIES:
            return {"id": iid, "qty": 1}
    return {"id": UNKNOWN_ID, "qty": 1, "display_name": str(name)}


_COMMON_RARITIES = {"comum", "common"}


# ---------------------------------------------------------------------------
# Equipamento (slots)
# ---------------------------------------------------------------------------
def ensure_equipment(player: dict) -> dict:
    eq = dict(player.get("equipment") or {})
    for s in SLOTS:
        eq.setdefault(s, None)
    return eq


def slot_for(item_id: str) -> str | None:
    itype = str((ARTIFACTS_DB.get(item_id) or {}).get("type", "")).lower()
    for slot, types in _SLOT_TYPES.items():
        if itype in types:
            return slot
    return None


def equip(player: dict, item_id: str) -> tuple[dict, str | None]:
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


def unequip(player: dict, slot: str) -> tuple[dict, str | None]:
    if slot not in SLOTS:
        return player, f"Slot inválido: {slot}"
    p = dict(player)
    eq = ensure_equipment(p)
    eq[slot] = None
    p["equipment"] = eq
    return p, None


def equipped_items(player: dict) -> list[str]:
    """Ids dos slots preenchidos COM posse no inventário (slot órfão não conta)."""
    inv_ = player.get("inventory") or []
    return [v for v in (player.get("equipment") or {}).values()
            if v and has_item(inv_, v)]


def reconcile_equipment(player: dict) -> tuple[dict, list[str]]:
    """Esvazia slots cujo item não está mais no inventário. Pura (cópia)."""
    p = dict(player)
    eq = dict(p.get("equipment") or {})
    removed = [slot for slot, v in eq.items()
               if v and not has_item(p.get("inventory") or [], v)]
    for slot in removed:
        eq[slot] = None
    if "equipment" in p or removed:
        p["equipment"] = eq
    return p, removed


# ---------------------------------------------------------------------------
# Uso em combate (Fase 4.3 R4) — resolução 100% Python
# ---------------------------------------------------------------------------
def use_item_in_combat(player: dict, item_ref: str,
                       target: dict | None = None) -> tuple[dict, list[str]]:
    """Wrapper de compatibilidade de `try_use_item` -> (player, logs)."""
    res = try_use_item(player, item_ref, target)
    return res["player"], res["logs"]


def _vitality_full(p: dict) -> bool:
    if p.get("vitalidade") is not None or isinstance(p.get("virtudes"), dict):
        import gamedata
        q = dict(p)
        gamedata.sync_vitality(q)
        return int(q.get("vitalidade", 0) or 0) >= int(q.get("max_vitalidade", 0) or 0)
    return int(p.get("hp", 0) or 0) >= int(p.get("max_hp", p.get("hp", 0)) or 0)


def try_use_item(player: dict, item_ref: str, target: dict | None = None,
                 rng=None) -> dict:
    """SPEC-227 R8: valida ANTES de consumir. Retorna
    {ok, reason, consumed_turn, logs, player}; recusa deixa player/inventário
    intactos e `consumed_turn=False`. Consome 1 unidade e aplica o efeito mecânico.

    Efeitos suportados: `mechanics.heal` ("2d4+2"), `mechanics.effects` (lista
    tipada 4.2 — buffs no PRÓPRIO usuário; spec itens-vivos-e-luz R5: debuff/dot/
    control vão no `target` inimigo, com save se `mechanics.save_stat`/`save_dc`)
    e o legado `active_ability.effect` com "Recupera XdY+Z HP". Item fora do
    inventário/efeito nenhum -> log de falha, turno NÃO consumido pelo chamador."""
    import combat_mechanics as cm

    def _refuse(msg: str) -> dict:
        return {"ok": False, "reason": msg, "consumed_turn": False,
                "logs": [msg], "player": player}

    inv = player.get("inventory") or []
    iid = find_in_inventory(inv, item_ref)
    if not iid or iid == UNKNOWN_ID:
        return _refuse(f"Não há '{item_ref}' utilizável no inventário.")
    item = ARTIFACTS_DB.get(iid) or {}
    if str(item.get("type", "")).lower() not in ("consumable", "potion"):
        return _refuse(f"{item.get('name', iid)} não é consumível.")

    mech = item.get("mechanics") or {}
    heal_formula = mech.get("heal")
    if not heal_formula:
        legacy = ((mech.get("active_ability") or {}).get("effect")) or ""
        m = re.search(r"recupera\s+(\d+d\d+(?:\s*\+\s*\d+)?)\s*hp", str(legacy), re.IGNORECASE)
        if m:
            heal_formula = m.group(1)
    effects = [e for e in (mech.get("effects") or []) if isinstance(e, dict)]

    if not heal_formula and not effects:
        return _refuse(f"{item.get('name', iid)} não tem efeito utilizável em combate.")

    hostile = [e for e in effects if e.get("kind") in ("debuff", "dot", "control")]
    no_target = not target or target.get("status", "ativo") != "ativo"
    if no_target and hostile and not heal_formula and len(hostile) == len(effects):
        return _refuse(f"{item.get('name', iid)}: sem alvo válido para o efeito.")
    if heal_formula and not effects and _vitality_full(player):
        return _refuse("Vitalidade já está cheia.")

    p = dict(player)
    logs: list[str] = []
    new_inv, ok = remove_item(inv, iid, 1)
    if not ok:
        return _refuse(f"Não há '{item_ref}' no inventário.")
    p["inventory"] = new_inv

    if heal_formula:
        amount, detail = cm.roll_dice_numeric(str(heal_formula))
        if p.get("vitalidade") is not None or isinstance(p.get("virtudes"), dict):
            import gamedata
            gamedata.sync_vitality(p)
            cur = int(p.get("vitalidade", 0) or 0)
            ceiling = int(p.get("max_vitalidade", cur + amount) or cur + amount)
            p["vitalidade"] = min(ceiling, cur + amount)
            gamedata.sync_legacy_hp_aliases(p)
            logs.append(f"{p.get('name','Herói')} usa {item.get('name', iid)}: "
                        f"recupera {p['vitalidade'] - cur} de Vitalidade "
                        f"(Vitalidade {p['vitalidade']}) [{detail}]")
        else:
            cur = int(p.get("hp", 0))
            ceiling = int(p.get("max_hp", cur + amount))
            p["hp"] = min(ceiling, cur + amount)
            logs.append(f"{p.get('name','Herói')} usa {item.get('name', iid)}: "
                        f"recupera {p['hp'] - cur} de HP (HP {p['hp']}) [{detail}]")
    name = item.get("name", iid)
    for eff in effects:
        kind = eff.get("kind")
        if kind == "buff":
            cond = cm._condition_from_effect(eff, name)
            if cond:
                logs.append(cm.apply_condition(p, cond))
        elif kind in ("debuff", "dot", "control"):
            # spec itens-vivos-e-luz (R5): efeito HOSTIL vai no inimigo (com save).
            if not target or target.get("status", "ativo") != "ativo":
                logs.append(f"{name}: sem alvo válido para o efeito.")
                continue
            cond = cm._condition_from_effect(eff, name)
            if not cond:
                continue
            save_stat = mech.get("save_stat")
            if save_stat:
                dc = int(mech.get("save_dc", 12) or 12)
                stat = cm.normalize_attr(save_stat)
                save_mod = cm.attr_mods(target.get("attributes", {})).get(stat, 0)
                save_mod += int((target.get("racial_save_bonus") or {}).get(stat, 0) or 0)
                save_mod += cm.condition_modifiers(target)["save"]
                roll = cm.random.randint(1, 20) + save_mod
                if roll >= dc:
                    logs.append(f"{target.get('name','Alvo')} resiste a {name} "
                                f"(save {roll} vs CD {dc}).")
                    continue
            logs.append(cm.apply_condition(target, cond))
    return {"ok": True, "reason": "", "consumed_turn": True, "logs": logs, "player": p}


# ---------------------------------------------------------------------------
# Backfill de saves antigos (R7)
# ---------------------------------------------------------------------------
def backfill_inventory(player: dict) -> dict:
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
