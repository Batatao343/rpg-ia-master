"""Narration agent that advances the story and campaign plan."""

import random
import re
from collections import Counter
from copy import deepcopy
from typing import Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from agents.npc import generate_new_npc
from agents.world_simulator import simulate_world
from llm_setup import get_llm
from observability.telemetry import log_event as _log_event
from rag import query_rag
from services import discovery as disc
from services import graph_resolver as gr
from services import law as _law_mod
from services import quest_log
from services.context_builder import build_context_pack
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages
from services.structured_outputs import (
    CrimeClaim,
    ProposedQuest,
    ProposedWorldEvent,
    coerce_crime_claims,
)
from state import GameState
from world_utils import (
    advance_factions,
    apply_rest,
    apply_travel,
    check_encounter,
    clock_label,
    ensure_faction_intel,
    ensure_factions,
    ensure_world,
    find_travel_destination,
    is_rest,
    is_travel_intent,
    resolve_faction_completions,
)


class FactionImpact(BaseModel):
    faction_id: str = Field(
        description="id EXATO de uma fação listada em <FACÇÕES_CONHECIDAS>; vazio se nenhuma."
    )
    direction: Literal["ajudou", "prejudicou"] = Field(
        description="'ajudou' (jogador beneficiou a fação) ou 'prejudicou' (jogador a atrapalhou/traiu/atacou)."
    )
    magnitude: Literal["menor", "maior"] = Field(
        default="menor",
        description="'maior' só para ato decisivo e inequívoco; na dúvida 'menor'.",
    )


