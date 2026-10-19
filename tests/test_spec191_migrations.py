"""SPEC-191: no public view over app.* may remain without security_invoker."""

import re
from pathlib import Path

MIGRATIONS = sorted(
    Path(__file__).resolve().parents[1].joinpath("supabase", "migrations").glob("*.sql")
)
_VIEW = re.compile(r"create\s+(?:or\s+replace\s+)?view\s+(public\.\w+)(.*?);", re.I | re.S)
_DROP = re.compile(r"drop\s+view\s+(?:if\s+exists\s+)?(public\.\w+)", re.I)


def _final_public_views() -> dict[str, str]:
    views: dict[str, str] = {}
    for path in MIGRATIONS:
        text = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
        for m in sorted(
            [(m.start(), "c", m) for m in _VIEW.finditer(text)]
            + [(m.start(), "d", m) for m in _DROP.finditer(text)],
            key=lambda x: x[0],
        ):
            _, kind, match = m
            if kind == "d":
                views.pop(match.group(1).lower(), None)
            else:
                views[match.group(1).lower()] = match.group(2)
    return views


def test_no_definer_style_public_views_remain():
    bad = [
        n
        for n, body in _final_public_views().items()
        if not re.search(r"security_invoker\s*=\s*(true|on)", body, re.I)
    ]
    assert bad == []


def test_wallet_views_replaced_by_functions():
    text = (MIGRATIONS[-1].parent / "20261015120000_wallet_views_definer_functions.sql").read_text(
        encoding="utf-8"
    )
    for name in ("rpg_wallet_balance", "rpg_wallet_history"):
        assert f"function public.{name}" in text
    assert "security definer set search_path=''" in text
    assert "to authenticated" in text
