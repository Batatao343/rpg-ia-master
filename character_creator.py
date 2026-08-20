"""
agents/character_creator.py
Gera a ficha do personagem baseada em História, Nível e Região.
Versão V7.0 (spec conflito-01): 5 Virtudes (0-5) substituem os 6 atributos D&D;
Vitalidade/Ferimentos derivam de Corpo. A distribuição das Virtudes vem do JOGADOR
(wizard) — a classe apenas RECOMENDA. O LLM só sugere inventário/flavor textual.
"""
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from llm_setup import get_llm, ModelTier
import gamedata

# --- IMPORTAÇÕES ESSENCIAIS ---
try:
    from rag import query_rag
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    def query_rag(*args, **kwargs): return ""

# Importa os dados oficiais para garantir consistência
try:
    from gamedata import CLASSES, load_json_data
except ImportError:
    CLASSES = {}
    def load_json_data(_): return {}

# --- VIRTUDE PRIMÁRIA POR CLASSE (recomendação de distribuição / attack_bonus) ---
# spec conflito-01: 5 Posturas diante do Abismo mapeadas às 5 Virtudes.
CLASS_PRIMARY_VIRTUE = {
    "Devoto do Abismo": "forca",
    "Sangromante": "agilidade",
    "Corruptor": "mente",
    "Arcanista Cinzento": "mente",
    "Médico de Campo": "mente",
}

# Bridge dos dados LEGADO (traits raciais em origins.json ainda usam chaves D&D):
# mapeia atributo curto -> Virtude. wis/int caem em "mente" (não há Virtude dedicada).
_ATTR_TO_VIRTUDE = {
    "str": "forca", "dex": "agilidade", "con": "corpo",
    "int": "mente", "wis": "mente", "cha": "carisma",
    # tolera nomes longos/PT eventuais
    "strength": "forca", "forca": "forca", "força": "forca",
    "dexterity": "agilidade", "agilidade": "agilidade",
    "constitution": "corpo", "corpo": "corpo",
    "intelligence": "mente", "mente": "mente",
    "wisdom": "mente", "charisma": "carisma", "carisma": "carisma",
}

# Distribuição default quando a classe não recomenda nada (permutação de 4/3/2/1/1).
_DEFAULT_VIRTUDES = {"forca": 4, "agilidade": 3, "corpo": 2, "mente": 1, "carisma": 1}


def to_virtude_key(key: str) -> str:
    """Normaliza uma chave de atributo/Virtude para a chave curta de Virtude."""
    return _ATTR_TO_VIRTUDE.get(str(key or "").strip().lower(), str(key or "").strip().lower())


def validate_virtude_distribution(virtudes: Dict[str, int]) -> None:
    """Rejeita distribuição de Virtudes fora do multiset 4/3/2/1/1 (R2).

    Levanta ValueError com mensagem clara. Aceita SÓ as 5 chaves canônicas,
    cada uma inteira, e o multiset ordenado precisa ser exatamente [1,1,2,3,4].
    """
    if not isinstance(virtudes, dict):
        raise ValueError("Virtudes precisa ser um dicionário {virtude: valor}.")
    faltando = [k for k in gamedata.VIRTUDES if k not in virtudes]
    extra = [k for k in virtudes if k not in gamedata.VIRTUDES]
    if faltando or extra:
        raise ValueError(
            f"Virtudes deve conter exatamente {list(gamedata.VIRTUDES)} — "
            f"faltando={faltando}, inesperadas={extra}."
        )
    try:
        valores = sorted(int(virtudes[k]) for k in gamedata.VIRTUDES)
    except (TypeError, ValueError):
        raise ValueError("Valores de Virtude precisam ser inteiros.")
    if valores != sorted(gamedata.DISTRIBUICAO_VIRTUDES_INICIAL):
        raise ValueError(
            "Distribuição de Virtudes inválida: use exatamente os valores "
            f"{list(gamedata.DISTRIBUICAO_VIRTUDES_INICIAL)} (um por Virtude). "
            f"Recebido (ordenado): {valores}."
        )


def recommended_virtudes(class_name: str) -> Dict[str, int]:
    """Distribuição RECOMENDADA da classe (base_stats.virtudes) — nunca vinculante."""
    data = CLASSES.get(class_name, {}) if isinstance(CLASSES, dict) else {}
    rec = (data.get("base_stats", {}) or {}).get("virtudes")
    if isinstance(rec, dict) and set(rec) == set(gamedata.VIRTUDES):
        try:
            validate_virtude_distribution(rec)
            return {k: int(rec[k]) for k in gamedata.VIRTUDES}
        except ValueError:
            pass
    return dict(_DEFAULT_VIRTUDES)


