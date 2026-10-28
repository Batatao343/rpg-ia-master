"""SPEC-347 R13: retrato do inimigo (importância, chave, resolução, visibilidade, marcador, sem provider)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services import creature_art as ca
from services import visual_catalog


def _goblin(n=1, name="Goblin"):
    return {"id": f"enemy_goblin_{n}", "name": name, "categoria": "padrao"}


class Reg:
    def __init__(self, rows=None):
        self.rows = rows or {}

    def get(self, key):
        return self.rows.get(key)

    def sign(self, store, key):  # SPEC-352 F3: o teste usa a "key" como URL
        return key


def _ready(key, *, visibility="shared", origin="g0", url="/x.webp"):
    return {
        key: {
            "status": "ready",
            "visibility": visibility,
            "origin_game_id": origin,
            "store": "shared",
            "object_keys": {"thumb": url},
        }
    }


# --- is_important -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "enemy,manifest,expected",
    [
        (_goblin(1), None, (False, "generico")),
        (
            {"id": "enemy_bandido_2", "name": "Bandido 2", "categoria": "lacaio"},
            None,
            (False, "generico"),
        ),
        ({"id": "adhoc_1", "name": "Saqueador de Marfim"}, None, (False, "generico")),
        (
            {"id": "enemy_goblin_2", "name": "Goblin", "categoria": "elite"},
            None,
            (False, "generico"),
        ),
        (
            {"id": "enemy_bandido_capitao_1", "name": "Capitão", "categoria": "chefe"},
            None,
            (True, "chefe"),
        ),
        (_goblin(3, "Grishnak"), None, (True, "nome_proprio")),
        (
            {"id": "x_1", "name": "Borin"},
            {"source": "npc_in_scene", "target_ref": "npc:Borin", "npc_name": "Borin"},
            (True, "npc"),
        ),
    ],
)
def test_is_important(enemy, manifest, expected):
    assert ca.is_important(enemy, manifest) == expected


# --- chaves -----------------------------------------------------------------------------
def test_generic_goblins_share_one_type_key():
    keys = {ca.portrait_key(_goblin(n), None, game_id="g1") for n in (1, 2, 3)}
    assert keys == {"tipo:enemy_goblin"}
    r = {"id": "adhoc_1", "name": "Bandido 1"}, {"id": "adhoc_2", "name": "Bandido 2"}
    assert len({ca.portrait_key(e, None, game_id="g1") for e in r}) == 1


def test_important_goblins_have_distinct_keys_and_stable_in_same_game():
    a = ca.portrait_key(_goblin(3, "Grishnak"), None, game_id="g1")
    b = ca.portrait_key(_goblin(4, "Ugruk"), None, game_id="g1")
    assert a != b and a.startswith("unico:g1:") and b.startswith("unico:g1:")
    assert a == ca.portrait_key(_goblin(7, "Grishnak"), None, game_id="g1")
    assert a != ca.portrait_key(_goblin(3, "Grishnak"), None, game_id="g2")


def test_npc_key_uses_entity_id():
    key = ca.portrait_key(
        {"id": "x_1", "name": "Borin"},
        {"source": "npc_in_scene", "npc_name": "Borin"},
        game_id="g1",
        npc_entity_id="borin-barqueiro",
    )
    assert key == "npc:borin-barqueiro"


# --- resolução --------------------------------------------------------------------------
def test_marker_with_family_icon_when_no_art():
    p = ca.portrait_for(_goblin(), None, game_id="g1")
    assert p["estado"] == "marcador" and p["src"] is None and p["gerar"] is None
    assert (
        p["icone"] == ca.FAMILY_ICON.get(p["familia"], "dark") and p["alt"] == "Retrato de Goblin"
    )


def test_registry_ready_type_art_is_shared_and_without_offer(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    reg = Reg(_ready("tipo:enemy_goblin"))
    p = ca.portrait_for(_goblin(), None, game_id="outro-jogo", registry=reg, quote_price=40)
    assert p["estado"] == "pronto" and p["src"] == "/x.webp" and p["gerar"] is None


def test_offer_only_with_flag_on_and_price(monkeypatch):
    p = ca.portrait_for(_goblin(), None, game_id="g1", quote_price=40)
    assert p["gerar"] is None  # flag off
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    assert ca.portrait_for(_goblin(), None, game_id="g1", quote_price=40)["gerar"] == {
        "preco_estilhas": 40,
        "escopo": "tipo",
    }
    assert (
        ca.portrait_for(_goblin(), None, game_id="g1")["gerar"] is None
    )  # sem perfil de preço (legacy/local)


def test_important_shows_type_art_first_then_own(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    gr = _goblin(3, "Grishnak")
    own_key = ca.portrait_key(gr, None, game_id="g1")
    reg = Reg(_ready("tipo:enemy_goblin", url="/tipo.webp"))
    before = ca.portrait_for(gr, None, game_id="g1", registry=reg, quote_price=60)
    assert before["src"] == "/tipo.webp" and before["proprio"] is False
    assert before["gerar"] == {"preco_estilhas": 60, "escopo": "unico"}
    reg.rows.update(_ready(own_key, visibility="game", origin="g1", url="/gr.webp"))
    after = ca.portrait_for(gr, None, game_id="g1", registry=reg, quote_price=60)
    assert after["src"] == "/gr.webp" and after["proprio"] is True and after["gerar"] is None
    other = ca.portrait_for(gr, None, game_id="g2", registry=reg, quote_price=60)
    assert (
        other["src"] == "/tipo.webp" and other["proprio"] is False
    )  # `unico:` de outro jogo nunca aparece


def test_pending_shows_gerando_and_blocks_offer(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    reg = Reg({"tipo:enemy_goblin": {"status": "pending", "visibility": "shared"}})
    p = ca.portrait_for(_goblin(), None, game_id="g1", registry=reg, quote_price=40)
    assert p["estado"] == "gerando" and p["gerar"] is None


def test_hold_registry_row_is_visible_only_to_origin_game():
    reg = Reg(_ready("tipo:enemy_goblin", visibility="game", origin="g1"))
    assert ca.portrait_for(_goblin(), None, game_id="g1", registry=reg)["estado"] == "pronto"
    assert ca.portrait_for(_goblin(), None, game_id="g2", registry=reg)["estado"] == "marcador"


def test_curated_creature_art_beats_registry_and_family_art_is_fallback(monkeypatch):
    def fake_visual(kind, sid):
        table = {
            ("creature", "enemy_goblin"): "/cur.webp",
            ("creature_family", "bruto"): "/fam.webp",
        }
        url = table.get((kind, sid))
        return {"variants": {"thumbnail": {"url": url}}} if url else None

    monkeypatch.setattr(visual_catalog, "visual_for", fake_visual)
    reg = Reg(_ready("tipo:enemy_goblin", url="/reg.webp"))
    assert ca.portrait_for(_goblin(), None, game_id="g1", registry=reg)["src"] == "/cur.webp"
    other = {"id": "enemy_x_1", "name": "X", "arquetipo": "bruto"}
    assert ca.portrait_for(other, None, game_id="g1")["src"] == "/fam.webp"


def test_no_image_provider_import_in_creature_art():
    tree = ast.parse(Path(ca.__file__).read_text(encoding="utf-8"))
    mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    ]
    assert not any("openai_images" in (m or "") for m in mods)


def test_family_icons_only_use_existing_web_icons():
    icons = Path("web/src/design/icons.tsx").read_text(encoding="utf-8")
    for icon in set(ca.FAMILY_ICON.values()):
        assert f'"{icon}":' in icons, icon


# --- view -------------------------------------------------------------------------------
def test_view_has_no_retrato_key_with_flag_off_and_no_curated_art(monkeypatch):
    import api
    from tests.test_api_jogadas import _state

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.delenv("RPG_CREATURE_ART", raising=False)
    block = api._combat_block(_state(monkeypatch))
    assert block["enemies"] and all("retrato" not in e for e in block["enemies"])


def test_view_exposes_marker_with_flag_on(monkeypatch):
    import api
    from tests.test_api_jogadas import _state

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setenv("RPG_CREATURE_ART", "on")
    block = api._combat_block(_state(monkeypatch))
    retrato = block["enemies"][0]["retrato"]
    assert retrato["estado"] == "marcador" and retrato["alt"].startswith("Retrato de ")
    assert set(retrato) == {"estado", "src", "familia", "icone", "alt", "proprio", "gerar"}


# --- formato real do registro (SPEC-347 P2-1) ---------------------------------------------
def _job_variants(with_url):
    """Mesmo formato que `workers/dynamic_art_jobs.generate_dynamic_art_job` devolve em `variants`."""
    rows = [
        {
            "key": "shared/creatures/x/a.full.abc.webp",
            "sha256": "f",
            "bytes": 10,
            "variant": "full",
            "mime_type": "image/webp",
            "width": 1536,
            "height": 1536,
        },
        {
            "key": "shared/creatures/x/a.thumb.abc.webp",
            "sha256": "t",
            "bytes": 5,
            "variant": "thumb",
            "mime_type": "image/webp",
            "width": 384,
            "height": 384,
        },
    ]
    if with_url:
        rows[0]["url"], rows[1]["url"] = "/m/full.webp", "/m/thumb.webp"
    return rows


def test_variant_url_reads_the_real_job_format():
    assert ca.variant_url(_job_variants(True)) == "/m/thumb.webp"  # thumb antes de full
    assert (
        ca.variant_url(_job_variants(False)) is None
    )  # só `key`: a 352 converte; nunca inventa caminho
    assert ca.variant_url({"full": {"url": "/f"}, "thumb": {"url": "/t"}}) == "/t"
    assert ca.variant_url(None) is None


def test_registry_row_in_real_job_format_resolves_or_falls_back_to_marker():
    def row(v):
        return {"tipo:enemy_goblin": {"status": "ready", "visibility": "shared", "variants": v}}

    ok = ca.portrait_for(_goblin(), None, game_id="g", registry=Reg(row(_job_variants(True))))
    assert ok["estado"] == "pronto" and ok["src"] == "/m/thumb.webp"
    no_url = ca.portrait_for(_goblin(), None, game_id="g", registry=Reg(row(_job_variants(False))))
    assert no_url["estado"] == "marcador" and no_url["src"] is None
