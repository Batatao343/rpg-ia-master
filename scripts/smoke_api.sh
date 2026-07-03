#!/usr/bin/env bash
# smoke_api.sh — smoke test da API REST (health, options, map, /game/new, /game/action).
# Uso:  bash scripts/smoke_api.sh [porta]     (default 8000)
# Requer a API já rodando:  uv run uvicorn api:app --port <porta>
# Sem GOOGLE_API_KEY roda no MockLLM — serve para validar fluxo, não narrativa.
set -u
PORT="${1:-8000}"
BASE="http://localhost:${PORT}"
FAIL=0

check() { # check <nome> <esperado> <obtido>
  if [ "$2" = "$3" ]; then echo "OK   $1"; else echo "FAIL $1 (esperado=$2 obtido=$3)"; FAIL=1; fi
}

# 1. health (espera API subir, até 20s)
code=""
for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health" 2>/dev/null)
  [ "$code" = "200" ] && break
  sleep 1
done
check "GET /health" 200 "$code"
[ "$code" != "200" ] && { echo "API não respondeu em $BASE — suba com: uv run uvicorn api:app --port $PORT"; exit 1; }

# 2. dados estáticos
check "GET /data/options" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/data/options")"
check "GET /data/map"     200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/data/map")"

# 3. novo jogo (payload = CreateCharacterRequest)
new=$(curl -s -X POST "$BASE/game/new" -H "Content-Type: application/json" -d '{
  "name": "Smoke", "race": "Humano", "class_name": "Guerreiro",
  "region": "Nova Arcádia", "level": 1, "backstory": "smoke test"
}')
game_id=$(printf '%s' "$new" | python -c "import sys,json;print(json.load(sys.stdin).get('game_id',''))" 2>/dev/null)
[ -n "$game_id" ] && echo "OK   POST /game/new (game_id=$game_id)" || { echo "FAIL POST /game/new: $(printf '%s' "$new" | head -c 200)"; FAIL=1; }

# 4. estado + 1 turno de ação (payload = ActionRequest)
if [ -n "$game_id" ]; then
  check "GET /game/state" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/game/state?game_id=$game_id")"
  act=$(curl -s -X POST "$BASE/game/action" -H "Content-Type: application/json" \
        -d "{\"input_text\": \"olho ao redor\", \"game_id\": \"$game_id\"}")
  msg=$(printf '%s' "$act" | python -c "import sys,json;d=json.load(sys.stdin);print(len(d.get('message','')))" 2>/dev/null)
  [ -n "$msg" ] && [ "$msg" -gt 0 ] && echo "OK   POST /game/action (narrativa ${msg} chars)" || { echo "FAIL POST /game/action: $(printf '%s' "$act" | head -c 200)"; FAIL=1; }
  # limpeza: save + memória de sessão do smoke
  rm -f "saves/${game_id}.json"
  rm -rf "data/saves_memory/${game_id}"
fi

[ "$FAIL" = "0" ] && echo "SMOKE OK" || echo "SMOKE COM FALHAS"
exit "$FAIL"
