"""SPEC-364 R17/R18 (D-364-1): debito = custo liquidado <= teto, reserva volta a 0; oferta carrega o teto exato."""

from __future__ import annotations

import api
import api_presenters
import api_core
from services import creature_art
from tests.test_image_quotes_local import (  # noqa: F401
    confirm,
    image_case,
    issue,
    lease,
    run,
)
from tests.test_spec363_portrait_offer import _Registry, _wire


def test_settle_below_ceiling_releases_remainder(image_case, tmp_path):  # noqa: F811
    c = image_case
    quote = issue(c)
    ceiling = int(quote["credits_milli"])
    generation = confirm(c, quote)
    assert c.repo.wallet.balance(c.owner).reserved_milli == ceiling
    job = lease(c, generation)
    _gen, result = run(c, generation, job, tmp_path, cost="0.01")
    assert result["status"] == "ready"
    balance = c.repo.wallet.balance(c.owner)
    settled = 1000 - balance.available_milli
    assert 0 < settled < ceiling  # custo liquidado menor que o teto
    assert balance.reserved_milli == 0  # o resto da reserva voltou


def test_settle_above_ceiling_capped(image_case, tmp_path):  # noqa: F811
    c = image_case
    quote = issue(c)
    ceiling = int(quote["credits_milli"])
    generation = confirm(c, quote)
    job = lease(c, generation)
    run(c, generation, job, tmp_path, cost="0.05")
    balance = c.repo.wallet.balance(c.owner)
    assert 1000 - balance.available_milli == ceiling  # nunca acima do teto
    assert balance.reserved_milli == 0


def test_portrait_for_carries_exact_ceiling(monkeypatch):
    monkeypatch.setattr(creature_art, "mode", lambda: "on")
    enemy = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}
    p = creature_art.portrait_for(enemy, None, game_id="g364", quote_price=1, quote_milli=15)
    assert p["gerar"] == {"preco_estilhas": 1, "preco_milli": "15", "escopo": "tipo"}
    legacy = creature_art.portrait_for(enemy, None, game_id="g364", quote_price=1)
    assert "preco_milli" not in legacy["gerar"]


def test_offer_has_preco_milli(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    monkeypatch.setattr(api_core, "_database_profile", lambda: True)
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    monkeypatch.setattr(creature_art, "mode", lambda: "on")
    monkeypatch.setattr(api_presenters, "_portrait_price_estilhas", lambda: 1)
    monkeypatch.setitem(api._PORTRAIT_PRICE_CACHE, "milli", 15)
    enemy = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}
    view = api._enemy_portrait({"game_id": "g364", "combat": {}}, {}, enemy, registry=_Registry())
    assert view["gerar"]["preco_estilhas"] == 1
    assert view["gerar"]["preco_milli"] == "15"


def test_offer_ignores_stale_milli(monkeypatch):
    _wire(monkeypatch, switch=True, pricing=True)
    monkeypatch.setattr(api_core, "_database_profile", lambda: True)
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    monkeypatch.setattr(creature_art, "mode", lambda: "on")
    monkeypatch.setattr(api_presenters, "_portrait_price_estilhas", lambda: 3)
    monkeypatch.setitem(api._PORTRAIT_PRICE_CACHE, "milli", 15)  # 15 milli => 1 Estilha != 3
    enemy = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}
    view = api._enemy_portrait({"game_id": "g364", "combat": {}}, {}, enemy, registry=_Registry())
    assert "preco_milli" not in view["gerar"]
