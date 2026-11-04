"""SPEC-389 R5: mede por que `retrato.gerar` some no staging, dentro da retencao dos logs da Vercel.

Numa so execucao (<= 15 min): (1) grava o estado dos kill switches (`list` + 5 linhas do `audit`);
(2) faz N leituras de `GET /game/state?game_id=...` pelo cliente da API e N carregamentos do navegador
(Playwright, larguras do §6), registrando hora, `X-Request-ID`, `x-vercel-id`, hash curto do jogo,
endpoint e se `gerar` veio; (3) baixa os logs da janela (`vercel logs --json`) e junta cada amostra ao
seu `creature_portrait.offer_view` pelo `request_id`; (4) grava `docs/spec389/offer-measure-<hora>.json`.

Controle positivo: se alguma amostra ficar sem `offer_view`, o script FALHA (sem linha, o problema e o
log, nao a oferta). Saida sem segredo, cookie nem id de jogo (so hash curto).

Uso (cookie da sessao sintetica em PORTRAIT_MEASURE_COOKIE, nunca em argv):
  python -m scripts.staging.portrait_offer_measure --base https://... --game-id <id> \
      --storage-state state.json --api-reads 6 --widths 1440,390,1440,1280,1440,390
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
EVENT = "creature_portrait.offer_view"


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def parse_logs(stdout: str) -> list[dict[str, Any]]:
    """Linhas `offer_view` do `vercel logs --json` (so campos do evento + ts + request_id do payload)."""
    rows: list[dict[str, Any]] = []
    for line in (stdout or "").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        data = item.get("data", item) if isinstance(item, dict) else {}
        message = str(data.get("message") or "")
        start = message.find("{")
        if start < 0 or EVENT not in message:
            continue
        try:
            payload = json.loads(message[start:])
        except ValueError:
            continue
        if payload.get("event") == EVENT:
            rows.append(payload)
    return rows


def join_samples(samples: list[dict[str, Any]], logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Junta por `request_id` (X-Request-ID da resposta == `request_id` da correlacao do log)."""
    by_id: dict[str, dict[str, Any]] = {}
    for log in logs:
        rid = str(log.get("request_id") or "")
        if rid:
            by_id.setdefault(rid, log)
    out = []
    for sample in samples:
        log = by_id.get(str(sample.get("request_id") or ""))
        view = (
            {
                k: log.get(k)
                for k in (
                    "instance",
                    "game_ref",
                    "offered",
                    "omitted",
                    "switch_age_s",
                    "price_cached",
                    "art_live",
                )
            }
            if log
            else None
        )
        out.append({**sample, "offer_view": view})
    return out


def missing_views(joined: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in joined if s.get("offer_view") is None]


def summarize(joined: list[dict[str, Any]]) -> dict[str, Any]:
    per_instance: dict[str, Counter] = {}
    causes: Counter = Counter()
    for sample in joined:
        view = sample.get("offer_view") or {}
        inst = str(view.get("instance") or "?")
        counter = per_instance.setdefault(inst, Counter())
        counter["samples"] += 1
        counter["offered"] += 1 if sample.get("gerar") else 0
        for cause, n in (view.get("omitted") or {}).items():
            counter[f"omitted:{cause}"] += n
            causes[cause] += n
    return {
        "samples": len(joined),
        "with_offer": sum(1 for s in joined if s.get("gerar")),
        "causes": dict(causes),
        "per_instance": {k: dict(v) for k, v in per_instance.items()},
        "games": sorted(  # R7: que jogo cada lado leu (hash do corpo x game_ref do log)
            {
                (
                    str(s.get("kind", "")).split(":")[0],
                    str(s.get("game")),
                    str((s.get("offer_view") or {}).get("game_ref")),
                )
                for s in joined
            }
        ),
    }


def collect_api(base: str, game_id: str, reads: int, cookie: str) -> list[dict[str, Any]]:
    import httpx

    samples = []
    with httpx.Client(timeout=60, headers={"Cookie": cookie}) as client:
        for _ in range(reads):
            resp = client.get(f"{base}/game/state", params={"game_id": game_id})
            body = resp.json() if resp.status_code == 200 else {}
            samples.append(sample_from("api", str(resp.url), resp.headers, resp.status_code, body))
            time.sleep(1)
    return samples


