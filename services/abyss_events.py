"""services/abyss_events.py — eventos do Abismo em conflito (spec conflito-10).

Camada NOVA e complementar aos gatilhos de classe já existentes
(`apply_entropy_trigger`/`special_rule`/`abyss.consequence` em `combat_mechanics.py`,
que NÃO mudam): eventos do Abismo preparados pela LLM ANTES do conflito (schema/
prompt de geração é conflito-11), carregáveis SEM LLM durante o combate por
Cargas + gatilho + prioridade + estado da cena + usos, reusando o catálogo FECHADO
de `EffectSpec.kind` da conflito-03. O Abismo é impessoal: transforma o que já
existe, nunca cria do nada, e respeita proibições rígidas (R4/R6).

ADITIVO: módulo novo + testes. O consumidor de `abyss_charge` e a fiação no loop
de combate entram no cutover (conflito-13).
"""
from typing import List, Optional, Tuple
import random

from pydantic import BaseModel, Field

from services import conflict_scene as cs

# R3: assinatura visual FIXA e recorrente — nunca variada pela LLM em tempo real.
ABYSS_SIGNATURE = (
    "O som ambiente abafa; as cores perdem intensidade; uma fissura negra fina se "
    "abre; um pulso pálido atravessa a cena; a realidade muda; a fissura some, mas a "
    "mudança permanece."
)

# R4: condições que o Abismo NÃO pode impor (controle mental / obrigar contra a
# personalidade — o Abismo é impessoal, sem plano sobre a mente alheia).
_FORBIDDEN_CONDITIONS = frozenset({
    "controle_mental", "controle mental", "dominado", "enfeiticado", "possuido",
})


# ==========================================================================
# Schema
# ==========================================================================
class PreparedAbyssEvent(BaseModel):
    id: str
    gatilho: str = "sempre"
    prioridade: int = 0
    cargas_necessarias: int = 1
    effect: dict = Field(default_factory=dict)     # EffectSpec (conflito-03)
    usos_permitidos: int = 1
    base_na_cena: str = ""                          # elemento existente que justifica o evento


# ==========================================================================
# Etapa 1 — base na cena (R5) + catálogo fechado (R6/§03)
# ==========================================================================
def _scene_tokens(scene_objects) -> set:
    tokens = set()
    for o in scene_objects or []:
        if isinstance(o, dict):
            for k in ("id", "name"):
                v = str(o.get(k, "") or "").strip().lower()
                if v:
                    tokens.add(v)
            for tag in (o.get("tags") or []):
                tokens.add(str(tag).strip().lower())
        else:
            tokens.add(str(o).strip().lower())
    return tokens


def validate_event_has_scene_basis(event: dict, scene_objects) -> bool:
    """R5: o evento só é válido se `base_na_cena` referencia um elemento QUE JÁ
    EXISTE na cena (id/nome/tag de objeto) e o `effect.kind` está no catálogo
    fechado (mesma validação da conflito-03 R6/R8). Sem base = rejeitado (nada 'do
    nada')."""
    base = str(event.get("base_na_cena") or "").strip().lower()
    if not base:
        return False
    if not cs.validate_effect_kind(event.get("effect") or {}):
        return False
    tokens = _scene_tokens(scene_objects)
    if base in tokens:
        return True
    return any(tok and (base in tok or tok in base) for tok in tokens)


# ==========================================================================
# Etapa 2 — carregamento determinístico/por seed (R2)
# ==========================================================================
def _gatilho_valid(gatilho: str, scene_state: dict) -> bool:
    g = str(gatilho or "").strip().lower()
    if g in ("sempre", "always", ""):
        return True
    return bool((scene_state or {}).get(g))


def _usos_restantes(event: dict) -> int:
    return int(event.get("usos_restantes", event.get("usos_permitidos", 1)) or 0)


