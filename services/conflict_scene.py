"""services/conflict_scene.py — cena de conflito posicional (spec conflito-03).

Estrutura de dados PURA (dict-based, serializável no save) para o combate novo:
zonas nomeadas (não-grid), 3 eixos independentes de posição (Distância/Postura/
Ocultação), Engajamento como relação separada, objetos interativos com catálogo
FECHADO de efeitos, e a regra de CENA CONGELADA (nada entra por interpretação
livre depois do início). NÃO resolve dano/efeito — isso é conflito-04/05.

Convivência: `round/active/order/idle_turns` do dict `combat` seguem existindo em
paralelo até o cutover (conflito-13). A ConflictScene mora em `combat["scene"]`.
"""
from typing import Dict, List, Optional

# --- Eixos independentes -----------------------------------------------------
DISTANCES = ("proximo", "distante", "separado")   # 3 estágios (R2)
POSTURAS = ("protegido", "neutro", "exposto")      # 3 estados (R2)
OCULTACOES = ("visivel", "escondido")              # 2 estados (R2)

# --- Catálogo FECHADO de efeitos (R6) — compartilhado com conflito-10/11 ------
EFFECT_KINDS = frozenset({
    "alter_terrain", "block_route", "unblock_route", "damage",
    "request_reaction", "apply_condition", "reposition",
    "spawn_reinforcement", "destroy_object", "change_environment_condition",
})

_COST_STATES = ("pre_acao", "pos_acao", "acao")


def validate_effect_kind(effect: dict) -> bool:
    """True se `effect.kind` está no catálogo fechado (R6). Efeito inventado pela
    LLM fora do catálogo é rejeitado — nunca vira regra nova."""
    return bool(effect) and str(effect.get("kind")) in EFFECT_KINDS


# --- Construção --------------------------------------------------------------
def new_scene(zones: Optional[List[dict]] = None) -> dict:
    return {
        "zones": list(zones or [{"id": "z0", "name": "Campo", "connections": []}]),
        "positions": {},
        "objects": [],
        "frozen": False,
        "reinforcement_triggers": [],
    }


def place(scene: dict, participant_id: str, *, zone_id: str = "z0",
          distance_state: str = "proximo", postura: str = "neutro",
          ocultacao: str = "visivel") -> dict:
    """Posiciona um participante. Bloqueado se a cena já está congelada (R8) —
    participantes entram na preparação, não no meio do conflito."""
    if scene.get("frozen"):
        return {"ok": False, "error": "Cena congelada: participante não entra fora de gatilho.", "log": ""}
    scene.setdefault("positions", {})[participant_id] = {
        "zone_id": zone_id,
        "distance_state": distance_state if distance_state in DISTANCES else "proximo",
        "postura": {"state": postura if postura in POSTURAS else "neutro",
                    "mode": "sustentado", "cause": None},
        "ocultacao": ocultacao if ocultacao in OCULTACOES else "visivel",
        "engaged_with": [],
    }
    return {"ok": True, "error": None, "log": f"{participant_id} posicionado."}


