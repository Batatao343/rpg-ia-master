"""SPEC-221 smoke local: A=perfil local (Postgres/Auth Supabase local), B=legacy (save MockLLM p/ export)."""
import json, os, subprocess, sys, time, secrets
from pathlib import Path
import httpx

WT = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
status = json.loads(subprocess.run(["npx.cmd", "--yes", "supabase@2.115.0", "status", "--output", "json"],
                    cwd=r"C:\Users\guilh\OneDrive\Área de Trabalho\rpg-ia-master", text=True,
                    capture_output=True, check=True).stdout)
token = (OUT / "metrics_token").read_text(encoding="ascii").strip()

uvicorn = str(Path(sys.executable).with_name("uvicorn.exe"))
base = os.environ.copy()
base.update({"RPG_FORCE_MOCK": "1", "PYTHONIOENCODING": "utf-8"})
envA = dict(base, RPG_RUNTIME_PROFILE="local",
            DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:55322/postgres",
            SUPABASE_URL=status["API_URL"], SUPABASE_PUBLISHABLE_KEY=status["PUBLISHABLE_KEY"],
            SUPABASE_SERVICE_ROLE_KEY=status["SERVICE_ROLE_KEY"],
            RPG_SESSION_SECRET="local-browser-session-secret-32-chars",
            RPG_METRICS_TOKEN=token, RPG_COOKIE_SECURE="1")
envB = dict(base); envB.pop("RPG_RUNTIME_PROFILE", None); envB.pop("RPG_COOKIE_SECURE", None)
envB.pop("RPG_METRICS_TOKEN", None)
procs = []
for name, env, port in (("A", envA, 8721), ("B", envB, 8722)):
    log = (OUT / f"api{name}.log").open("wb")
    procs.append(subprocess.Popen([uvicorn, "api:app", "--host", "0.0.0.0" if name == "A" else "127.0.0.1",
                                   "--port", str(port)], cwd=WT, env=env, stdout=log, stderr=log))
def wait(port):
    for _ in range(160):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise SystemExit(f"port {port} not healthy")
lines = []
def rec(label, r, keys=()):
    hs = {k: r.headers.get(k) for k in keys}
    lines.append(f"{label}: HTTP {r.status_code} {json.dumps(hs, ensure_ascii=False)}")
