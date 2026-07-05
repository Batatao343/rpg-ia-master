"""
party.py — Aliados em combate (Fase 4.5). Python puro, sem IA.

Companion = ficha estilo bestiário resolvida pelo MESMO motor dos inimigos
(perfis 2.5b via resolve_ally_turn). O LLM nunca decide se um NPC aceita
juntar-se: gate determinístico (relationship + teto + fação hostil).
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from gamedata import load_json_data
from services import graph_resolver as gr

COMPANION_TEMPLATES: Dict[str, dict] = load_json_data("companions.json") or {}

RECRUIT_MIN_REL = 7   # relationship 0..10 (escala da Fase 2)
MAX_ACTIVE = 3

_ARCHETYPE_WORDS = {
    "guerreiro": ("guerreir", "soldado", "guarda", "legion", "mercenari", "lutador",
                  "veteran", "capit"),
    "arqueiro": ("arqueir", "caçador", "cacador", "batedor", "rastreador", "sentinela"),
    "curandeiro": ("curandeir", "médic", "medic", "alquimist", "botic", "enfermeir"),
    "mago": ("mag", "arcanist", "feiticeir", "brux", "erudit", "sábi", "sabi"),
}


def _fold(s: str) -> str:
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def _archetype_for(npc: Dict) -> str:
    blob = _fold(" ".join(str(npc.get(k, "")) for k in ("role", "persona", "appearance")))
    for arch, words in _ARCHETYPE_WORDS.items():
        if any(w in blob for w in words):
            return arch
    return "capanga"


def make_companion_from_npc(npc: Dict, name: str) -> Dict:
    """Ficha de combate determinística a partir do NPC + template de arquétipo."""
    arch = _archetype_for(npc or {})
    tpl = dict(COMPANION_TEMPLATES.get(arch) or COMPANION_TEMPLATES.get("capanga") or {})
    cstats = (npc or {}).get("combat_stats") or {}
    hp = int(cstats.get("hp") or tpl.get("hp", 14))
    comp = {
        "id": (npc or {}).get("id") or f"comp_{_fold(name).replace(' ', '_')}",
        "name": name,
        "archetype": arch,
        "hp": hp, "max_hp": hp,
        "defense": int(cstats.get("ac") or tpl.get("defense", 12)),
        "attributes": dict((npc or {}).get("attributes")
                           or tpl.get("attributes")
                           or {"str": 10, "dex": 10, "con": 10}),
        "attacks": list(cstats.get("attacks") or tpl.get("attacks") or []),
        "behavior": dict(tpl.get("behavior") or {"profile": "tatico"}),
        "active": True,
        "active_conditions": [],
        "status": "ativo",
        "origin_npc": (npc or {}).get("id") or "",
        "waiting_at": "",
        "stats": {},  # compat com o CompanionState mínimo antigo
    }
    if not comp["attacks"]:
        comp["attacks"] = [{"name": "Golpe", "type": "melee", "bonus": 2, "damage": "1d6"}]
    return comp


def active_allies(state: Dict) -> List[Dict]:
    return [c for c in (state.get("party") or [])
            if c.get("active") and c.get("status", "ativo") == "ativo"
            and int(c.get("hp", 0)) > 0]


def can_recruit(state: Dict, npc_name: str) -> Tuple[bool, str]:
    """Gate DETERMINÍSTICO (o LLM só narra o sim/não):
    relationship >= 7 ∧ party ativa < 3 ∧ NPC não é de fação hostil ao jogador."""
    npc = (state.get("npcs") or {}).get(npc_name) or {}
    rel = int(npc.get("relationship", 5) or 5)
    if rel < RECRUIT_MIN_REL:
        return False, f"{npc_name} não confia o bastante em você (relação {rel}/10)."
    if len(active_allies(state)) >= MAX_ACTIVE:
        return False, f"Seu grupo já está cheio ({MAX_ACTIVE} companheiros)."
    if any(c.get("name") == npc_name for c in state.get("party") or []):
        return False, f"{npc_name} já anda com você."
    fac_id = npc.get("faction") or ""
    if fac_id:
        for f in state.get("factions") or []:
            if f.get("id") == fac_id and f.get("disposition") == "hostil":
                return False, f"{npc_name} serve a um poder hostil a você."
    return True, ""


def recruit(state: Dict, npc_name: str) -> Tuple[Optional[List[Dict]], str]:
    """(nova party, motivo). None = recusado (motivo explica)."""
    ok, reason = can_recruit(state, npc_name)
    if not ok:
        return None, reason
    npc = (state.get("npcs") or {}).get(npc_name) or {}
    comp = make_companion_from_npc(npc, npc_name)
    return list(state.get("party") or []) + [comp], ""


def dismiss(state: Dict, name: str) -> Tuple[List[Dict], bool]:
    """Remove da party (relationship do NPC fica preservado em state['npcs'])."""
    party = list(state.get("party") or [])
    new = [c for c in party if _fold(c.get("name", "")) != _fold(name)]
    return new, len(new) != len(party)


def set_waiting(state: Dict, name: str, location: str = "") -> Tuple[List[Dict], bool]:
    party = [dict(c) for c in state.get("party") or []]
    found = False
    for c in party:
        if _fold(c.get("name", "")) == _fold(name):
            c["active"] = False
            c["waiting_at"] = location
            found = True
    return party, found


def set_following(state: Dict, name: str) -> Tuple[List[Dict], bool]:
    party = [dict(c) for c in state.get("party") or []]
    found = False
    for c in party:
        if _fold(c.get("name", "")) == _fold(name):
            c["active"] = True
            c["waiting_at"] = ""
            found = True
    return party, found


PARTY_COMMANDS = (
    (re.compile(r"\b(junte-se|junta(-se)?\s+a\s+mim|venha comigo|vem comigo|recruto|se junte)\b", re.I), "recruit"),
    (re.compile(r"\b(dispenso|pode ir embora|est[áa] dispensad)", re.I), "dismiss"),
    (re.compile(r"\b(espere aqui|aguarde aqui|fique aqui)\b", re.I), "wait"),
    (re.compile(r"\b(siga-me|me siga|vamos, )\b", re.I), "follow"),
)


def detect_party_command(text: str) -> Optional[str]:
    for rx, cmd in PARTY_COMMANDS:
        if rx.search(text or ""):
            return cmd
    return None


def backfill_party(party: List) -> List[Dict]:
    """Save antigo (CompanionState mínimo) ganha os campos de combate da 4.5."""
    out = []
    for c in party or []:
        if not isinstance(c, dict):
            continue
        c = dict(c)
        c.setdefault("id", f"comp_{_fold(c.get('name', 'x')).replace(' ', '_')}")
        c.setdefault("archetype", "capanga")
        c.setdefault("defense", 12)
        c.setdefault("attributes", {"str": 10, "dex": 10, "con": 10})
        c.setdefault("attacks", [{"name": "Golpe", "type": "melee", "bonus": 2, "damage": "1d6"}])
        c.setdefault("behavior", {"profile": "tatico"})
        c.setdefault("active", True)
        c.setdefault("active_conditions", [])
        c.setdefault("status", "ativo" if int(c.get("hp", 1)) > 0 else "morto")
        c.setdefault("origin_npc", "")
        c.setdefault("waiting_at", "")
        out.append(c)
    return out