def can_trigger(event: dict, scene_state: Optional[dict], charges_available: int, *,
                scene_objects=None) -> bool:
    """R2: pode carregar SE Cargas suficientes + usos restantes + gatilho válido no
    estado da cena (+ base na cena, quando os objetos forem passados). 100%
    determinístico, sem LLM."""
    if int(charges_available) < int(event.get("cargas_necessarias", 1) or 0):
        return False
    if _usos_restantes(event) <= 0:
        return False
    if not _gatilho_valid(event.get("gatilho"), scene_state or {}):
        return False
    if scene_objects is not None and not validate_event_has_scene_basis(event, scene_objects):
        return False
    return True


def select_event(events: List[dict], scene_state: Optional[dict], charges_available: int, *,
                 seed=None, scene_objects=None) -> Optional[dict]:
    """R2: entre os eventos que podem carregar, a maior PRIORIDADE vence; empate é
    resolvido deterministicamente por seed (ou por id, estável). Sem candidato → None."""
    candidatos = [e for e in (events or [])
                  if can_trigger(e, scene_state, charges_available, scene_objects=scene_objects)]
    if not candidatos:
        return None
    top = max(int(e.get("prioridade", 0) or 0) for e in candidatos)
    empatados = [e for e in candidatos if int(e.get("prioridade", 0) or 0) == top]
    if len(empatados) == 1:
        return empatados[0]
    empatados.sort(key=lambda e: str(e.get("id", "")))
    if seed is not None:
        return empatados[random.Random(seed).randrange(len(empatados))]
    return empatados[0]


# ==========================================================================
# Etapa 3 — proibições do Abismo (R4/R6)
# ==========================================================================
def validate_abyss_effect(effect: dict, *, context: Optional[dict] = None) -> Tuple[bool, str]:
    """R4/R6: o que o Abismo pode/não pode. Retorna (ok, motivo). Proíbe: desfazer
    sucesso já resolvido, controlar mentalmente / obrigar contra a personalidade,
    criar Ferimento direto, agravar Ferimento fora do combate normal, e qualquer
    kind fora do catálogo fechado (R5)."""
    ctx = context or {}
    if not cs.validate_effect_kind(effect or {}):
        return False, "efeito fora do catálogo fechado"
    kind = str((effect or {}).get("kind", "")).lower()
    params = (effect or {}).get("params") or {}

    if params.get("undo_resolved") or ctx.get("targets_resolved_success"):
        return False, "não desfaz sucesso já resolvido (R6)"
    if kind == "apply_condition":
        cond = str(params.get("condition", "")).lower()
        if (cond in _FORBIDDEN_CONDITIONS or params.get("mind_control")
                or params.get("force_against_personality")):
            return False, "não controla mentalmente nem obriga contra a personalidade"
    if params.get("direct_wound") or params.get("aggravate_wound_out_of_combat"):
        return False, "não cria nem agrava Ferimento diretamente"
    return True, ""


# ==========================================================================
# Etapa 4 — disparo + assinatura + exposição de gasto (R3)
# ==========================================================================
def trigger_event(event: dict, scene_state: Optional[dict] = None, *,
                  context: Optional[dict] = None) -> dict:
    """Dispara um evento preparado: valida as proibições (R4/R6), decrementa os usos
    e devolve o EffectSpec (aplicado pelo mesmo aplicador da conflito-03) + o log com
    a assinatura fixa e o gasto de Carga reportado IMEDIATAMENTE (R3). NÃO chama LLM."""
    ok, reason = validate_abyss_effect(event.get("effect") or {}, context=context)
    if not ok:
        return {"ok": False, "error": reason, "effect": None}
    cargas = int(event.get("cargas_necessarias", 1) or 0)
    event["usos_restantes"] = max(0, _usos_restantes(event) - 1)
    return {
        "ok": True, "error": None, "effect": event.get("effect"),
        "cargas_gastas": cargas, "signature": ABYSS_SIGNATURE,
        "log": f"[ABISMO] {cargas} Carga(s) gasta(s). {ABYSS_SIGNATURE}",
    }


def abyss_signature() -> str:
    return ABYSS_SIGNATURE
