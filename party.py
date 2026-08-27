"""
party.py — Aliados em combate (Fase 4.5). Python puro, sem IA.

Companion = ficha estilo bestiário resolvida pelo MESMO motor dos inimigos
(perfis 2.5b via resolve_ally_turn). O LLM nunca decide se um NPC aceita
juntar-se: gate determinístico (relationship + teto + fação hostil).
"""
from copy import deepcopy
import re
import unicodedata
from typing import Dict, List, Literal, Optional, Tuple, TypedDict

from gamedata import load_json_data
from services import graph_resolver as gr

COMPANION_TEMPLATES: Dict[str, dict] = load_json_data("companions.json") or {}

RECRUIT_MIN_REL = 7   # relationship 0..10 (escala da Fase 2)
MAX_ACTIVE = 3


class RecruitmentDecision(TypedDict):
    ok: bool
    code: Literal["ok", "relationship_too_low", "party_full", "already_member", "hostile"]
    relationship: int
    required_relationship: int
    public_hint: str

# spec aliados-em-combate: um NPC amigo EM CENA luta ao seu lado neste combate
# SEM precisar do compromisso de recrutamento (rel>=7). Limiar acima do neutro
# (default 5) p/ um estranho qualquer não virar combatente — só quem você já
# cativou um pouco (rel>=6). Teto p/ o combate não trivializar com muitos amigos.
SCENE_ALLY_MIN_REL = 6
MAX_SCENE_ALLIES = 2

_ARCHETYPE_WORDS = {
    "guerreiro": ("guerreir", "soldado", "guarda", "legion", "mercenari", "lutador",
                  "veteran", "capit"),
    "arqueiro": ("arqueir", "caçador", "cacador", "batedor", "rastreador", "sentinela"),
    "curandeiro": ("curandeir", "médic", "medic", "alquimist", "botic", "enfermeir"),
    "mago": ("mag", "arcanist", "feiticeir", "brux", "erudit", "sábi", "sabi"),
}

_NPC_V4_REQUIRED_FIELDS = (
    "virtudes",
    "vitalidade",
    "max_vitalidade",
    "ferimento_espacos",
    "ferimentos",
    "esquiva",
    "tactical_profile",
)

_NPC_V4_COPY_FIELDS = (
    *_NPC_V4_REQUIRED_FIELDS,
    "vitalidade_max_penalty",
    "categoria",
    "active_conditions",
    "conscious",
    "status",
    "tactical_archetype",
    "known_cards",
    "prepared_cards",
    "card_usage",
    "dead",
    "fled",
    "surrendered",
    "incapacitated",
    "estado_terminal",
    "last_stand_pending",
)


def _fold(s: str) -> str:
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def _archetype_for(npc: Dict) -> str:
    blob = _fold(" ".join(str(npc.get(k, "")) for k in ("role", "persona", "appearance")))
    for arch, words in _ARCHETYPE_WORDS.items():
        if any(w in blob for w in words):
            return arch
    return "capanga"


def _has_complete_v4_sheet(npc: Dict) -> bool:
    if not all(
        field in npc and npc[field] is not None
        for field in _NPC_V4_REQUIRED_FIELDS
    ):
        return False
    if not isinstance(npc.get("virtudes"), dict) or not npc["virtudes"]:
        return False
    if not isinstance(npc.get("ferimento_espacos"), dict):
        return False
    if not isinstance(npc.get("ferimentos"), dict):
        return False
    profile = npc.get("tactical_profile")
    return isinstance(profile, dict) and bool(profile.get("priorities"))


def _valid_partial_virtudes(raw: object) -> Optional[Dict[str, int]]:
    """Aceita somente uma ficha v4 parcial fechada (0..5), nunca attributes."""
    if not isinstance(raw, dict):
        return None
    keys = ("forca", "agilidade", "corpo", "mente", "carisma")
    out: Dict[str, int] = {}
    for key in keys:
        try:
            value = int(raw[key])
        except (KeyError, TypeError, ValueError):
            return None
        if not 0 <= value <= 5:
            return None
        out[key] = value
    return out