# --- Distância (R3) ----------------------------------------------------------
def move_distance(scene: dict, participant_id: str, direction: str,
                  via: str = "pre") -> dict:
    """Move 1 estágio de Distância por Pré-Ação OU Pós-Ação (R3). Usar as duas no
    mesmo turno = 2 chamadas = atravessa 2 estágios. `direction`: aproximar|afastar."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return {"ok": False, "error": f"{participant_id} não está na cena.", "log": ""}
    idx = DISTANCES.index(pos.get("distance_state", "proximo"))
    d = str(direction or "").lower()
    if d in ("aproximar", "approach", "closer", "-"):
        idx = max(0, idx - 1)
    elif d in ("afastar", "away", "farther", "+"):
        idx = min(len(DISTANCES) - 1, idx + 1)
    else:
        return {"ok": False, "error": "Direção inválida (aproximar|afastar).", "log": ""}
    pos["distance_state"] = DISTANCES[idx]
    return {"ok": True, "error": None, "distance_state": DISTANCES[idx],
            "via": via, "log": f"{participant_id} -> {DISTANCES[idx]} ({via})"}


# --- Engajamento (relação separada da distância, R2) -------------------------
def engage(scene: dict, a: str, b: str) -> dict:
    pa = (scene.get("positions") or {}).get(a)
    pb = (scene.get("positions") or {}).get(b)
    if not pa or not pb:
        return {"ok": False, "error": "Participante ausente da cena.", "log": ""}
    if b not in pa["engaged_with"]:
        pa["engaged_with"].append(b)
    if a not in pb["engaged_with"]:
        pb["engaged_with"].append(a)
    return {"ok": True, "error": None, "log": f"{a} e {b} engajados."}


def disengage(scene: dict, a: str, b: str) -> dict:
    for x, y in ((a, b), (b, a)):
        p = (scene.get("positions") or {}).get(x)
        if p and y in p.get("engaged_with", []):
            p["engaged_with"].remove(y)
    return {"ok": True, "error": None, "log": f"{a} e {b} desengajados."}


def is_engaged(scene: dict, a: str, b: str) -> bool:
    p = (scene.get("positions") or {}).get(a) or {}
    return b in p.get("engaged_with", [])


# --- Postura / Ocultação (R4) ------------------------------------------------
def set_postura(scene: dict, participant_id: str, state: str, *,
                mode: str = "sustentado", cause: Optional[str] = None) -> dict:
    """Protegido/Exposto momentâneo (só o próximo ataque) ou sustentado (persiste
    enquanto a causa concreta existir)."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return {"ok": False, "error": f"{participant_id} não está na cena.", "log": ""}
    if state not in POSTURAS:
        return {"ok": False, "error": f"Postura inválida: {state}.", "log": ""}
    pos["postura"] = {"state": state,
                      "mode": "momentaneo" if mode == "momentaneo" else "sustentado",
                      "cause": cause}
    return {"ok": True, "error": None, "log": f"{participant_id}: {state} ({mode})."}


def consume_postura_on_attack(scene: dict, participant_id: str) -> None:
    """Postura MOMENTÂNEA expira depois do próximo ataque aplicável (R4). A
    sustentada não é tocada aqui (some só quando a causa é removida)."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return
    postura = pos.get("postura") or {}
    if postura.get("mode") == "momentaneo" and postura.get("state") != "neutro":
        pos["postura"] = {"state": "neutro", "mode": "sustentado", "cause": None}


def clear_sustained_postura(scene: dict, participant_id: str, cause: str) -> None:
    """Remove a Postura sustentada quando a causa concreta (pilastra/corrente/
    cobertura/Guardar) deixa de existir (R4)."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return
    postura = pos.get("postura") or {}
    if postura.get("mode") == "sustentado" and postura.get("cause") == cause:
        pos["postura"] = {"state": "neutro", "mode": "sustentado", "cause": None}


# --- Objetos interativos (R5/R7) ---------------------------------------------
def add_object(scene: dict, obj: dict, *, from_trigger: bool = False) -> dict:
    """Adiciona objeto à cena. Bloqueado após o congelamento (R8), salvo se vier
    de um gatilho de reforço declarado antes do início."""
    if scene.get("frozen") and not from_trigger:
        return {"ok": False, "error": "Cena congelada: nenhum objeto novo entra.", "log": ""}
    o = dict(obj)
    o.setdefault("secret", False)
    o.setdefault("discovered", False)
    o.setdefault("destroyed", False)
    o.setdefault("interactions", [])
    scene.setdefault("objects", []).append(o)
    return {"ok": True, "error": None, "log": f"Objeto '{o.get('name', o.get('id'))}' na cena."}


def visible_objects(scene: dict) -> List[dict]:
    """Objetos que o jogador ENXERGA: não-destruídos e (não-secretos OU já
    descobertos) (R7). Cada interação expõe só label+cost, nunca o effect (R5)."""
    out = []
    for o in scene.get("objects", []):
        if o.get("destroyed"):
            continue
        if o.get("secret") and not o.get("discovered"):
            continue
        out.append({
            "id": o.get("id"), "name": o.get("name"),
            "distance_state": o.get("distance_state"), "zone_id": o.get("zone_id"),
            "interactions": [{"label": it.get("label"), "cost": it.get("cost")}
                             for it in o.get("interactions", [])],
            "uses_remaining": o.get("uses_remaining"),
        })
    return out


