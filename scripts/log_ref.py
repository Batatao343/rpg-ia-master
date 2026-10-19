"""SPEC-262 R2: pseudonimo (HMAC) de um id para buscar nos logs.

    uv run python scripts/log_ref.py owner  <user-id>
    uv run python scripts/log_ref.py game   <game-id>
    uv run python scripts/log_ref.py action <action-id>

O segredo (``RPG_TELEMETRY_SECRET``) vem do ambiente, de ``.env`` ou de stdin (``--stdin``) —
NUNCA de argumento de linha de comando (apareceria no historico do shell e na lista de processos).
Recusa rodar sem o segredo: o fallback publico de ``pseudonym()`` geraria referencias que nao
batem com as de producao.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"owner": "owner_ref", "game": "game_ref", "action": "action_ref"}


def load_secret(argv: list[str], env: dict[str, str]) -> str | None:
    if "--stdin" in argv:
        return sys.stdin.readline().strip() or None
    secret = env.get("RPG_TELEMETRY_SECRET")
    if secret:
        return secret
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "RPG_TELEMETRY_SECRET" and value.strip():
                return value.strip().strip("'\"")
    return None


def main(argv: list[str], env: dict[str, str] | None = None) -> int:
    env = dict(os.environ if env is None else env)
    if any(arg.startswith("--secret") for arg in argv):
        print("recusado: o segredo nao pode ir por argumento; use RPG_TELEMETRY_SECRET, .env ou --stdin.",
              file=sys.stderr)
        return 2
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2 or args[0] not in FIELDS:
        print("uso: log_ref.py <owner|game|action> <id> [--stdin]", file=sys.stderr)
        return 2
    secret = load_secret(argv, env)
    if not secret or len(secret) < 16:
        print("recusado: RPG_TELEMETRY_SECRET ausente ou curto (use o segredo do ambiente alvo).", file=sys.stderr)
        return 3
    sys.path.insert(0, str(ROOT))
    from observability.telemetry import pseudonym
    raw = args[1].strip()
    try:
        raw = str(uuid.UUID(raw))       # mesma forma canonica usada pelo servidor
    except ValueError:
        pass
    print(f"{FIELDS[args[0]]}={pseudonym(raw, secret=secret)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