try:
    wait(8721); wait(8722)
    A, B = "http://127.0.0.1:8721", "http://127.0.0.1:8722"
    rec("A health profile", httpx.get(A + "/health"))
    lines.append("   " + httpx.get(A + "/health").text[:200])
    rec("1a A GET /metrics sem token", httpx.get(A + "/metrics"))
    rec("1b A GET /metrics token errado", httpx.get(A + "/metrics", headers={"Authorization": "Bearer " + "x" * 48}))
    r = httpx.get(A + "/metrics", headers={"Authorization": f"Bearer {token}"})
    rec("1c A GET /metrics Bearer <token>", r, ("content-type",))
    lines.append("   gauges: " + ", ".join([l for l in r.text.splitlines()
                 if l.startswith(("rpg_metrics_db_error", "rpg_db_pool", "rpg_jobs{"))][:6]))
    rec("2a A GET /game/state (sem sessao)", httpx.get(A + "/game/state"), ("cache-control",))
    rec("2b A GET /account/balance (sem sessao)", httpx.get(A + "/account/balance"), ("cache-control",))
    rec("2c A GET /auth/config", httpx.get(A + "/auth/config"), ("cache-control",))
    rec("2d A GET /data/options", httpx.get(A + "/data/options"), ("cache-control",))
    rec("3a A HEAD / (RPG_COOKIE_SECURE=1)", httpx.head(A + "/"), ("strict-transport-security", "content-security-policy"))
    rec("3b B HEAD / (sem cookie secure)", httpx.head(B + "/"), ("strict-transport-security",))
    import socket
    CRLF = bytes([13, 10])
    sk = socket.create_connection(("127.0.0.1", 8721)); sk.settimeout(10)
    sk.sendall(CRLF.join([b"POST /auth/login HTTP/1.1", b"Host: x", b"Content-Type: application/json",
                          b"Content-Length: 1048576", b"", b""]))  # declara 1 MiB, nao envia o corpo
    data = sk.recv(4096); sk.close()
    lines.append("4a A POST /auth/login Content-Length 1 MiB (corpo nao enviado): "
                 + data.split(CRLF)[0].decode() + " | " + data.split(CRLF + CRLF)[-1].decode())
    import socket
    CRLF = bytes([13, 10])
    sk = socket.create_connection(("127.0.0.1", 8721)); sk.settimeout(10)
    sk.sendall(CRLF.join([b"POST /auth/login HTTP/1.1", b"Host: x", b"Content-Type: application/json",
                          b"Transfer-Encoding: chunked", b"", b""]))
    sent = 0
    try:
        for _ in range(5):
            sk.sendall(b"10000" + CRLF + b"x" * 65536 + CRLF); sent += 65536
        sk.sendall(b"0" + CRLF + CRLF)
    except OSError as e:
        lines.append(f"   (servidor fechou apos {sent} bytes: {e.__class__.__name__})")
    data = b""
    try:
        while b"payload_too_large" not in data:
            chunk = sk.recv(4096)
            if not chunk:
                break
            data += chunk
    except OSError as e:
        lines.append(f"   (recv: {e.__class__.__name__})")
    sk.close()
    status_line = data.split(CRLF)[0].decode(errors="replace")
    tail = data.split(CRLF + CRLF)[-1].decode(errors="replace")[:60]
    lines.append(f"4b A POST /auth/login chunked 320 KiB (sem Content-Length): {status_line} | {tail} | enviados {sent}B")
    rec("4c A POST /auth/login pequeno", httpx.post(A + "/auth/login", json={"email": "a@b.c", "password": "x" * 9}))
    new = httpx.post(B + "/game/new", timeout=120, json={"name": "Ωmega José-Ângelo", "race": "Humano",
        "class_name": "Devoto do Abismo", "region": "Nova Arcádia", "backstory": "teste"})
    lines.append(f"5a B POST /game/new nome unicode: HTTP {new.status_code}")
    gid = new.json().get("game_id") if new.status_code == 200 else None
    r = httpx.get(B + "/game/chronicle/export", params={"game_id": gid} if gid else None)
    rec("5b B GET /game/chronicle/export", r, ("content-disposition", "cache-control"))
    if gid:
        httpx.delete(B + f"/game/save/{gid}")
    # Scrape real (SPEC-106 Prometheus) com bearer
    prom_up = None
    for _ in range(40):
        try:
            q = httpx.get("http://127.0.0.1:59091/api/v1/query", params={"query": 'up{job="valoria-api"}'}, timeout=2).json()
            res = q["data"]["result"]
            if res:
                prom_up = res[0]["value"][1]
                if prom_up == "1":
                    break
        except Exception:
            pass
        time.sleep(1)
    lines.append(f"6  Prometheus up{{job=valoria-api}} = {prom_up}")
    time.sleep(45)  # 2 s de intervalo => ~22 scrapes > 12/min
    q = httpx.get("http://127.0.0.1:59091/api/v1/query", params={"query": 'min_over_time(up{job="valoria-api"}[40s])'}).json()
    n = httpx.get("http://127.0.0.1:59091/api/v1/query", params={"query": 'count_over_time(up{job="valoria-api"}[40s])'}).json()
    lines.append(f"   apos 45 s: min_over_time(up[40s]) = {q['data']['result'][0]['value'][1]}, amostras = {n['data']['result'][0]['value'][1]}")
    try:
        t = httpx.get("http://127.0.0.1:59091/api/v1/targets", timeout=2).json()["data"]["activeTargets"][0]
        lines.append(f"   target health={t['health']} lastError={t['lastError']!r} url={t['scrapeUrl']}")
    except Exception as e:
        lines.append(f"   targets err {e}")
finally:
    for p in procs:
        p.terminate()
    if "--keep" in sys.argv:
        pass
txt = "\n".join(lines).replace(token, "<token>")
(OUT / "smoke.txt").write_text(txt, encoding="utf-8")
print(txt)