def _legacy_npc_sheet(npc: Dict, name: str) -> Dict:
    """Materializa legado só de conceitos/categorias fechadas em Python.

    ``attributes`` e ``combat_stats`` são deliberadamente excluídos. Estado
    vivo já aplicado (Vitalidade/Ferimentos/condições) sobrevive, com a
    Vitalidade limitada ao teto determinístico recém-materializado.
    """
    from services.encounter_preparation import build_npc_combat_sheet

    conceptual = {
        key: deepcopy(npc[key])
        for key in (
            "id",
            "role",
            "persona",
            "appearance",
            "tactical_archetype",
            "categoria",
        )
        if key in npc
    }
    conceptual["name"] = name
    partial_virtudes = _valid_partial_virtudes(npc.get("virtudes"))
    if partial_virtudes is not None:
        conceptual["virtudes"] = partial_virtudes
    sheet = build_npc_combat_sheet(conceptual)

    if npc.get("vitalidade") is not None:
        try:
            current = int(npc["vitalidade"])
        except (TypeError, ValueError):
            current = int(sheet["max_vitalidade"])
        maximum = int(sheet["max_vitalidade"])
        sheet["vitalidade"] = max(0, min(maximum, current))

    wounds = npc.get("ferimentos")
    if isinstance(wounds, dict):
        sheet["ferimentos"] = {
            category: deepcopy(
                wounds.get(category)
                if isinstance(wounds.get(category), list)
                else []
            )
            for category in ("leve", "grave", "critico")
        }

    for field in (
        "active_conditions",
        "conscious",
        "status",
        "dead",
        "fled",
        "surrendered",
        "incapacitated",
        "estado_terminal",
        "last_stand_pending",
    ):
        if field in npc:
            sheet[field] = deepcopy(npc[field])
    return sheet


def _npc_v4_sheet(npc: Dict, name: str) -> Dict:
    if not _has_complete_v4_sheet(npc):
        return _legacy_npc_sheet(npc, name)
    return {
        field: deepcopy(npc[field])
        for field in _NPC_V4_COPY_FIELDS
        if field in npc
    }


def make_companion_from_npc(npc: Dict, name: str) -> Dict:
    """Copia a ficha v4 do NPC ou materializa legado por tabelas Python.

    Templates fornecem somente aliases/ataques legados de compatibilidade.
    Números de ``attributes``/``combat_stats`` nunca governam a ficha canônica
    do aliado.
    """
    source = npc or {}
    arch = _archetype_for(source)
    tpl = deepcopy(
        COMPANION_TEMPLATES.get(arch)
        or COMPANION_TEMPLATES.get("capanga")
        or {}
    )
    sheet = _npc_v4_sheet(source, name)
    comp = {
        "id": source.get("id") or f"comp_{_fold(name).replace(' ', '_')}",
        "name": name,
        "archetype": arch,
        "attributes": deepcopy(
            tpl.get("attributes") or {"str": 10, "dex": 10, "con": 10}
        ),
        "attacks": deepcopy(tpl.get("attacks") or []),
        "behavior": deepcopy(tpl.get("behavior") or {"profile": "tatico"}),
        "active": True,
        "origin_npc": source.get("id") or "",
        "waiting_at": "",
        "stats": {},  # compat com o CompanionState mínimo antigo
        **sheet,
    }
    if not comp["attacks"]:
        comp["attacks"] = [{
            "name": "Golpe",
            "type": "melee",
            "bonus": 2,
            "damage": "1d6",
        }]
    from services.conflict_orchestrator import ensure_combat_sheet
    normalized = ensure_combat_sheet(comp)
    normalized["defense"] = int(normalized["esquiva"])
    return normalized


def active_allies(state: Dict) -> List[Dict]:
    return [c for c in (state.get("party") or [])
            if c.get("active") and c.get("status", "ativo") == "ativo"
            and not c.get("dead") and not c.get("fled")
            and not c.get("surrendered") and c.get("conscious", True)]


