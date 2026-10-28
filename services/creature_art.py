"""SPEC-347 R13: retrato do inimigo no tabuleiro (determinístico, sem LLM, sem provider de imagem).

- `is_important` / `portrait_key`: genérico reaproveita a arte do TIPO; importante tem arte própria.
- `portrait_for`: curada (`creature`, `npc`, `creature_family`) -> registro `ready` -> marcador (ícone da família).
- Nenhum import de provider de imagem aqui (R13.9): a geração, quando existir, passa pela porta `ImageGenerator`.

O registro de retratos é um `PortraitRegistry` (Protocol): hosted usa Postgres (`app.creature_portraits`),
legacy/local usam o registro vazio (só catálogo e marcador).
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Literal, Protocol, TypedDict

from services import enemy_decks, visual_catalog
from services.discovery import normalize_bestiary_id
from services.encounter_manifest import species_label_for

FAMILY_ICON: dict[str, str] = {  # D-347-H: só ícones que já existem em web/src/design/icons.tsx
    "predador": "combat",
    "predador_apice": "unique",
    "bruto": "combat",
    "covarde_oportunista": "exit",
    "conjurador": "card-virtue",
    "morto_vivo_implacavel": "death",
    "guardiao": "card-reaction",
    "tatico": "ruler",
    "lider_matilha": "quest",
    "emboscador": "dark",
    "abissal": "abyss",
    "desconhecida": "dark",
}


class GerarOffer(TypedDict):
    preco_estilhas: int
    escopo: Literal["tipo", "unico"]


class CreaturePortrait(TypedDict):
    estado: Literal["pronto", "gerando", "marcador"]
    src: str | None
    familia: str
    icone: str
    alt: str
    proprio: bool
    gerar: GerarOffer | None


class PortraitRegistry(Protocol):
    def get(self, portrait_key: str) -> dict[str, Any] | None: ...


class EmptyRegistry:
    """legacy/local: não há gravação de retratos (só catálogo e marcador)."""

    def get(self, portrait_key: str) -> dict[str, Any] | None:
        return None


def mode() -> str:
    return "on" if os.environ.get("RPG_CREATURE_ART", "off").strip().lower() == "on" else "off"


def _fold(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", raw).strip().lower()


def slug(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _fold(text)).strip("-") or "x"


def _strip_number(name: str) -> str:
    return re.sub(r"\s+\d+$", "", str(name or "")).strip()


def is_important(enemy: dict[str, Any], manifest: dict[str, Any] | None) -> tuple[bool, str]:
    """(importante?, motivo) - motivo em {"chefe", "npc", "nome_proprio", "generico"}."""
    if _fold(enemy.get("categoria")) == "chefe" or _fold(enemy.get("type")) in {"boss", "chefe"}:
        return True, "chefe"
    manifest = manifest or {}
    ref = str(manifest.get("target_ref") or "")
    npc_name = str(manifest.get("npc_name") or (ref[4:] if ref.startswith("npc:") else ""))
    if (manifest.get("source") == "npc_in_scene" or ref.startswith("npc:")) and npc_name:
        if _fold(_strip_number(enemy.get("name", ""))) == _fold(npc_name):
            return True, "npc"
    name = _strip_number(enemy.get("name", ""))
    if name and _fold(name) != _fold(species_label_for(enemy)):
        return True, "nome_proprio"
    return False, "generico"


def family_of(enemy: dict[str, Any]) -> str:
    return enemy_decks.family_key(enemy) or "desconhecida"


def _type_key(enemy: dict[str, Any]) -> str:
    bid = normalize_bestiary_id(enemy)
    if bid:
        return f"tipo:{bid}"
    pool_id = str(enemy.get("pool_entry_id") or "")
    if pool_id:
        return f"tipo:bst:{pool_id}"
    return f"tipo:gen:{slug(species_label_for(enemy))}"


def portrait_key(
    enemy: dict[str, Any],
    manifest: dict[str, Any] | None,
    *,
    game_id: str,
    npc_entity_id: str | None = None,
) -> str:
    important, why = is_important(enemy, manifest)
    if not important:
        return _type_key(enemy)
    pool_id = str(enemy.get("pool_entry_id") or "")
    name = slug(_strip_number(enemy.get("name", "")))
    if why == "npc" and npc_entity_id:
        return f"npc:{npc_entity_id}"
    if pool_id:
        return f"unico:bst:{pool_id}:{name}"
    return f"unico:{game_id}:{slug(species_label_for(enemy))}:{name}"


def _src(asset: dict[str, Any] | None) -> str | None:
    variants = (asset or {}).get("variants") or {}
    for name in ("thumbnail", "card", "full"):
        if (variants.get(name) or {}).get("url"):
            return str(variants[name]["url"])
    return None


def _curated(subject_type: str, subject_id: str) -> str | None:
    return _src(visual_catalog.visual_for(subject_type, subject_id)) if subject_id else None


_VARIANT_ORDER = ("thumb", "thumbnail", "full", "display")


def variant_url(variants: Any) -> str | None:
    """URL servível da melhor variante de uma linha do registro. Aceita o formato REAL do job
    (`workers/dynamic_art_jobs.py`: lista de `{variant: "thumb"|"full", key, ...}`) e o dict
    `{thumb|thumbnail|full|display: {url}}`. O job só grava `key` (objeto no storage): quem converte a chave em URL
    é a SPEC-352; até lá uma linha sem `url` não resolve imagem (cai no marcador, nunca num caminho inventado)."""
    if isinstance(variants, list):
        by_name = {str(v.get("variant")): v for v in variants if isinstance(v, dict)}
    elif isinstance(variants, dict):
        by_name = {str(k): v for k, v in variants.items() if isinstance(v, dict)}
    else:
        return None
    for name in _VARIANT_ORDER:
        url = (by_name.get(name) or {}).get("url")
        if url:
            return str(url)
    return None


def _registry_src(registry: PortraitRegistry, key: str, *, game_id: str) -> tuple[str | None, bool]:
    """(src, pending). Visibilidade: `game` só para o jogo de origem; `shared` para todos."""
    row = registry.get(key)
    if not row:
        return None, False
    if row.get("visibility") == "game" and row.get("origin_game_id") != game_id:
        return None, False
    if row.get("status") == "ready":
        return variant_url(row.get("variants")), False
    return None, row.get("status") == "pending"


def portrait_for(
    enemy: dict[str, Any],
    manifest: dict[str, Any] | None,
    *,
    game_id: str,
    registry: PortraitRegistry | None = None,
    npc_entity_id: str | None = None,
    quote_price: int | None = None,
) -> CreaturePortrait:
    """Ordem: (a) arte própria do importante -> (b) curada da criatura -> (c) registro do tipo ->
    (d) curada da família -> (e) marcador. `gerar` só com a flag `on`, preço conhecido (hosted) e sem
    arte própria da chave nem geração pendente."""
    registry = registry or EmptyRegistry()
    important, _why = is_important(enemy, manifest)
    key = portrait_key(enemy, manifest, game_id=game_id, npc_entity_id=npc_entity_id)
    family = family_of(enemy)
    bid = normalize_bestiary_id(enemy)
    pool_id = str(enemy.get("pool_entry_id") or "")

    own_src: str | None = None
    pending = False
    if important:
        if key.startswith("npc:"):
            own_src = _curated("npc", key[4:])
        if own_src is None:
            own_src, pending = _registry_src(registry, key, game_id=game_id)
    curated_creature = _curated("creature", bid) or (
        _curated("creature", f"bst:{pool_id}") if pool_id else None
    )
    type_src, type_pending = _registry_src(registry, _type_key(enemy), game_id=game_id)
    src = own_src or curated_creature or type_src or _curated("creature_family", family)
    if not important:
        pending = pending or (type_pending and not (curated_creature or type_src))
    estado: Literal["pronto", "gerando", "marcador"]
    estado = "gerando" if pending else ("pronto" if src else "marcador")

    type_has_art = bool(curated_creature or type_src)
    has_own_art = own_src is not None if important else type_has_art
    gerar: GerarOffer | None = None
    if mode() == "on" and quote_price is not None and not pending and not has_own_art:
        gerar = {"preco_estilhas": int(quote_price), "escopo": "unico" if important else "tipo"}
    return {
        "estado": estado,
        "src": src,
        "familia": family,
        "icone": FAMILY_ICON.get(family, "dark"),
        "alt": f"Retrato de {enemy.get('name') or 'criatura'}",
        "proprio": own_src is not None,
        "gerar": gerar,
    }


def has_curated_art(enemy: dict[str, Any]) -> bool:
    """A view inclui `retrato` com a flag `off` só quando existe arte curada (R13.7)."""
    bid = normalize_bestiary_id(enemy)
    return bool(
        (bid and _curated("creature", bid)) or _curated("creature_family", family_of(enemy))
    )