def _coerce_faction_impacts(raw: object) -> list:
    """SPEC-298 R10: impacto com direction/magnitude fora do Literal é DESCARTADO
    (nunca derruba a resposta inteira — padrão SPEC-045)."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if isinstance(item, FactionImpact):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        if item.get("direction") not in ("ajudou", "prejudicou"):
            continue
        magnitude = item.get("magnitude", "menor")
        if magnitude not in ("menor", "maior"):
            magnitude = "menor"
        out.append({**item, "magnitude": magnitude})
    return out


class StoryUpdate(BaseModel):
    # default "" (não required): Gemini real às vezes omite o campo num schema
    # grande — melhor narrar via fallback do que perder o turno (smoke 2026-07-05)
    narrative: str = Field(
        default="", description="O texto narrativo da resposta. OBRIGATÓRIO: sempre preencha."
    )
    introduced_npcs: list[str] = Field(
        default_factory=list,
        description="Nomes de personagens que ENTRARAM na cena neste turno (novos ou conhecidos que reapareceram).",
    )
    npcs_left_scene: list[str] = Field(
        default_factory=list,
        description="Nomes de personagens JÁ CONHECIDOS que SAÍRAM da cena neste turno (foram embora, morreram, sumiram). Vazio se ninguém saiu.",
    )
    faction_impacts: list[FactionImpact] = Field(
        default_factory=list,
        description=(
            "Fações afetadas pela AÇÃO do jogador NESTE turno. Vazio se a ação não ajuda "
            "nem prejudica claramente uma fação listada. Use o faction_id EXATO."
        ),
    )

    @field_validator("faction_impacts", mode="before")
    @classmethod
    def _drop_invalid_impacts(cls, v: object) -> list:
        return _coerce_faction_impacts(v)

    crime_claims: list[CrimeClaim] = Field(
        default_factory=list,
        description=(
            "Crimes que a AÇÃO do jogador cometeu NESTE turno (furto, agressao, homicidio, "
            "dano_propriedade, magia_ilegal). Vazio se não houve crime — na dúvida, vazio."
        ),
    )

    @field_validator("crime_claims", mode="before")
    @classmethod
    def _drop_invalid_crimes(cls, v: object) -> list:
        return coerce_crime_claims(v)

    beat_completed: bool = Field(
        default=False,
        description=(
            "True SOMENTE se a ação deste turno cumpriu de forma clara o Objetivo Atual "
            "da cena (o beat ativo). Caso contrário False. Não marque True por progresso vago."
        ),
    )
    proposed_events: list[ProposedWorldEvent] = Field(
        default_factory=list,
        description=(
            "APENAS se a ação deste turno causou mudança PERSISTENTE no mundo "
            "(morte de personagem NOMEADO, segredo revelado, mudança de controle de local). "
            "Use ids EXATOS do bloco <ENTIDADES_CANONICAS>. Deixe vazio na dúvida. "
            "Para CONCLUIR uma quest listada em <QUESTS_ATIVAS>, proponha um evento "
            "type='quest_completed' com target_id=quest_id e payload={'quest_id': quest_id}."
        ),
    )
    proposed_quests: list[ProposedQuest] = Field(
        default_factory=list,
        description=(
            "APENAS se um personagem PRESENTE NA CENA ofereceu uma missão CONCRETA ao "
            "jogador NESTE turno. origin_name = quem pediu; origin_entity_id = id EXATO "
            "do bloco <ENTIDADES_CANONICAS> se houver, senão vazio; location_id só se o "
            "destino for claro. Deixe vazio na dúvida — não invente missões."
        ),
    )
    items_gained: list[str] = Field(
        default_factory=list,
        description=(
            "APENAS se a narrativa deu um item CONCRETO ao jogador NESTE turno "
            "(recebeu, pegou, ganhou). Nome do item conhecido — NÃO invente itens "
            "novos (criação de item é papel do baú/loja). Vazio na dúvida."
        ),
    )


_MONEY_CLAIM_RE = re.compile(r"\b(?:ouro|moedas?)\b", re.IGNORECASE)


def encounter_handoff(enc: dict) -> dict:
    """SPEC-203 R3(a): referência canônica one-shot do encontro sistêmico para o
    spawn do combate (o `enemy_id` do bestiário não se perde no handoff)."""
    enc = enc or {}
    out = {
        "enemy_id": str(enc.get("enemy_id") or ""),
        "reason": str(enc.get("reason") or ""),
        "hint": str(enc.get("hint") or ""),
    }
    # SPEC-292: rótulo seguro p/ o jogador só quando difere do canônico (fação oculta)
    public = str(enc.get("public_hint") or "")
    if public and public != out["hint"]:
        out["public_hint"] = public
    return out


def _is_monetary_claim(value: object) -> bool:
    """Dinheiro é economia, nunca um item a resolver pelo nome livre do LLM."""
    return bool(_MONEY_CLAIM_RE.search(str(value or "")))


def _inventory_counts(player: dict) -> Counter:
    counts: Counter = Counter()
    for entry in player.get("inventory") or []:
        if isinstance(entry, dict) and entry.get("id"):
            counts[str(entry["id"])] += int(entry.get("qty", 1) or 1)
    return counts


def _reward_confirmation(before: dict, after: dict) -> str:
    """Linha canônica derivada somente do delta mecânico confirmado."""
    rewards: list[str] = []
    gold_delta = int(after.get("gold", 0) or 0) - int(before.get("gold", 0) or 0)
    if gold_delta > 0:
        rewards.append(f"+{gold_delta} de ouro")
    before_items = _inventory_counts(before)
    after_items = _inventory_counts(after)
    if after_items:
        from inventory import item_display, make_entry

        for item_id, qty in (after_items - before_items).items():
            label = item_display(make_entry(item_id))
            rewards.append(f"{label}" + (f" ×{qty}" if qty > 1 else ""))
    return "Recompensa confirmada: " + ", ".join(rewards) + "." if rewards else ""


def _scene_canonical_entities(state: GameState, factions: list, intel: dict, loc: str) -> str:
    """Ids+nomes canônicos (entities.json) das entidades da cena — o LLM só pode usar estes.

    Fações conhecidas já trazem id canônico; local e NPCs presentes casam por nome com o
    grafo (best-effort). Defensivo: qualquer falha vira lista vazia (o validator é o gate real).
    """
    lines: list[str] = []
    seen = set()
    for f in factions:
        fid = f.get("id")
        if (
            fid
            and intel.get(fid, {}).get("known")
            and not f.get("defeated")
            and fid not in seen
            and gr.get_entity(fid)
        ):
            lines.append(f"- id={fid} · {f.get('name')} · faction")
            seen.add(fid)
    try:
        entities = gr.load_entities()
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "entities_unavailable", exc)
        entities = {}
    names_present = {n.lower() for n in state.get("npcs", {}).keys()}
    loc_l = (loc or "").strip().lower()
    for eid, ent in entities.items():
        if eid in seen:
            continue
        etype, ename = ent.get("type"), ent.get("name", "")
        nl = ename.lower()
        if etype == "location" and loc_l and (nl == loc_l or eid == loc_l):
            lines.append(f"- id={eid} · {ename} · location")
            seen.add(eid)
        elif etype == "npc" and nl in names_present:
            lines.append(f"- id={eid} · {ename} · npc")
            seen.add(eid)
    return "\n".join(lines) or "Nenhuma entidade canônica identificada na cena."


def _quests_ativas_block(quests: list[dict], state: dict | None = None) -> str:
    """Fase 3.3: side quests ativas — o LLM só pode referenciar estes ids em quest_completed.

    SPEC-223 R1: cada linha diz se o ESTADO já prova a conclusão; sem prova o
    motor rejeita a proposta (o narrador não decide que a missão acabou)."""
    ativas = [q for q in (quests or []) if q.get("status") == "active"]
    if not ativas:
        return "Nenhuma missão pendente registrada."

    def _prova(q: dict) -> str:
        if state is None:
            return ""
        ok, _why = quest_log.has_completion_proof(q, state)
        return " · prova: ok" if ok else " · prova: pendente"

    return "\n".join(
        f"- id={q.get('id')} · {q.get('title')} · origem: {q.get('origin_name', '?')}{_prova(q)}"
        for q in ativas
    )


def _npc_fallback_clause(state: GameState) -> str:
    """spec npc-fallback-sem-alvo (R2): quando a rota NPC não achou interlocutor,
    o storyteller narra a AUSÊNCIA (sem inventar NPC em cena) e dá um gancho útil
    (onde há gente / o objetivo atual). Pura — testável sem LLM."""
    hint = state.get("npc_fallback_hint")
    if not hint:
        return ""
    from services.social_direction import build_social_direction

    direction = build_social_direction(state)
    return (
        f"\n    - SEM INTERLOCUTOR: o jogador tentou falar com alguém "
        f'("{str(hint)[:120]}"), mas NÃO há ninguém por perto para responder. '
        "Narre a solidão/silêncio SEM inventar um NPC novo em cena, e ofereça "
        f"esta direção ÚTIL e canônica: {direction}"
    )


def _mediated_subject_view(state: GameState) -> dict | None:
    """SPEC-202 R11: recorte PÚBLICO (camada 2) do NPC de quem o narrador fala."""
    subject_id = state.get("mediated_subject_id")
    if not subject_id:
        return None
    from services import interlocutor, npc_layers

    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict) and interlocutor.canonical_npc_id(state, key) == subject_id:
            views = npc_layers.visible_npc_view({key: row})
            if not views:
                return None
            view = dict(views[0])
            # R15(b): pronome só se o registro já tiver o campo (P4: sem dado novo).
            for field in ("pronouns", "pronome", "gender", "genero"):
                if row.get(field):
                    view["pronome"] = str(row[field])
                    break
            return view
    return None


def _mediation_clause(state: GameState) -> str:
    """SPEC-202 R2/R7/R11: o narrador responde SOBRE um NPC ou media vários
    presentes — sem fala em 1ª pessoa de personagem, só dados públicos. Pura."""
    from services import interlocutor

    reason = state.get("interlocutor_reason")
    if reason not in interlocutor.MEDIATION_REASONS:
        return ""
    if reason == "ambiguous_multi_mediated":
        present = (
            ", ".join(
                interlocutor.canonical_npc_name(state, key)
                for key in interlocutor.scene_keys(state)
            )
            or "ninguém"
        )
        return (
            "\n    - VÁRIOS PRESENTES: o jogador falou sem indicar a quem "
            f"({present}). Descreva quem está presente e como cada um reage, "
            "sem eleger um porta-voz que responda em primeira pessoa."
        )
    clause = (
        "\n    - PERGUNTA AO NARRADOR: o jogador se dirigiu a VOCÊ (narrador), "
        "não a um personagem. Responda como narrador, em terceira pessoa, só com "
        "o que o herói pode observar ou já sabe; NENHUM personagem fala em "
        "primeira pessoa e nada oculto é revelado."
    )
    view = _mediated_subject_view(state)
    if view:
        traits = (
            ", ".join(
                t.get("name", "") for t in view.get("revealed_traits") or [] if isinstance(t, dict)
            )
            or "nenhum percebido"
        )
        parts = [
            f"nome={view.get('name', '')}",
            f"papel={view.get('role') or '?'}",
            "presente na cena="
            + ("sim (descreva o que o herói observa nele/nela)" if view.get("in_scene") else "não"),
            f"relação com o herói={view.get('relationship', 5)}/10",
            f"traços já percebidos={traits}",
        ]
        if view.get("pronome"):
            parts.append(f"pronome={view['pronome']}")
        if view.get("last_memory"):
            parts.append(f"última lembrança={str(view['last_memory'])[:160]}")
        clause += " Sujeito (dados públicos): " + "; ".join(parts) + "."
    return clause


def _log_narrative_rejected(kind: str, codes: list[str]) -> None:
    """SPEC-252 R2: `narrative.rejected` (kind item|event|mediation + reason_code fechado), 1 linha
    por (kind, reason_code) com `count`; a contagem por kind tambem vai em `rpg.turn`."""
    from observability.telemetry import count_turn

    for code, n in Counter(codes).items():
        _log_event("narrative", "rejected", level="info", kind=kind, reason_code=code, count=n)
    count_turn(kind, len(codes))


def _guard_mediation_secret(text: str, state: GameState) -> tuple[str, list[str]]:
    """SPEC-202 R11: parágrafo mediado com assinatura de segredo não revelado vira
    descrição observável neutra (determinística) + registro de rejeição."""
    from services import interlocutor
    from services.secret_signatures import find_unrevealed

    if state.get("interlocutor_reason") not in interlocutor.MEDIATION_REASONS:
        return text, []
    hit = find_unrevealed(text, state)
    if not hit:
        return text, []
    view = _mediated_subject_view(state) or {}
    who = view.get("name") or "A cena"
    neutral = (
        f"{who} não deixa transparecer mais do que o óbvio; o que você "
        "consegue observar não basta para afirmar nada além disso."
    )
    rejections: list[str] = []
    paragraphs = str(text).split("\n\n")
    out: list[str] = []
    for paragraph in paragraphs:
        found = find_unrevealed(paragraph, state)
        if found:
            rejections.append(f"mediation_secret:{found[0]}")
            if neutral not in out:
                out.append(neutral)
        else:
            out.append(paragraph)
    if not rejections:  # assinatura atravessando parágrafos: troca o texto todo
        out, rejections = [neutral], [f"mediation_secret:{hit[0]}"]
    return "\n\n".join(out), list(dict.fromkeys(rejections))


def _player_facing_note(note: str) -> str:
    """Converte notas de prompt em texto diegético; não vaza imperativos internos."""
    text = str(note or "").strip()
    if not text:
        return ""
    text = re.sub(r"^O jogador VIAJOU para ", "Após a viagem, você chega a ", text)
    text = re.sub(r"^O jogador ENTROU em ", "Você entra em ", text)
    text = re.sub(
        r"^O jogador ENCONTROU um baú/esconderijo em ([^:]+):\s*",
        r"Entre os vestígios de \1, você encontra um baú/esconderijo: ",
        text,
    )
    text = re.sub(
        r"^Ao explorar ([^,]+), o jogador ENCONTROU:\s*", r"Ao explorar \1, você encontra ", text
    )
    # SPEC-233 R8: notas de descanso viram texto diegético de 2ª pessoa.
    text = re.sub(r"^O jogador DESCANSOU\.\s*", "Você descansa. ", text)
    text = text.replace("O tempo avançou para", "O tempo avança para")
    text = text.replace("e ele recuperou parte das forças", "e você recupera parte das forças")
    text = re.sub(r"^O jogador TENTOU descansar, mas", "Você tenta descansar, mas", text)
    text = text.replace("NÃO permite descanso seguro", "não permite descanso seguro")
    text = text.replace("NADA foi recuperado", "nada foi recuperado")
    text = re.sub(r"\s*Descreva\b[^.]*\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*Narre\b[^.]*\.?", "", text, flags=re.IGNORECASE)
    from services import prose_guard

    return prose_guard.sanitize_player_facing(text)


def _dedupe_encounter(enc, world: dict):
    """spec encontros-dedupe (R3) + SPEC-233 R6: não repete o MESMO template de encontro
    2x seguidas no mesmo local — exceto reforços/controle, consequência prometida."""
    if not enc:
        return enc
    if enc.get("reason") in ("reinforcements", "controlled"):
        return enc
    if (
        enc.get("hint")
        and enc.get("hint") == world.get("last_encounter_id")
        and world.get("last_encounter_loc") == world.get("current_location_id")
    ):
        return None
    return enc


def _deterministic_story_fallback(notes, light: dict) -> str:
    """Fallback visível e contextual; nunca expõe erro de provider ao jogador."""
    parts = [_player_facing_note(note) for note in notes if str(note or "").strip()]
    parts = [part for part in parts if part]
    if light.get("dark"):
        parts.append(
            "Sem fonte de luz, a escuridão limita sua visão; sons e cheiros "
            "chegam antes das formas."
        )
    elif light.get("label") == "iluminado pela sua luz":
        parts.append(
            "A luz que você carrega abre um círculo trêmulo no breu e revela o espaço imediato."
        )
    return "\n".join(parts) or ("O momento passa em silêncio; o mundo aguarda seu próximo passo.")


def _typed_by_player(name: str, player_inputs) -> bool:
    from services.shared_pool import name_typed_by_player

    return name_typed_by_player(name, player_inputs)


def _pool_enabled() -> bool:
    from services.shared_pool import enabled

    return enabled()


def _cast_match(cast: list | None, name: str):
    """Entrada do elenco oferecido cujo nome (dobrado) bate com o introduzido."""
    if not cast:
        return None
    from services.shared_pool_models import fold_name

    folded = fold_name(name)
    return next((e for e in cast if e.name_fold == folded), None)


def _with_new_npc(
    npcs: dict[str, dict],
    new_name: str,
    loc: str,
    narrative_text: str,
    game_id: str = "",
    home_id: str = "",
    turn: int = 0,
    cast: list | None = None,
    pool_used_out: list | None = None,
    player_inputs: tuple = (),
) -> dict[str, dict]:
    from services import npc_layers
    from services.entity_identity import find_runtime_npc_key

    canonical = find_runtime_npc_key(npcs, new_name)
    if canonical is not None:
        # já conhecido: a cena o trouxe de volta (camada 3).
        # spec encontros-dedupe (exceção narrativa): re-introduzir um NPC conhecido
        # é uma decisão DELIBERADA do narrador/player (com o filtro R1 ele nem
        # aparece no contexto fora do seu local, então não há reuso passivo). Logo,
        # se ele foi trazido para OUTRO local (viajou junto, mandado em missão),
        # RELOCALIZA — o home_location_id passa a ser o local atual.
        new_npcs = dict(npcs)
        if isinstance(new_npcs.get(canonical), dict):
            atual = new_npcs[canonical]
            new_npcs[canonical] = {
                **atual,
                "in_scene": True,
                "last_seen_turn": turn,
                "home_location_id": home_id or atual.get("home_location_id", ""),
            }
        return new_npcs
    tpl = None
    pool_entry = _cast_match(cast, new_name)
    if pool_entry is not None:
        # SPEC-297 R23: elenco do pool = cópia da base, SEM chamada de LLM.
        from observability.telemetry import log_event
        from services import shared_pool

        tpl = shared_pool.materialize_npc(pool_entry, game_id=game_id, home_location_id=home_id)
        if pool_used_out is not None:
            pool_used_out.append(pool_entry.entry_id)
        log_event("pool", "cast_used", entry_id=pool_entry.entry_id)
    elif _pool_enabled():
        # R7: com o pool ligado a cena narrada NÃO entra no prompt de geração.
        tpl = generate_new_npc(
            new_name,
            context=f"Local: {loc}",
            game_id=game_id,
            location_id=home_id,
            # P1-3: nome que o jogador digitou e o narrador devolveu continua "player".
            name_origin=("player" if _typed_by_player(new_name, player_inputs) else "narrator"),
            turn=turn,
            player_inputs=player_inputs,
        )
    else:
        tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl:
        return npcs
    # O librarian/cache pode resolver uma referência técnica para uma ficha já
    # presente (ex.: npc_skriit_mil_olhos -> Skriit Mil-olhos). Revalida APÓS
    # a fábrica para não inserir o mesmo id sob uma segunda chave.
    canonical = find_runtime_npc_key(npcs, new_name, tpl)
    if canonical is not None:
        new_npcs = dict(npcs)
        atual = dict(new_npcs[canonical])
        new_npcs[canonical] = {
            **atual,
            "in_scene": True,
            "last_seen_turn": turn,
            "home_location_id": home_id or atual.get("home_location_id", ""),
        }
        return new_npcs
    new_npcs = dict(npcs)
    # A fábrica já devolve a ficha v4 materializada. Ela é a fonte da verdade:
    # recompor aqui apenas os campos antigos apagava Virtudes, Vitalidade,
    # Ferimentos e o perfil tático persistido.
    novo = dict(tpl)
    novo.setdefault("name", new_name)
    novo.setdefault("role", "Desconhecido")
    novo.setdefault("persona", "")
    novo["location"] = loc
    novo.setdefault("relationship", tpl.get("initial_relationship", 5))
    novo.setdefault("memory", [])
    novo.setdefault("last_interaction", "")
    novo.setdefault("attributes", {})
    novo.setdefault("combat_stats", {})
    # spec encontros-dedupe (R1/R2): vínculo de local + turnos p/ cooldown/invariante.
    novo.setdefault("created_turn", turn)
    novo["last_seen_turn"] = turn
    # spec npcs-3-camadas: quem a cena introduziu está EM cena e é conhecido.
    novo = npc_layers.ensure_npc_fields(novo, game_id, home_location_id=home_id, in_scene=True)
    new_npcs[str(novo.get("name") or new_name)] = novo
    return new_npcs


def _engine_owns_factions() -> bool:
    """SPEC-302 R21b: no modo `on` o progresso das facções roda no tick diário."""
    from services import world_engine

    return world_engine.mode() == "on"


def _perception_state(state, world: dict, factions: list, intel: dict) -> dict:
    return {**state, "world": world, "factions": factions, "faction_intel": intel}


def _perceive_world(state, world: dict, factions: list, intel: dict, tick):
    """SPEC-302 R23/R25: filtra o digest pelo que o herói viu/ouviu, grava o TEXTO DO
    TEMPLATE em `world.news` e devolve (world, itens percebidos). Só no modo `on`."""
    if tick.sim_key != "world_sim" or not tick.days_ticked or tick.world_sim is None:
        return world, []
    try:
        from services import world_perception as wperc

        sim = tick.world_sim
        pst = _perception_state(state, world, factions, intel)
        items = list(sim.get("pending_digest") or [])
        seen = wperc.perceivable(pst, items)
        world = wperc.record_news(world, pst, seen)
        done = {i["item_id"] for i in seen}
        stats = dict(sim.get("perceived_stats") or {})
        stats["items"] = int(stats.get("items", 0)) + len(seen)
        stats["signals"] = int(stats.get("signals", 0)) + sum(
            1 for i in seen if i["kind"] == "sinal"
        )
        stats["crises"] = int(stats.get("crises", 0)) + sum(1 for i in seen if i["kind"] == "crise")
        sim["perceived_stats"] = stats
        day = int((world.get("world_clock") or {}).get("day", 1) or 1)
        # so rumores (com subject_id) esperam propagacao; o resto e testemunho do dia
        sim["pending_digest"] = [
            i
            for i in items
            if i["item_id"] not in done
            and i.get("subject_id")
            and day - int(i.get("day", day)) <= 10
        ]
        return world, seen
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_perception_failed", exc)
        return world, []


def _narrate_world(state, world: dict, factions: list, intel: dict, perceived: list) -> str:
    """SPEC-302 R26: no máximo 1 chamada por ação; só com itens percebidos."""
    if not perceived:
        return ""
    from agents.world_simulator import narrate_day

    text = narrate_day(_perception_state(state, world, factions, intel), perceived)
    return f"[ECOS DO MUNDO] {text}" if text else ""


def _world_tick(state, world_before: dict, world: dict, factions: list, intel: dict):
    """SPEC-302 R1: 1 tick por dia virado após viagem/descanso. Nunca levanta: falha do
    motor não derruba o turno (devolve o mundo/facções como estavam e tick=None)."""
    try:
        from services import world_engine

        tick = world_engine.advance_days(state, world_before, world, factions, intel)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_tick_failed", exc)
        return world, factions, None
    new_world = tick.world
    if tick.sim_key == "world_sim":
        # SPEC-302 (revisão P2-1): o decaimento de perigo (SPEC-233 R2) nao depende do pulso.
        from world_utils import decay_danger_overrides

        new_world = decay_danger_overrides(dict(new_world))
    return new_world, tick.factions, tick


def storyteller_node(state: GameState):
    messages = state.get("messages", [])
    if not messages:
        return {"messages": [AIMessage(content="Comece a história.")]}

    last_user_input = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    from services.actor_lifecycle import is_recovery_turn

    recovery_turn = is_recovery_turn(state)
    if recovery_turn:
        # Recovery is passage of time/treatment, never permission for another action.
        last_user_input = "Descanso e aguardo socorro."
    world = ensure_world(state.get("world", {}))

    # --- Fase 0: viagem / descanso (determinístico) ---
    # --- Fase 2: o tempo que passa avança as fações off-screen (mundo vivo) ---
    travel_note = rest_note = faction_note = ""
    rested_player = None
    # SPEC-226 R10: ganhos individuais do turno (guard narrativo aceita o bruto).
    from services.turn_outcome import record_gain

    turn_bl = state.get("turn_baseline")
    factions = ensure_factions(state.get("factions"))
    intel = ensure_faction_intel(state.get("faction_intel"))
    travel_intent = bool(last_user_input and is_travel_intent(str(last_user_input), world))
    dest = find_travel_destination(world, last_user_input) if travel_intent else None
    if travel_intent and not dest:
        try:
            from world_utils import invalid_travel_message

            refusal = invalid_travel_message(world, str(last_user_input))
        except (ImportError, AttributeError):
            refusal = ""
        if refusal:
            from services.intent_guard import log_intent_guard

            log_intent_guard("travel_refused", "no_route", str(last_user_input))
            # Recusa canônica antes da LLM: destino impossível nunca aparece como
            # chegada na mensagem, no resumo nem na memória.
            return {
                "messages": [AIMessage(content=refusal)],
                "world": world,
                "archive_due": False,
            }
    travel_periods = 0
    world_before = world  # SPEC-302: relogio ANTES de viagem/descanso (dias virados)
    world_tick = None
    sim_updates: dict = {}
    discovery_events: list = []
    reward_player_before = deepcopy(state.get("player") or {})
    discovery_player = None
    if dest:
        from world_utils import travel_cost

        travel_periods = travel_cost(world, dest)  # custo ANTES de mover (usa origem)
        # spec loot-exploracao (R1): fog of war checado ANTES de apply_travel (que
        # carimba `visited`). Baú curado (R3) pode reconceder-se? Não — one-shot.
        first_visit = dest["id"] not in (world.get("visited") or [])
        world = apply_travel(world, dest)
        world, factions, world_tick = _world_tick(state, world_before, world, factions, intel)
        if not _engine_owns_factions():
            factions, faction_events = advance_factions(factions, travel_periods)
            factions, world, faction_note = resolve_faction_completions(
                factions, world, faction_events, intel
            )
        # spec loot-exploracao: achado ambiental (1ª visita) OU baú curado (sempre
        # que houver e não saqueado). Muta player.inventory/gold + world in-place
        # (propaga: viagem sem descanso não substitui o player no updates parcial).
        _pl = deepcopy(state.get("player"))
        if isinstance(_pl, dict) and (first_visit or (dest.get("treasure"))):
            from services import exploration

            _rng = exploration.arrival_rng(
                str(state.get("game_id", "")), dest["id"], int(world.get("turn_count", 0) or 0)
            )
            disc_note, discovery_events = exploration.discover_on_arrival(
                _pl,
                world,
                dest,
                int(_pl.get("level", 1) or 1),
                _rng,
                projection=state.get("world_projection"),
                first_visit=first_visit,
            )
            if disc_note:
                faction_note = (faction_note + " " + disc_note).strip()
            discovery_player = _pl
            turn_bl = record_gain(
                turn_bl,
                "gold",
                int(_pl.get("gold", 0) or 0) - int((state.get("player") or {}).get("gold", 0) or 0),
                "exploration",
            )
        if travel_periods == 0:
            travel_note = (
                f"O jogador ENTROU em {dest['name']} (mesma cidade — o tempo não passou). "
                f"Contexto do local: {dest.get('lore_seed', '')} Descreva o que ele vê ao entrar."
            )
        else:
            travel_note = (
                f"O jogador VIAJOU para {dest['name']}"
                + (f" (viagem longa: {travel_periods} períodos). " if travel_periods > 1 else ". ")
                + f"Contexto do local: {dest.get('lore_seed', '')} Descreva a chegada e o que ele vê agora."
            )
    elif last_user_input and is_rest(last_user_input):
        from world_utils import weather_effects

        rest_blocked = weather_effects(world).get("rest_block", False)  # Fase 6.5
        # spec refatoracao-sistema-classes (R6): aliado ativo mitiga a Insônia do Devoto.
        import party as _party_mod

        _rest_allies = _party_mod.active_allies(state)
        rested_player, world = apply_rest(dict(state.get("player", {})), world, allies=_rest_allies)
        # SPEC-233 R7: fações avançam pelo delta REAL do relógio (bloqueado = 1 período).
        world, factions, world_tick = _world_tick(state, world_before, world, factions, intel)
        if not _engine_owns_factions():
            factions, faction_events = advance_factions(factions, 1 if rest_blocked else 2)
            factions, world, faction_note = resolve_faction_completions(
                factions, world, faction_events, intel
            )
        if rest_blocked:
            rest_note = (
                f"O jogador TENTOU descansar, mas o clima ({world.get('weather', 'o miasma')}) "
                f"NÃO permite descanso seguro ao relento — NADA foi recuperado e o tempo passou "
                f"({clock_label(world)}). Narre a noite péssima e a exaustão."
            )
        else:
            rest_note = (
                f"O jogador DESCANSOU. O tempo avançou para {clock_label(world)} e ele recuperou parte das forças. "
                "Narre a passagem do tempo e o estado do mundo ao acordar."
            )
    perceived_items: list = []
    if world_tick is not None:
        if world_tick.world_sim is not None:
            sim_updates[world_tick.sim_key] = world_tick.world_sim
            world, perceived_items = _perceive_world(state, world, factions, intel, world_tick)
        extra_engine_events_tick = list(world_tick.pending_events)
    else:
        extra_engine_events_tick = []
    # Viagem fecha a cena anterior antes de qualquer encontro ou contexto. Isso
    # também protege retornos antecipados de combate contra NPCs teleportados.
    from services import npc_layers

    scene_npcs = npc_layers.reset_scene(state.get("npcs", {})) if dest else state.get("npcs", {})
    scene_state = {**state, "world": world, "npcs": scene_npcs}
    travel_needs_replan = bool(state.get("needs_replan"))
    if dest:
        from agents.campaign_manager import _same_region

        planned_location = str((state.get("campaign_plan") or {}).get("location") or "")
        if planned_location and not _same_region(
            planned_location,
            str(world.get("current_location") or ""),
        ):
            travel_needs_replan = True

    # (Ação livre: o gating é feito pelo PRÓPRIO narrador no prompt — sem chamada extra ao Ruler.)

    # --- O tempo passou (viagem/descanso): ou cai em encontro, ou o mundo "respira" ---
    world_note = ""
    extra_engine_events: list = list(extra_engine_events_tick)
    track_bk = None  # Fase 6.4: rastro atualiza o Codex do jogador
    # spec mapa-sublocais (R2): custo 0 (intra-cidade/interior) não rola encontro
    if (dest and travel_periods >= 1) or rested_player is not None:
        turn = int(world.get("turn_count", 0))
        # R5 (fix-playtest-achados): a FORÇA do encontro escala pelo nível (apex não).
        _plevel = int((state.get("player") or {}).get("level", 1) or 1)
        from gamedata import get_location as _get_location
        from world_utils import effective_danger, recovery_rest_safe

        danger_now = effective_danger(world)  # SPEC-233 R1
        # spec letalidade-early-game-v2 (alavanca 1): um DESCANSO de early-game em
        # zona não-apex de perigo baixo recupera SEM sortear encontro — o laço de
        # recuperação que faltava (viagem não cura; descanso interrompido = morte).
        # Só vale pra REST (rested_player is not None), nunca pra viagem.
        _rest_recovers = rested_player is not None and recovery_rest_safe(
            _plevel, danger_now, _get_location(world.get("current_location_id", "")) or {}
        )
        if _rest_recovers:
            enc = None
        else:
            # Fase 6.3: sorteio ponderado — pressão de caça/fação/migração
            _law_hint = _law_mod.hunter_encounter(
                {**state, "world": world},
                str(world.get("current_location_id") or ""),
                _law_mod.clock_of({**state, "world": world}),
            )
            enc = check_encounter(
                world,
                factions,
                intel,
                turn,
                bestiary_knowledge=state.get("bestiary_knowledge"),
                projection=state.get("world_projection"),
                player_level=_plevel,
                law_hint=_law_hint,
            )
        # spec encontros-dedupe (R3): não repete o MESMO template de encontro 2x
        # seguidas no mesmo local (o mundo não é um carrossel).
        enc = _dedupe_encounter(enc, world)  # SPEC-233 R6
        if not enc:
            world.pop("encounter_eff_danger", None)  # SPEC-233 R5
        if enc:
            world["last_encounter_turn"] = turn
            world["last_encounter_id"] = enc.get("hint")
            world["last_encounter_loc"] = world.get("current_location_id")
            danger = effective_danger(world)
            base_p = (
                rested_player
                if rested_player is not None
                else dict(discovery_player or state.get("player") or {})
            )

            # Fase 6.4 (R1): percepção decide surpresa; (R2): nem todo perigo é combate.
            # Reforço/fação dominante SEMPRE é combate (eles vieram POR você).
            from world_utils import (
                detection_check,
                light_level,
                resolve_track,
                resolve_trap,
                roll_encounter_type,
                weather_effects,
            )

            # Fase 6.5: neblina/vendaval atrapalham a percepção.
            # spec itens-vivos-e-luz (R3): escuridão sem luz também penaliza.
            _perc_mod = weather_effects(world).get("perception_mod", 0) + light_level(
                world, base_p
            ).get("perception_mod", 0)
            det = detection_check(base_p, danger, perception_mod=_perc_mod)
            kind = (
                "combat"
                if enc.get("reason") in ("reinforcements", "controlled", "bounty_hunters")
                else roll_encounter_type(danger)
            )

            if kind == "combat":
                from services.combat_origin import from_encounter

                # surpresa: percebeu -> herói embosca; falhou -> inimigo age antes
                world["encounter_surprise"] = "player" if det["perceived"] else "enemy"
                # R5: percebeu = tem AGÊNCIA — pode golpear OU recuar (a fuga já é
                # mecânica no combate: "fujo/corro/recuo"). Surpreendido = sem saída.
                sur_txt = (
                    "Você os percebe ANTES — há tempo de golpear primeiro OU RECUAR "
                    "(diga que foge/corre/recua para escapar)."
                    if det["perceived"]
                    else "Eles saem do nada — você é pego de surpresa, sem chance de recuar."
                )
                updates = {
                    "messages": [SystemMessage(content=f"COMBAT START. {enc['flavor']} {sur_txt}")],
                    "world": world,
                    "factions": factions,
                    "combat_target": enc["hint"],
                    "combat_encounter_hint": encounter_handoff(enc),
                    "combat_origin_hint": from_encounter(
                        enc,
                        world,
                        trigger=("rest" if rested_player is not None else "travel"),
                    ),
                    "next": "combat_agent",
                    "archive_due": True,  # emboscada = evento relevante
                    "npcs": scene_npcs,
                    "needs_replan": travel_needs_replan,
                }
                if enc.get("reason") == "bounty_hunters":
                    updates.update(
                        _law_mod.mark_hunters(
                            state,
                            str(enc.get("jurisdiction_id") or ""),
                            _law_mod.clock_of({**state, "world": world}),
                        )
                    )
                if rested_player is not None:
                    updates["player"] = rested_player  # já curou no descanso antes da emboscada
                elif discovery_player is not None:
                    updates["player"] = discovery_player
                # spec loot-exploracao: claim de único do baú curado não se perde
                # se um encontro disparar na mesma chegada.
                if turn_bl is not state.get("turn_baseline"):
                    updates["turn_baseline"] = turn_bl
                updates.update(sim_updates)
                if discovery_events or extra_engine_events:
                    updates["pending_world_events"] = (
                        (state.get("pending_world_events", []) or [])
                        + discovery_events
                        + list(extra_engine_events)
                    )
                # Fase 3.2 (R3): criatura nomeada no hint ANTES do combate = rumor.
                enemy_id = enc.get("enemy_id")
                if enemy_id:
                    updates["bestiary_knowledge"] = disc.record_rumor(
                        state.get("bestiary_knowledge", {}), enemy_id, turn
                    )
                return updates

            from gamedata import get_location

            loc_node = get_location(world.get("current_location_id", "")) or {}
            world.pop("encounter_eff_danger", None)  # SPEC-233 R5: não-combate
            if kind == "trap":
                from party import active_allies

                helper = next(iter(active_allies(state)), None)
                new_p, trap_logs, info = resolve_trap(
                    base_p,
                    loc_node,
                    danger,
                    helper=helper,
                )
                rested_player = new_p  # reusa o encanamento de player existente
                turn_bl = record_gain(
                    turn_bl,
                    "xp",
                    int(new_p.get("xp", 0) or 0) - int(base_p.get("xp", 0) or 0),
                    "exploration",
                )
                world_note = (
                    "ENCONTRO NA ESTRADA (armadilha — números JÁ resolvidos, narre-os):\n"
                    + "\n".join(trap_logs)
                )
                if info:
                    extra_engine_events += info.get("level_up_events", [])
            elif kind == "track":
                track_bk, note, hint = resolve_track(
                    state.get("bestiary_knowledge", {}), loc_node, danger, turn
                )
                if hint:
                    world["treasure_hint"] = True
                world_note = f"ENCONTRO NA ESTRADA (rastro): {note}"
            else:  # social
                world_note = (
                    "ENCONTRO NA ESTRADA (social): um grupo HOSTIL-MAS-NEGOCIÁVEL aborda o "
                    "jogador (ligado ao perigo local). Narre a abordagem tensa SEM iniciar "
                    "combate — eles querem algo (pedágio, informação, escolta). Se surgir um "
                    "porta-voz, registre-o em introduced_npcs."
                )
        # Sem emboscada: o mundo gera 1 evento off-screen narrado (e grava no RAG da sessão).
        try:
            if _engine_owns_factions():
                # modo on: a narracao diaria substitui o pulso (SPEC-302 R26); so se o dia
                # virou e algo foi percebido (0 chamadas caso contrario)
                world_note = world_note or _narrate_world(
                    state, world, factions, intel, perceived_items
                )
            else:
                world, world_note = simulate_world(state, world, factions, intel, 1 if dest else 2)
                if world_note.startswith("[ECOS DO MUNDO]"):
                    # SPEC-296 R6: rumor percebido persiste ("Ouvi dizer").
                    from services.ambient import append_news

                    world = append_news(
                        world,
                        text=world_note[len("[ECOS DO MUNDO]") :].strip(),
                        location_id=world.get("current_location_id", ""),
                        location_name=world.get("current_location", ""),
                        turn=int(world.get("turn_count", 0) or 0),
                    )
        except Exception as exc:
            from observability.telemetry import log_fallback

            log_fallback("storyteller", "world_pulse_failed", exc)
            world_note = ""

    loc = world.get("current_location", "")
    # spec encontros-dedupe (R1): só NPCs vinculados ao local/em cena/party —
    # NPC gerado em outro lugar não é reciclado nesta cena.
    from services.npc_layers import npcs_for_context

    scene_state = {**scene_state, "world": world}
    existing_npcs = npcs_for_context(scene_state)

    # --- Contexto Híbrido ---
    game_id = state.get("game_id")
    # --- Fase 2.8: contexto centralizado (estado dinâmico + lore + memória, com budget) ---
    # ESTADO ATUAL entra ANTES da lore base: a verdade viva vence o canônico.
    pack = build_context_pack(
        scene_state, query=f"{loc} {last_user_input}", purpose="story", game_id=game_id
    )
    lore_context = pack.lore_block or "Dark Fantasy Genérica."
    memoria_recente = pack.memory_block or "Sem memória recente dentro do budget deste turno."
    # spec arvores-habilidade-classes (§3.3): utilitárias conhecidas — gate
    # determinístico; a LLM só narra o que a ficha PERMITE.
    from services.context_builder import utility_context_block

    capacidades_block = utility_context_block(state.get("player", {}) or {})

    # SPEC-296 R4/R5: bloco de ambiente único (período, clima local/global, luz,
    # perigo, abrigo e saídas) — substitui luz_block/clima_block.
    from services.ambient import ambient_block, heard_block
    from world_utils import weather_effects as _weather_effects

    ambiente_block = ambient_block(world, state.get("player", {}) or {}, audience="story")
    ouviu_block = heard_block(world)
    from world_utils import light_level as _light_level

    _ll = _light_level(world, state.get("player", {}) or {})
    weather_note = ""
    if world.get("weather_global"):
        weather_note = (
            f"Fenômeno global ativo: {_weather_effects(world).get('label', 'clima anômalo')}. "
            "Ele domina o céu e afeta toda a cena."
        )

    campaign_plan = state.get("campaign_plan") or {}
    beats = [dict(beat) for beat in campaign_plan.get("beats", [])]
    current_step = campaign_plan.get("current_step", 0)
    beat_eligible = (
        isinstance(current_step, int)
        and not isinstance(current_step, bool)
        and 0 <= current_step < len(beats)
        and beats[current_step].get("status", "pending") in {"pending", "active"}
    )
    active_step = (
        beats[current_step].get("description") if beat_eligible else "Clímax ou Ação Livre."
    )

    llm = get_llm(temperature=0.7)

    # PROMPT ATUALIZADO
    eventos_turno = (
        "\n".join(n for n in (travel_note, rest_note, faction_note, world_note) if n)
        or "Nenhum evento especial."
    )

    # Fações que o JOGADOR conhece (não-onisciência): só estas podem ser citadas/afetadas.
    faccoes_conhecidas = (
        "\n".join(
            f"- id={f.get('id')} · {f.get('name')} ({f.get('region', '')}) · disposição={f.get('disposition', 'neutro')}"
            for f in factions
            if intel.get(f.get("id"), {}).get("known") and not f.get("defeated")
        )
        or "Nenhuma fação conhecida pelo jogador ainda."
    )

    # Fase 2.6: ids canônicos que o LLM pode usar em proposed_events (defesa em profundidade).
    entidades_canonicas = _scene_canonical_entities(scene_state, factions, intel, loc)
    # Fase 3.3: quests ativas que o LLM pode concluir via proposed_events(quest_completed).
    quests_ativas = _quests_ativas_block(state.get("quests", []), {**state, "world": world})

    # spec npc-fallback-sem-alvo (R2): rota NPC sem interlocutor delegou aqui.
    npc_fallback_clause = _npc_fallback_clause(scene_state)
    # SPEC-202 R2/R7/R11: mediação do narrador (dados públicos do sujeito).
    npc_fallback_clause += _mediation_clause(scene_state)
    # spec polish-prosa: R1 (varie a abertura) + R3 (menu de opções concretas).
    from services import prose_guard

    _aberturas = prose_guard.ultimas_aberturas(messages)
    varie_clause = prose_guard.openings_clause(_aberturas)
    opcoes_clause = (
        "\n    - FECHE com 2 a 3 OPÇÕES concretas de ação, cada uma numa "
        "linha iniciada por '— ', e termine com '— Ou outra ação.' "
        "(dê rumo ao jogador; as opções mecânicas de combate vêm à parte)."
    )
    _hero = state.get("player", {}) or {}
    hero_state_block = (
        "<ESTADO_DO_HEROI>\n"
        f"Nível: {int(_hero.get('level', 1) or 1)} · "
        f"Vitalidade: {int(_hero.get('vitalidade', _hero.get('hp', 0)) or 0)}/"
        f"{int(_hero.get('max_vitalidade', _hero.get('max_hp', 0)) or 0)} · "
        f"Ouro: {int(_hero.get('gold', 0) or 0)}\n"
        "Se mencionar o saldo do herói, use EXATAMENTE esse Ouro.\n"
        "</ESTADO_DO_HEROI>"
    )

    # SPEC-298 R25: fama do local atual (rótulo, nunca número) — só se o jogador é conhecido ali.
    from services.reputation import fame_line

    _fame = fame_line(state)
    fame_block = f"<FAMA_LOCAL>\n{_fame}\n</FAMA_LOCAL>" if _fame else ""

    # SPEC-297 R22: elenco oferecido ao NARRADOR (não ao jogador); vazio salvo flag `on`.
    try:
        from services import shared_pool

        _cast = shared_pool.cast_entries(state)
        cast_block_text = shared_pool.cast_block_text(_cast)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "pool_cast_failed", exc)
        _cast, cast_block_text = [], ""

    # SPEC-300: companheiros com alma (fala espontânea sem chamada LLM extra).
    try:
        from services.companion_prompt import companion_prompt_block

        companion_block, companion_ack = companion_prompt_block(state, "story")
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "companion_block_failed", exc)
        companion_block, companion_ack = "", []

    # SPEC-299 R9/R16/R19: fato de cena da lei (patrulha, confronto, sinais). Sem nada a
    # dizer o bloco nem existe (zero token). Nunca heat/bounty/nível (R17).
    _law_text, _law_scene_updates = _law_mod.scene_block(state)
    lei_block = _law_text
    if _law_mod.crime_hint_enabled(state):
        lei_block = "\n".join(p for p in (lei_block, _law_mod.CRIME_CLAIM_HINT) if p)

    sys = SystemMessage(
        content=f"""
    <PERSONA>
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    Momento: {clock_label(world)}.
    NPCs na cena: {existing_npcs}.
    Objetivo Atual: {active_step}
    </PERSONA>

    <EVENTOS_DESTE_TURNO>
    {eventos_turno}
    </EVENTOS_DESTE_TURNO>
    {ambiente_block}
    {ouviu_block}
    {hero_state_block}
    {companion_block}
    {fame_block}
    {lei_block}

    <FACÇÕES_CONHECIDAS>
    {faccoes_conhecidas}
    Se a ação do jogador NESTE turno claramente ajudar ou prejudicar uma destas fações,
    registre em 'faction_impacts' (faction_id EXATO + direction 'ajudou'/'prejudicou' + magnitude 'menor'/'maior').
    Caso contrário, deixe 'faction_impacts' vazio. NÃO invente ids fora da lista.
    </FACÇÕES_CONHECIDAS>

    <ENTIDADES_CANONICAS>
    {entidades_canonicas}
    Se — e SÓ se — a ação deste turno causou mudança PERSISTENTE no mundo (morte de
    personagem NOMEADO, segredo revelado, mudança de controle de local), registre em
    'proposed_events' usando os ids EXATOS acima. Na dúvida, deixe vazio. NUNCA invente
    ids fora desta lista.
    </ENTIDADES_CANONICAS>

    <QUESTS_ATIVAS>
    {quests_ativas}
    Se um personagem PRESENTE NA CENA ofereceu uma missão concreta ao jogador NESTE
    turno, registre em 'proposed_quests' (origem = quem pediu; location_id só se o
    destino é claro). Se a ação deste turno CONCLUIU uma das quests listadas acima
    COM "prova: ok", proponha em 'proposed_events' um evento type='quest_completed'
    com target_id=quest_id e payload={{"quest_id": quest_id}} usando o id EXATO.
    Quest com "prova: pendente" NÃO pode ser concluída (o motor rejeita): falta ir
    ao local e investigar, ou voltar a quem pediu. Na dúvida, deixe vazio. NUNCA
    invente ids.
    </QUESTS_ATIVAS>

    {capacidades_block}

    {cast_block_text}{pack.world_state_block}
    (Se o ESTADO ATUAL DO MUNDO acima contradisser o lore/fatos passados abaixo, o ESTADO ATUAL VENCE.)

    <MEMORIA_RECENTE>
    Resumo dos fatos anteriores: {memoria_recente}
    </MEMORIA_RECENTE>

    <LORE_PUBLICO_CANONICO>
    {lore_context}
    </LORE_PUBLICO_CANONICO>

    <INSTRUÇÕES>
    - Responda em 2 a 3 parágrafos.
    - JULGUE a ação: se for implausível para a classe/ficha do personagem ({state.get("player", {}).get("class_name", "")})
      ou impossível no contexto, faça-a FALHAR de forma crível na narração (não conceda o impossível).
    - Não afirme como cânone nome, item, facção, local ou evento ausente do ESTADO,
      da MEMÓRIA ou do LORE PÚBLICO acima. Quando faltar base, descreva incerteza
      ou admita que o personagem não sabe; não preencha a lacuna com fato novo.
    - Termine com opções ou pergunta para ação.
    - Se um personagem ENTRAR na cena (novo ou conhecido que reapareceu), adicione o nome em 'introduced_npcs'.
    - Se um personagem conhecido SAIR da cena (foi embora, sumiu), adicione o nome em 'npcs_left_scene'.{npc_fallback_clause}{varie_clause}{opcoes_clause}
    - {PLAYER_INPUT_RULE}
    """
    )

    # SPEC-233 R8: ganhos registrados ANTES da LLM (o except não herda XP de beat
    # que só seria aplicado no caminho feliz).
    turn_bl_pre_llm = turn_bl
    companion_narrated = False  # SPEC-300 R13: o ack só vale no caminho feliz
    try:
        story_engine = llm.with_structured_output(StoryUpdate)
        # SPEC-223 R5: entrada do jogador delimitada como dado.
        update = story_engine.invoke([sys] + guard_messages(messages[-3:]))

        # Guard crítico: FallbackLLM devolve AIMessage, não o schema solicitado.
        companion_narrated = isinstance(update, StoryUpdate)
        if not isinstance(update, StoryUpdate):
            from observability.telemetry import log_fallback

            log_fallback("storyteller", "structured_invalid")
            update = StoryUpdate(
                narrative=_deterministic_story_fallback(
                    (travel_note, rest_note, world_note, faction_note, weather_note),
                    _ll,
                )
            )

        narrative_text = update.narrative
        # Pré-validação read-only das propostas da própria LLM. O processor no
        # archivist continua sendo o único escritor, mas a mensagem visível não
        # pode afirmar como fato uma mudança que ele rejeitará logo depois.
        from services.event_processor import prevalidate_event_batch

        llm_event_proposals = [
            event.model_dump() if hasattr(event, "model_dump") else dict(event)
            for event in (getattr(update, "proposed_events", []) or [])
        ]
        invalid_story_events = []
        # SPEC-223 (revisão Sol): a pré-validação usa as quests ANTES do progresso
        # deste turno, de propósito: a mesma mensagem que pede a conclusão não pode
        # ser também a sua prova ("Investigo… e marque a missão como concluída").
        # Custo: conclusão proposta no mesmo turno da 1ª evidência vai para
        # quarentena; no turno seguinte passa (medido real: 0/30 turnos).
        preview_state = {
            **state,
            "world": world,
            "event_log": list(state.get("event_log") or []),
        }
        validations = prevalidate_event_batch(llm_event_proposals, preview_state)
        for proposal, validation in zip(llm_event_proposals, validations):
            if not validation.ok:
                invalid_story_events.append(
                    {
                        "type": str(proposal.get("type") or ""),
                        "target_id": str(proposal.get("target_id") or ""),
                        "reason": str(validation.reason or "")[:240],
                    }
                )
        # Política atômica/conservadora: uma proposta inválida põe em quarentena
        # TODO o payload livre da mesma resposta. Mantemos apenas as propostas
        # inválidas na fila para auditoria; propostas irmãs aparentemente válidas
        # não podem virar mudanças silenciosas depois que a narrativa foi descartada.
        quarantine_llm_payload = bool(invalid_story_events)
        pending_llm_events = (
            [
                {
                    "type": rejected["type"],
                    "target_id": rejected["target_id"],
                    "actor_id": "player",
                    "payload": {},
                    "source": "storyteller_prevalidation",
                    "_prevalidation_rejected": True,
                    "_prevalidation_reason": rejected["reason"],
                }
                for rejected in invalid_story_events
            ]
            if quarantine_llm_payload
            else llm_event_proposals
        )
        if not str(narrative_text).strip():
            # Fallback digno: o TURNO MECÂNICO sobrevive mesmo com LLM flaky —
            # as notas determinísticas (viagem/descanso/encontro) viram a narração.
            narrative_text = _deterministic_story_fallback(
                (travel_note, rest_note, world_note, faction_note, weather_note),
                _ll,
            )
        narrative_text = prose_guard.sanitize_player_facing(str(narrative_text))
        narrative_text = prose_guard.reconcile_player_gold_claims(
            narrative_text, int((state.get("player") or {}).get("gold", 0) or 0)
        )
        if invalid_story_events:
            # Não há fact-check semântico confiável frase a frase. Em vez de
            # deixar a alegação rejeitada sobreviver, usa somente consequências
            # determinísticas já aplicadas neste turno.
            safe_parts = [note for note in (travel_note, rest_note, faction_note) if note]
            narrative_text = (
                _deterministic_story_fallback(safe_parts, _ll)
                if safe_parts
                else (
                    "A tentativa altera apenas o momento imediato; nenhuma mudança "
                    "permanente no mundo foi confirmada."
                )
            )
            narrative_text += (
                "\n\n[SISTEMA] Uma mudança permanente proposta pela narração "
                "foi rejeitada pelo estado canônico."
            )

        narrative_text = prose_guard.vary_repeated_opening(
            str(narrative_text),
            _aberturas,
            salt=(f"{state.get('game_id', '')}:{(world or {}).get('turn_count', 0)}:storyteller"),
        )

        # SPEC-202 R11: narração mediada não revela segredo não revelado.
        narrative_text, mediation_rejections = _guard_mediation_secret(
            str(narrative_text), scene_state
        )

        # spec polish-prosa (R4): telemetria de abertura repetida (não re-tenta).
        prose_guard.log_if_repeats(
            str(narrative_text), _aberturas[0] if _aberturas else "", where="storyteller"
        )

        # --- SPEC-298 R11: a ação do jogador NÃO altera mais a reputação aqui. O storyteller
        # só enfileira propostas `faction_deed`; o validador exige a fação em cena e o
        # processador (services.reputation) aplica com delta tabelado — ou guarda como
        # pendência até a fação saber (regra de ouro).
        rep_events = []
        faction_impacts = (
            [] if quarantine_llm_payload else (getattr(update, "faction_impacts", []) or [])
        )
        # SPEC-226 R8: 1 impacto por facção/turno (último vence).
        _by_fid: dict = {}
        for imp in faction_impacts:
            _by_fid[getattr(imp, "faction_id", "")] = imp
        for imp in _by_fid.values():
            fid = getattr(imp, "faction_id", "")
            if not fid:
                continue
            rep_events.append(
                {
                    "type": "faction_deed",
                    "actor_id": "player",
                    "target_id": fid,
                    "payload": {
                        "direction": getattr(imp, "direction", ""),
                        "magnitude": getattr(imp, "magnitude", "menor"),
                        "location_id": (world or {}).get("current_location_id", ""),
                    },
                    "source": "storyteller",
                }
            )

        # --- SPEC-299 R4(a)/R6/R7: crimes classificados pelo LLM; o motor valida e registra.
        # Guard de FallbackLLM: `update` não-StoryUpdate já caiu no except acima (sem claim).
        law_updates: dict = {}
        try:
            law_updates = _law_mod.apply_claims(
                {**state, **_law_scene_updates, "world": world, "npcs": scene_npcs},
                getattr(update, "crime_claims", []) or [],
                player_text=str(last_user_input or ""),
                quarantine=bool(quarantine_llm_payload),
            )
        except Exception as exc:  # silent-ok: lei nunca derruba o turno
            _log_event("law", "claims_failed", level="warning", error=type(exc).__name__)

        # --- Avanço de beat: o narrador sinaliza quando o objetivo da cena foi cumprido ---
        needs_replan = travel_needs_replan
        updated_plan = campaign_plan
        beat_done = (
            bool(getattr(update, "beat_completed", False))
            and not quarantine_llm_payload
            and beat_eligible
        )
        # Fase 4.1: beat concluído = XP determinístico (o LLM só sinaliza o beat;
        # valor/level up são do motor). Level ups viram eventos source="progression".
        leveled_player = None
        level_up_events: list = []
        # Cena de abertura roda com turn_count==1 (campaign_manager incrementa antes):
        # narrador generoso marcando beat no prólogo não pode virar XP grátis na
        # criação (achado do smoke real 2026-07-05). XP de beat só do turno 2 em diante.
        if beat_done and int(world.get("turn_count", 0) or 0) > 1:
            from progression import XP_PER_BEAT, grant_xp

            # SPEC-226 R3: compõe sobre o jogador já atualizado (descanso/achado).
            base_p = (
                rested_player
                if rested_player is not None
                else discovery_player
                if discovery_player is not None
                else dict(state.get("player") or {})
            )
            leveled_player, level_up_events = grant_xp(base_p, XP_PER_BEAT)
            turn_bl = record_gain(turn_bl, "xp", XP_PER_BEAT, "beat")
        if beat_done:
            beats[current_step] = {**beats[current_step], "status": "done"}
            new_step = current_step + 1
            updated_plan = {**campaign_plan, "beats": beats, "current_step": new_step}
            # Esgotou os beats → próximo turno o campaign_manager replaneja (vê _should_replan).
            if new_step >= len(beats):
                needs_replan = True

        # spec npcs-3-camadas (R5): viagem zera a cena (ninguém teleporta junto);
        # introduced_npcs entram em cena; npcs_left_scene saem.
        new_npcs = scene_npcs
        home_id = world.get("current_location_id", "")
        _turn = int(world.get("turn_count", 0) or 0)
        introduced_npcs = [] if quarantine_llm_payload else (update.introduced_npcs or [])
        _pool_used_new: list = []
        _recent_player_inputs = tuple(
            str(m.content) for m in [m for m in messages if isinstance(m, HumanMessage)][-3:]
        )
        npcs_left_scene = (
            [] if quarantine_llm_payload else (getattr(update, "npcs_left_scene", []) or [])
        )
        for new_name in introduced_npcs:
            new_npcs = _with_new_npc(
                new_npcs,
                new_name,
                loc,
                narrative_text,
                game_id=str(game_id or ""),
                home_id=home_id,
                turn=_turn,
                cast=_cast,
                pool_used_out=_pool_used_new,
                player_inputs=_recent_player_inputs,
            )
        for gone_name in npcs_left_scene:
            key = next((k for k in new_npcs if k.lower() == str(gone_name).lower()), None)
            if key and isinstance(new_npcs.get(key), dict):
                new_npcs = {**new_npcs, key: {**new_npcs[key], "in_scene": False}}

        updates = {
            **sim_updates,
            "messages": [AIMessage(content=narrative_text)],
            "npcs": new_npcs,
            "world": world,
            "factions": factions,
            "campaign_plan": updated_plan,
            "needs_replan": needs_replan,
        }
        if _pool_used_new:  # SPEC-297 R24: nunca duas vezes no mesmo jogo
            updates["pool_used"] = list(
                dict.fromkeys([*(state.get("pool_used") or []), *_pool_used_new])
            )
        # sinais mostrados + crime novo: o crime parte do estado já com os sinais
        updates.update(_law_scene_updates)
        updates.update(law_updates)
        # Rumores/cores do simulador são percepção narrativa, não fatos globais.
        # A consequência mecânica aplicada já é persistida diretamente pelo
        # world_simulator; o archivist deve ignorar inferências livres deste texto.
        if world_note:
            updates["memory_fact_policy"] = "canonical_only"
        if rested_player is not None:
            updates["player"] = rested_player
        elif discovery_player is not None:
            updates["player"] = discovery_player
        if leveled_player is not None:  # Fase 4.1: XP do beat (inclui o descanso, se houve)
            updates["player"] = leveled_player

        # Fase 4.3 (R5): item narrado ENTRA no inventário — só se resolver no
        # ARTIFACTS_DB (storyteller não cria item; isso é papel do loot_node).
        gained = [
            g
            for g in ([] if quarantine_llm_payload else (getattr(update, "items_gained", []) or []))
            if str(g).strip()
        ]
        rejected_claims: list[str] = []
        rejected_item_codes: list[str] = []
        if gained:
            from inventory import add_item, get_qty, is_unique, resolve_item_name
            from services.economy import claim_event, is_unique_available

            proj = state.get("world_projection") or {}
            cur_p = dict(updates.get("player") or state.get("player") or {})
            inv = list(cur_p.get("inventory") or [])
            changed = False
            seen_unique: set[str] = set()
            for g in gained:
                if _is_monetary_claim(g):
                    # O valor válido já foi aplicado pela exploração/economia.
                    # Texto do provider nunca concede nem rejeita moeda.
                    continue
                iid = resolve_item_name(str(g))
                if not iid:
                    _log_event("storyteller", "unknown_item_ignored", level="warning")
                    rejected_claims.append(str(g))
                    rejected_item_codes.append("unknown_item")
                    continue
                # Fase 6.2: único já reclamado NUNCA re-entra pela narrativa
                unique = is_unique(iid)
                if unique and iid in seen_unique:
                    # Name/ID aliases in one payload represent one grant, not a
                    # second rejection that would erase the valid first grant.
                    continue
                if unique:
                    seen_unique.add(iid)
                if unique and (get_qty(inv, iid) > 0 or not is_unique_available(iid, proj)):
                    _log_event(
                        "storyteller", "unique_item_claimed_ignored", level="warning", item_id=iid
                    )
                    rejected_claims.append(str(g))
                    rejected_item_codes.append("unique_claimed")
                    _log_event(
                        "economy",
                        "unique_claim_conflict",
                        level="warning",
                        source="narrative",
                        item_id=iid,
                    )
                    continue
                inv = add_item(inv, iid, 1)
                changed = True
                if unique:
                    rep_events.append(claim_event(iid, "player"))
            if changed:
                cur_p["inventory"] = inv
                updates["player"] = cur_p
        if rejected_item_codes:
            _log_narrative_rejected("item", rejected_item_codes)
        if rejected_claims:
            clean = prose_guard.remove_rejected_claims(narrative_text, rejected_claims)
            clean = clean or "A busca não produz nenhum objeto utilizável."
            rejection_note = (
                "Nenhum outro objeto foi acrescentado aos seus pertences."
                if changed
                else "Ao conferir seus pertences, você percebe que nada novo foi obtido."
            )
            clean = f"{clean}\n\n{rejection_note}"
            updates["messages"] = [AIMessage(content=clean)]
            updates["narrative_rejections"] = [
                f"item_rejected:{name}" for name in dict.fromkeys(rejected_claims)
            ]
            from persistence import normalize_rejected_item_claims

            updates["rejected_item_claims"] = normalize_rejected_item_claims(
                [
                    *list(state.get("rejected_item_claims") or []),
                    *rejected_claims,
                ]
            )
        reward_note = _reward_confirmation(
            reward_player_before,
            updates.get("player") or state.get("player") or {},
        )
        if reward_note:
            current_text = str(updates["messages"][0].content or "").rstrip()
            updates["messages"] = [AIMessage(content=f"{current_text}\n\n{reward_note}")]
        if invalid_story_events:
            from services.world_validators import reason_code as _reason_code

            _log_narrative_rejected(
                "event", [_reason_code(e.get("reason")) for e in invalid_story_events]
            )
            updates["narrative_rejections"] = [
                *list(updates.get("narrative_rejections") or []),
                *[
                    f"event_rejected:{entry['type']}:{entry['target_id']}"
                    for entry in invalid_story_events
                ],
            ]
        # Viagem/descanso/beat concluído = evento relevante → pede arquivamento.
        if dest or rested_player is not None or beat_done:
            updates["archive_due"] = True
        if track_bk is not None:  # Fase 6.4: rastro alimenta o Codex (3.2)
            updates["bestiary_knowledge"] = track_bk
        # Fase 2.6: enfileira propostas de evento estruturado (motor valida no archivist).
        # Fase 3.4: reputation_changed (Python) entra na mesma fila. 4.1: level_up idem.
        # Fase 6.4: XP de esquiva de armadilha pode ter gerado level_up.
        pending = (
            pending_llm_events
            + rep_events
            + level_up_events
            + extra_engine_events
            + discovery_events
        )
        if pending:
            updates["pending_world_events"] = (
                state.get("pending_world_events", []) or []
            ) + pending
            updates["archive_due"] = True  # mudança de mundo é evento relevante
        if rested_player is not None and rested_player.get("dead"):
            updates["death_pending"] = True
            updates["archive_due"] = True
            updates["pending_world_events"] = list(
                updates.get("pending_world_events") or state.get("pending_world_events", []) or []
            ) + [
                {
                    "type": "player_downed",
                    "actor_id": "player",
                    "target_id": "player",
                    "detail": "O herói tombou numa armadilha durante a viagem.",
                    "payload": {
                        "location": world.get("current_location", ""),
                        "cause": "armadilha",
                    },
                    "source": "trap",
                }
            ]

        # Fase 3.3: side quests propostas nesta cena (validadas/criadas em Python).
        turn = int(world.get("turn_count", 0))
        proposed_quests = (
            [] if quarantine_llm_payload else (getattr(update, "proposed_quests", []) or [])
        )
        new_quests, created = quest_log.register_proposed_quests(
            state.get("quests", []), proposed_quests, turn=turn
        )
        new_quests = quest_log.sync_location_progress(
            new_quests,
            str(world.get("current_location_id") or ""),
            turn=turn,
        )
        new_quests, ready_quest_ids = quest_log.sync_action_progress(
            new_quests,
            str(world.get("current_location_id") or ""),
            last_user_input,
            turn=turn,
        )
        if ready_quest_ids:
            quest_events = [
                {
                    "type": "quest_completed",
                    "actor_id": "player",
                    "target_id": quest_id,
                    "detail": "Objetivo concluído por investigação verificável.",
                    "payload": {"quest_id": quest_id},
                    "source": "system",
                }
                for quest_id in ready_quest_ids
            ]
            updates["pending_world_events"] = (
                list(
                    updates.get("pending_world_events")
                    or state.get("pending_world_events", [])
                    or []
                )
                + quest_events
            )
        if created or new_quests != list(state.get("quests", []) or []):
            updates["quests"] = new_quests
            updates["archive_due"] = True  # nova missão é evento relevante
        if turn_bl is not state.get("turn_baseline"):
            updates["turn_baseline"] = turn_bl
        if companion_narrated and companion_ack:
            updates["companion_voice_ack"] = list(companion_ack)
        if mediation_rejections:
            _log_narrative_rejected("mediation", ["secret_signature"] * len(mediation_rejections))
            updates["narrative_rejections"] = [
                *list(updates.get("narrative_rejections") or []),
                *mediation_rejections,
            ]
        return updates

    except Exception as e:
        _log_event("storyteller", "failed", level="error", error=type(e).__name__)
        fallback = {
            **sim_updates,
            "messages": [
                AIMessage(
                    content=_deterministic_story_fallback(
                        (travel_note, rest_note, world_note, faction_note, weather_note),
                        _ll,
                    )
                )
            ],
        }
        if dest:
            # viagem mecânica sobrevive ao LLM flaky: mundo anda e a cena esvazia
            from services import npc_layers

            fallback["world"] = world
            fallback["needs_replan"] = travel_needs_replan
            fallback["npcs"] = npc_layers.reset_scene(state.get("npcs", {}))
        # SPEC-233 R8: TODA mecânica já aplicada sobrevive à exceção — o texto não pode
        # prometer descanso/achado que o estado não registra (nem o inverso).
        applied_player = rested_player if rested_player is not None else discovery_player
        if applied_player is not None:
            fallback["player"] = applied_player
        if dest or rested_player is not None:
            fallback["world"] = world
            fallback["factions"] = factions
            fallback["archive_due"] = True
        if discovery_events or extra_engine_events:
            fallback["pending_world_events"] = (
                (state.get("pending_world_events", []) or [])
                + list(discovery_events)
                + list(extra_engine_events)
            )
        if turn_bl_pre_llm is not state.get("turn_baseline"):
            fallback["turn_baseline"] = turn_bl_pre_llm
        if track_bk is not None:  # rastro narrado no fallback também chega ao Codex
            fallback["bestiary_knowledge"] = track_bk
        if rested_player is not None and rested_player.get("dead"):
            fallback["death_pending"] = True
            fallback["archive_due"] = True
            fallback["pending_world_events"] = list(
                fallback.get("pending_world_events") or state.get("pending_world_events", []) or []
            ) + [
                {
                    "type": "player_downed",
                    "actor_id": "player",
                    "target_id": "player",
                    "detail": "O herói tombou numa armadilha durante a viagem.",
                    "payload": {
                        "location": world.get("current_location", ""),
                        "cause": "armadilha",
                    },
                    "source": "trap",
                }
            ]
        return fallback