def scene_allies(state: Dict, *, excluded: Optional[List[str]] = None) -> List[Dict]:
    """spec aliados-em-combate (R2): NPCs amigos EM CENA (in_scene) que não são
    party formal → companheiros TRANSITÓRIOS (`transient=True`) p/ este combate.
    Gate determinístico: in_scene ∧ relationship>=SCENE_ALLY_MIN_REL ∧ fação
    não-hostil ∧ ainda não é companheiro. Teto MAX_SCENE_ALLIES. Não persiste
    em party (R3); some ao fim do combate. O LLM não decide nada aqui."""
    from services.npc_layers import is_in_scene
    excluded_folded = {_fold(value) for value in (excluded or []) if value}
    hostile = {f.get("id") for f in (state.get("factions") or [])
               if isinstance(f, dict) and f.get("disposition") == "hostil"}
    already = set()
    loc = str((state.get("world") or {}).get("current_location_id") or "")
    for c in (state.get("party") or []):
        if isinstance(c, dict):
            already.add(c.get("origin_npc") or "")
            already.add(c.get("name") or "")
    out: List[Dict] = []
    for name, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict) or not is_in_scene(npc):
            continue
        home = str(npc.get("home_location_id") or "")
        if home and loc and home != loc:
            continue
        identity = {name, npc.get("name", ""), npc.get("id", "")}
        if any(_fold(value) in excluded_folded for value in identity if value):
            continue
        if int(npc.get("relationship", 5) or 5) < SCENE_ALLY_MIN_REL:
            continue
        if (npc.get("faction") or "") in hostile:
            continue
        if (npc.get("id") in already) or (name in already):
            continue
        comp = make_companion_from_npc(npc, npc.get("name", name))
        comp["transient"] = True
        comp["active"] = True
        out.append(comp)
        if len(out) >= MAX_SCENE_ALLIES:
            break
    return out


def recruitment_decision(state: Dict, npc_name: str) -> RecruitmentDecision:
    """Single trait-aware authority used by product and playtest profiles."""
    npc = (state.get("npcs") or {}).get(npc_name) or {}
    rel = int(npc.get("relationship", 5) or 5)
    from services.npc_layers import trait_dc_modifier
    required = max(3, min(10, RECRUIT_MIN_REL + trait_dc_modifier(npc, "persuasao")))

    def result(ok: bool, code: str, hint: str) -> RecruitmentDecision:
        return {"ok": ok, "code": code, "relationship": rel,
                "required_relationship": required, "public_hint": hint}  # type: ignore[typeddict-item]

    if any(c.get("name") == npc_name for c in state.get("party") or []):
        return result(False, "already_member", f"{npc_name} já anda com você.")
    if len(active_allies(state)) >= MAX_ACTIVE:
        return result(False, "party_full", f"Seu grupo já está cheio ({MAX_ACTIVE} companheiros).")
    fac_id = npc.get("faction") or ""
    if any(f.get("id") == fac_id and f.get("disposition") == "hostil"
           for f in state.get("factions") or [] if fac_id):
        return result(False, "hostile", f"{npc_name} serve a um poder hostil a você.")
    if rel < required:
        return result(False, "relationship_too_low",
                      f"{npc_name} ainda não confia o bastante em você.")
    return result(True, "ok", "")


def can_recruit(state: Dict, npc_name: str) -> Tuple[bool, str]:
    """Gate DETERMINÍSTICO (o LLM só narra o sim/não):
    relationship >= 7 ∧ party ativa < 3 ∧ NPC não é de fação hostil ao jogador."""
    decision = recruitment_decision(state, npc_name)
    return decision["ok"], decision["public_hint"]


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
        if "status" not in c:
            c["status"] = (
                "ativo"
                if c.get("vitalidade") is not None or int(c.get("hp", 1)) > 0
                else "morto"
            )
        c.setdefault("origin_npc", "")
        c.setdefault("waiting_at", "")
        from services.conflict_orchestrator import ensure_combat_sheet
        out.append(ensure_combat_sheet(c))
    return out