def collect_browser(base: str, widths: list[int], storage_state: str) -> list[dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    samples = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in widths:
            ctx = browser.new_context(
                viewport={"width": width, "height": 900}, storage_state=storage_state
            )
            page = ctx.new_page()
            seen: list[Any] = []
            page.on(
                "response", lambda r, bag=seen: bag.append(r) if "/game/state" in r.url else None
            )
            page.goto(base, wait_until="networkidle")
            for resp in seen[-1:]:  # sem resposta = sem amostra: `count_problems` reprova
                body = resp.json() if resp.ok else {}
                samples.append(
                    sample_from(f"browser:{width}", resp.url, resp.headers, resp.status, body)
                )
            ctx.close()
        browser.close()
    return samples


def _gerar_present(body: dict[str, Any]) -> bool:
    enemies = ((body.get("combat") or {}).get("enemies")) or []
    return any(((e.get("retrato") or {}).get("gerar")) for e in enemies if isinstance(e, dict))


def sample_from(kind: str, url: str, headers: Any, status: int, body: dict) -> dict[str, Any]:
    """Amostra com o jogo REAL da resposta (`game_id` do corpo) e o path real (sem query)."""
    body = body if isinstance(body, dict) else {}
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "kind": kind,
        "endpoint": urlsplit(url).path,
        "status": status,
        "request_id": headers.get("x-request-id", ""),
        "vercel_id": headers.get("x-vercel-id", ""),
        "game": short_hash(str(body.get("game_id") or "")),
        "gerar": _gerar_present(body),
    }


def count_problems(samples: list[dict[str, Any]], api_reads: int, browser_loads: int) -> list[str]:
    """Controle positivo do lado do cliente: contagem minima por lado e status 200."""
    api = [s for s in samples if s.get("kind") == "api"]
    web = [s for s in samples if str(s.get("kind", "")).startswith("browser")]
    problems = []
    if len(api) != api_reads:
        problems.append(f"api: {len(api)}/{api_reads} amostras")
    if len(web) != browser_loads:
        problems.append(f"navegador: {len(web)}/{browser_loads} amostras")
    bad = [s for s in samples if s.get("status") != 200]
    if bad:
        problems.append(f"{len(bad)} amostra(s) com status != 200")
    return problems


STAGING_DSN_ENV = "RPG_STAGING_DB_URL"  # como `incident_drill.py`
STAGING_ENV_FILE = ".env.staging"
SWITCH_KEY = "image_generation"


def switches_snapshot(run: Any = subprocess.run) -> dict[str, Any]:
    """Estado de `image_generation` (list) + 5 ultimas linhas do `audit` DELA, com hora do `on`.
    Sem `actor_id`/`reason`. Falha (RuntimeError) se o snapshot nao vier."""
    base = [
        sys.executable,
        str(ROOT / "scripts" / "admin_kill_switch.py"),
        "--dsn-env",
        STAGING_DSN_ENV,
        "--env-file",
        STAGING_ENV_FILE,
    ]
    out: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds")}
    parsed = {}
    for cmd, extra in (("list", []), ("audit", ["--limit", "50"])):
        proc = run([*base, cmd, *extra], capture_output=True, text=True, timeout=120, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"admin_kill_switch {cmd} falhou (rc={proc.returncode})")
        try:
            parsed[cmd] = json.loads(proc.stdout)
        except ValueError as exc:
            raise RuntimeError(f"admin_kill_switch {cmd}: saida invalida") from exc
    out[SWITCH_KEY] = parsed["list"].get(SWITCH_KEY, "default-on")
    rows = [r for r in parsed["audit"] if r.get("key") == SWITCH_KEY][:5]
    keep = ("key", "previous_enabled", "enabled", "created_at")
    out["audit"] = [{k: r.get(k) for k in keep} for r in rows]
    return out


def fetch_logs(since: str) -> str:
    from scripts.staging import s192

    env = s192.load_env()
    proc = s192.vercel(
        [
            "logs",
            "--environment",
            "production",
            "--since",
            since,
            "--query",
            EVENT,
            "--limit",
            "1000",
            "--json",
        ],
        env,
        timeout=300,
    )
    return proc.stdout or ""


def run(args: argparse.Namespace) -> dict[str, Any]:
    cookie = os.environ.get("PORTRAIT_MEASURE_COOKIE", "")
    result: dict[str, Any] = {"switches": switches_snapshot()}
    widths = [int(w) for w in args.widths.split(",") if w.strip()]
    samples = collect_api(args.base, args.game_id, args.api_reads, cookie)
    if widths and args.storage_state:
        samples += collect_browser(args.base, widths, args.storage_state)
    joined = join_samples(
        samples, parse_logs(fetch_logs(args.since))
    )  # mesma execucao: retencao curta
    result.update(
        samples=joined,
        summary=summarize(joined),
        missing=len(missing_views(joined)),
        problems=count_problems(samples, args.api_reads, len(widths)),
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--storage-state", default="")
    parser.add_argument("--api-reads", type=int, default=6)
    parser.add_argument("--widths", default="1440,390,1440,1280,1440,390")
    parser.add_argument("--since", default="20m")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    result = run(args)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = Path(args.out) if args.out else ROOT / "docs" / "spec389" / f"offer-measure-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    if result["problems"]:
        print("FALHA: " + "; ".join(result["problems"]))
        return 1
    if result["missing"]:
        print(
            f"FALHA: {result['missing']} amostra(s) sem offer_view (problema de log, nao de oferta)"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