def _resolve_virtudes(user_input: Dict[str, Any], class_name: str) -> Dict[str, int]:
    """Virtudes escolhidas pelo jogador (validadas) ou recomendação da classe."""
    escolhidas = user_input.get("virtudes")
    if escolhidas:
        norm = {to_virtude_key(k): int(v) for k, v in dict(escolhidas).items()}
        validate_virtude_distribution(norm)  # levanta se inválida
        return {k: norm[k] for k in gamedata.VIRTUDES}
    return recommended_virtudes(class_name)


# --- SCHEMAS DA IA ---

class PlayerFlavorSchema(BaseModel):
    """A IA só sugere sabor textual — Virtudes vêm do jogador, não do LLM."""
    inventory: List[str] = Field(description="Itens baseados na Região e Lore.")
    flavor_abilities: List[str] = Field(description="2 ou 3 magias/truques extras (Flavor) além da passiva.")

# --- LÓGICA AUXILIAR ---

def _prof_bonus(level: int) -> int:
    return 2 + ((int(level) - 1) // 4)


def _calculate_attack_bonus(class_name: str, virtudes: Dict[str, int], level: int) -> int:
    """attack_bonus = Virtude primária da classe + bônus de proficiência.

    Ponte transicional: o motor antigo ainda soma um attack_bonus; a fórmula real
    (2d10 + Virtude vs Esquiva) chega na conflito-04."""
    primary = CLASS_PRIMARY_VIRTUE.get(class_name)
    if not primary:
        primary = max(virtudes, key=virtudes.get) if virtudes else "forca"
    return int(virtudes.get(primary, 0)) + _prof_bonus(level)


def find_race(race: str) -> Dict:
    """Resolve a raça de data/origins.json por id ou nome (case-insensitive)."""
    races = (load_json_data("origins.json") or {}).get("races", [])
    key = str(race or "").strip().lower()
    for r in races:
        if key in (str(r.get("id", "")).lower(), str(r.get("name", "")).lower()):
            return r
    return {}


def apply_racial_traits(sheet: Dict[str, Any], race: str) -> Dict[str, Any]:
    """
    Aplica os traits mecânicos da raça (Fase 2.5b) sobre a ficha, em Python
    determinístico — pós-LLM, nunca confiando na IA para números.

    spec conflito-01: attr_bonus/save_bonus dos dados LEGADO (chaves D&D) são
    mapeados para Virtudes (`_ATTR_TO_VIRTUDE`); bônus em Virtude respeita o teto 5.
    Muta e retorna a própria `sheet`.
    """
    race_data = find_race(race)
    traits = race_data.get("traits", []) or []
    names: List[str] = []
    resists: List[str] = []
    save_bonus: Dict[str, int] = {}

    for t in traits:
        names.append(t.get("name", t.get("id", "?")))
        fx = t.get("effects", {}) or {}
        # spec conflito-01: attr_bonus racial (dados D&D LEGADO) NÃO altera Virtudes.
        # Num Virtude 0-5 um +1/+2 é um salto grande demais; a distribuição
        # 4/3/2/1/1 é escolha do jogador. Bônus racial de Virtude fica adiado para
        # um rework de raças dedicado — aqui a raça pesa em hp/defesa/resist/save/itens.
        # ``hp_bonus`` é metadado legado de origem e não altera a Vitalidade:
        # o teto canônico deriva exclusivamente de Corpo e Cicatrizes.
        if fx.get("defense_bonus"):
            sheet["defense"] = int(sheet.get("defense", 10)) + int(fx["defense_bonus"])
        if fx.get("gold_bonus"):
            sheet["gold"] = int(sheet.get("gold", 0)) + int(fx["gold_bonus"])
        for item in fx.get("start_items") or []:
            from inventory import add_item, item_display
            inv = sheet.setdefault("inventory", [])
            if not any(item_display(e) == item or e.get("id") == item
                       for e in inv if isinstance(e, dict)):
                sheet["inventory"] = add_item(inv, item, 1)
        resists.extend(str(c).lower() for c in fx.get("condition_resist") or [])
        for attr, inc in (fx.get("save_bonus") or {}).items():
            k = to_virtude_key(attr)
            save_bonus[k] = save_bonus.get(k, 0) + int(inc)

    sheet["racial_traits"] = names
    sheet["condition_resists"] = resists
    sheet["racial_save_bonus"] = save_bonus
    return sheet


def _resolve_starting_cards(user_input: Dict[str, Any], class_name: str,
                            virtudes: Dict[str, int]) -> Dict[str, Any]:
    """spec conflito-02: monta Acervo (6) + Preparadas (4) + 2 Cartas de Virtude.

    Vem do JOGADOR (wizard) quando fornecido; senão auto-seleciona do pool da
    classe (determinístico) — fluxo clássico/CLI segue funcionando."""
    from services import cards as cards_svc

    level = max(1, min(gamedata.NIVEL_MAX, int(user_input.get("level", 1) or 1)))
    # A criação nunca usa uma Carta para inferir ramo: até a escolha explícita
    # de subclasse, o Acervo nasce somente do tronco e respeita o gate numérico.
    available = [
        card for card in cards_svc.cards_for_class(class_name)
        if not card.get("subclasse") and int(card.get("level_req", 1) or 1) <= level
        and not card.get("apex")
    ]
    # conflito-13/14: `data/cards/exemplos.json` permanece como fixture e contém
    # IDs legados da mesma classe. A ordem alfabética dos arquivos fazia algumas
    # classes começarem com esses exemplos em vez do acervo autoral v4.
    canonical = [
        c for c in available
        if c.get("classe") == class_name and c.get("origem") == "conflito-14"
    ]
    remaining = [c for c in available if c not in canonical]
    pool = [c["id"] for c in canonical + remaining]
    known = list(dict.fromkeys(user_input.get("known_cards") or []))
    if not known:
        known = pool[:6]
    else:
        known = [c for c in known if c in pool][:6]
    if len(known) < 6:  # completa com o pool se o jogador escolheu de menos
        known += [c for c in pool if c not in known][: 6 - len(known)]

    slots = gamedata.prepared_slots_for_level(user_input.get("level", 1))
    prepared = list(dict.fromkeys(user_input.get("prepared_cards") or []))
    prepared = [c for c in prepared if c in known][:slots]
    if not prepared:
        prepared = known[:slots]

    # 2 Cartas de Virtude (permanentes, fora dos slots), estágio pela Virtude relacionada
    vpool = cards_svc.virtue_cards_pool()
    chosen_ids = list(dict.fromkeys(user_input.get("virtue_cards") or []))
    valid_ids = {c["id"] for c in vpool}
    chosen_ids = [cid for cid in chosen_ids if cid in valid_ids][:2]
    if len(chosen_ids) < 2:
        for c in vpool:
            if c["id"] not in chosen_ids:
                chosen_ids.append(c["id"])
            if len(chosen_ids) == 2:
                break
    virtue_cards = []
    for cid in chosen_ids[:2]:
        card = cards_svc.get_card(cid) or {}
        vkey = gamedata.normalize_virtude(card.get("virtude_relacionada", ""))
        estagio = gamedata.virtue_card_stage(virtudes.get(vkey, 0))
        virtue_cards.append({
            "card_id": cid, "virtude": vkey, "estagio": estagio, "mastery": 0,
        })

    return {
        "known_cards": known,
        "prepared_cards": prepared,
        "virtue_cards": virtue_cards,
        "card_usage": {},
        "evolved_cards": {},
    }


def _get_class_data(class_name: str) -> Dict:
    """Retorna os dados oficiais da classe ou um padrão genérico."""
    if class_name in CLASSES:
        return CLASSES[class_name]
    return {
        "passive": "Determinação: +1 em testes de Vontade.",
        "base_stats": {"hp": 10, "virtudes": dict(_DEFAULT_VIRTUDES)},
    }

# --- FUNÇÃO PRINCIPAL ---

def create_player_character(user_input: Dict[str, Any], *,
                            use_llm_flavor: bool = True) -> Dict[str, Any]:
    name = user_input.get("name", "Herói")
    p_class = user_input.get("class_name", "Aventureiro")
    race = user_input.get("race", "Humano")
    region = user_input.get("region", "Nova Arcádia")
    backstory = user_input.get("backstory", "")

    raw_level = str(user_input.get("level", "1"))
    clean_level = "".join(filter(str.isdigit, raw_level))
    level = int(clean_level) if clean_level else 1

    # 1. BUSCA DADOS OFICIAIS (A "Regra")
    class_data = _get_class_data(p_class)
    base_stats = class_data.get("base_stats", {})

    # 2. VIRTUDES — escolha do jogador (validada) ou recomendação da classe (R2)
    virtudes = _resolve_virtudes(user_input, p_class)

    # 3. Vitalidade/Ferimentos derivados de Corpo (R4). Nível e origem não
    # escrevem HP: os campos legados serão aliases criados pelo helper canônico.

    # spec refatoracao-sistema-classes: Entropia é o pool ÚNICO das 5 classes.
    level_gains = class_data.get("level_gains", {}) or {}
    base_entropy = base_stats.get("entropy", 0)
    final_entropy = base_entropy + int(level_gains.get("entropy", 0) or 0) * (level - 1)

    # 4. LORE + geração de sabor via IA (só inventário/flavor — Virtudes NÃO vêm do LLM)
    flavor_data: Dict[str, Any] = {}
    if use_llm_flavor:
        region_lore = _get_region_lore(region)
        llm = get_llm(temperature=0.6, tier=ModelTier.SMART)
        system_msg = SystemMessage(content=f"""
        Você é um Motor de Regras para RPG do mundo de Valoria.

        CONTEXTO DO MUNDO: {region_lore}
        CLASSE: {p_class}.

        TAREFA:
        1. Gere um inventário temático da região {region}.
        2. Sugira 2 habilidades extras (flavor) que combinem com a classe.
        """)
        human_msg = HumanMessage(content=f"Personagem: {name}, {race} {p_class}. Conceito: {backstory}")

        try:
            stats = llm.with_structured_output(PlayerFlavorSchema).invoke([system_msg, human_msg])
            if stats:
                dumped = stats.model_dump()
                # Sem chave, o FallbackLLM devolve AIMessage cujo dump não tem 'inventory'.
                if isinstance(dumped, dict) and "inventory" in dumped:
                    flavor_data = dumped
        except Exception as e:
            print(f"⚠️ Erro IA: {e}")

    if not flavor_data:
        flavor_data = {
            "inventory": ["Kit Básico"] if use_llm_flavor else [],
            "flavor_abilities": [],
        }

    # 5. MONTAGEM FINAL (MERGE)
    sheet = {
        "name": name,
        "class_name": p_class,
        "race": race,
        "region": region,
        "backstory": backstory,
        "concept": f"{race} {p_class} de {region}",
        "traits": [],
        "entropy": final_entropy,
        "max_entropy": final_entropy,
        "abyss_charge": 0,
        "virtudes": virtudes,
        "inventory": [],  # preenchido abaixo
        "level": level,
        "xp": 0,
        "pending_choices": [],
    }

    # spec conflito-02/13: Cartas substituem integralmente known_abilities.
    sheet.update(_resolve_starting_cards(user_input, p_class, virtudes))

    # Vitalidade/Ferimentos: cheia na criação (R4)
    gamedata.sync_player_vitals(sheet, heal_to_full=True)

    # 6. Inventário estruturado — starting_equipment canônico + flavor do LLM
    from inventory import add_item, backfill_inventory
    inv: List[Dict] = []
    for iid in class_data.get("starting_equipment", []) or []:
        inv = add_item(inv, iid, 1)
    for free_name in flavor_data.get("inventory", []) or []:
        inv = add_item(inv, str(free_name), 1)
    sheet["inventory"] = inv

    # 7. TRAITS RACIAIS (Fase 2.5b) — ANTES de defesa/ataque (bônus de Virtude reflete)
    apply_racial_traits(sheet, race)
    gamedata.sync_legacy_hp_aliases(sheet)

    # 8. Equipamento (auto-equipa melhor arma/armadura UMA vez)
    sheet.update(backfill_inventory(sheet))

    # 9. Defesa/Ataque derivados de Virtude (ponte transicional até a conflito-04/05)
    base_def = base_stats.get("defense", 10)
    racial_def_bonus = int(sheet.get("defense", 0) or 0) - 10 if "defense" in sheet else 0
    sheet["defense"] = max(base_def, 10 + int(virtudes.get("agilidade", 0))) + max(0, racial_def_bonus)
    sheet["attack_bonus"] = _calculate_attack_bonus(p_class, sheet["virtudes"], level)
    return sheet

def _get_region_lore(region_name: str) -> str:
    if not RAG_AVAILABLE: return ""
    try: return query_rag(f"Describe {region_name}", index_name="lore")
    except: return ""