def discover_object(scene: dict, object_id: str) -> dict:
    for o in scene.get("objects", []):
        if o.get("id") == object_id:
            o["discovered"] = True
            return {"ok": True, "error": None, "log": f"'{o.get('name', object_id)}' descoberto."}
    return {"ok": False, "error": f"Objeto '{object_id}' não existe.", "log": ""}


def _find_object(scene: dict, object_id: str) -> Optional[dict]:
    for o in scene.get("objects", []):
        if o.get("id") == object_id:
            return o
    return None


def apply_object_interaction(scene: dict, object_id: str, interaction_label: str,
                             actor_id: str) -> dict:
    """Executa uma interação de objeto: devolve o EffectSpec (validado contra o
    catálogo fechado) e decrementa usos/destrói. NÃO resolve o efeito (conflito-04)."""
    obj = _find_object(scene, object_id)
    if not obj or obj.get("destroyed"):
        return {"ok": False, "error": f"Objeto '{object_id}' indisponível.", "effect": None}
    if obj.get("secret") and not obj.get("discovered"):
        return {"ok": False, "error": "Objeto secreto ainda não descoberto.", "effect": None}
    it = next((i for i in obj.get("interactions", []) if i.get("label") == interaction_label), None)
    if not it:
        return {"ok": False, "error": f"Interação '{interaction_label}' inexistente.", "effect": None}
    effect = it.get("effect") or {}
    if not validate_effect_kind(effect):
        return {"ok": False, "error": f"Efeito fora do catálogo: {effect.get('kind')!r}.", "effect": None}

    left = obj.get("uses_remaining")
    if left is not None:
        if int(left) <= 0:
            return {"ok": False, "error": "Objeto sem usos restantes.", "effect": None}
        obj["uses_remaining"] = int(left) - 1
        if obj["uses_remaining"] <= 0:
            obj["destroyed"] = True
    if effect.get("kind") == "destroy_object":
        obj["destroyed"] = True
    return {"ok": True, "error": None, "effect": effect,
            "log": f"{actor_id} usa '{interaction_label}' em '{obj.get('name', object_id)}'."}


# --- Cena congelada (R8) -----------------------------------------------------
def freeze(scene: dict) -> dict:
    """Congela a cena no início do conflito: nada é acrescentado por interpretação
    livre depois disso (R8)."""
    scene["frozen"] = True
    return scene


def add_reinforcement_trigger(scene: dict, trigger: dict) -> dict:
    """Declara ANTES do início um gatilho de reforço (spawn_reinforcement). Só
    esses podem introduzir participantes/objetos depois do congelamento (R8)."""
    if scene.get("frozen"):
        return {"ok": False, "error": "Gatilhos de reforço só antes de congelar.", "log": ""}
    scene.setdefault("reinforcement_triggers", []).append(dict(trigger))
    return {"ok": True, "error": None, "log": "Gatilho de reforço registrado."}


def fire_reinforcement(scene: dict, trigger_id: str) -> dict:
    """Dispara um gatilho de reforço preparado — a única via de entrada de novos
    elementos numa cena congelada (R8)."""
    trig = next((t for t in scene.get("reinforcement_triggers", [])
                 if t.get("id") == trigger_id), None)
    if not trig:
        return {"ok": False, "error": f"Gatilho '{trigger_id}' não foi preparado.", "effect": None}
    for obj in trig.get("objects", []) or []:
        add_object(scene, obj, from_trigger=True)
    for pid, ppos in (trig.get("participants") or {}).items():
        scene.setdefault("positions", {})[pid] = ppos
    return {"ok": True, "error": None, "log": f"Reforço '{trigger_id}' disparado.",
            "effect": {"kind": "spawn_reinforcement", "params": {"trigger": trigger_id}}}
