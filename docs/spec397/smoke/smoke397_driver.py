"""SPEC-397 §5 smoke driver (in-process TestClient, LLM real). Usage: python smoke397_driver.py <fase> [out_dir]"""
import json, os, sys, tempfile
FLAGS = json.load(open("scripts/staging/staging_flags.json", encoding="utf-8"))["flags"]
for k, v in FLAGS.items():
    os.environ[k] = str(v)
os.environ.update({"RPG_RUNTIME_PROFILE": "legacy", "RPG_RATE_LIMIT": "0", "RPG_CREATURE_ART": "off",
                   "RPG_DYNAMIC_ART_ENABLED": "0", "RPG_CORS_ORIGINS": "*"})
os.environ.pop("RPG_FORCE_MOCK", None); os.environ.pop("RPG_NO_MOCK", None)
from fastapi.testclient import TestClient
import api, persistence
FARO = "cor1_tro_faro_do_abismo"
OUT = sys.argv[2] if len(sys.argv) > 2 else "out"
os.makedirs(OUT, exist_ok=True)
c = TestClient(api.app)

def new(name):
    r = c.post("/game/new", json={"name": name, "race": "Humano", "class_name": "Corruptor",
               "region": "Nova Arcádia", "level": 1, "backstory": ""})
    assert r.status_code == 200, r.text
    return r.json()["game_id"]
def load(g): return persistence.load_game_state(persistence.save_path(g))
def save(s): assert persistence.save_game_state(s)
def ambush(g, mutate):
    s = load(g); mutate(s["player"]); s["world"]["encounter_surprise"] = "enemy"; save(s)
def act(g, text="Ataco o goblin"):
    r = c.post("/game/action", json={"game_id": g, "input_text": text})
    assert r.status_code == 200, r.text
    return r.json()
def summary(g, resp):
    s = load(g); cb = s.get("combat") or {}; p = s["player"]
    msgs = [getattr(m, "content", str(m)) for m in s.get("messages", [])]
    return {"game_id": g, "resp_keys": sorted(resp.keys()),
            "combat_active": cb.get("active"), "phase": cb.get("phase"), "round": cb.get("round"),
            "initiator": cb.get("initiator"), "initiator_reason": cb.get("initiator_reason"),
            "prepared_cards": p.get("prepared_cards"), "deck": p.get("deck"),
            "faro_known": FARO in (p.get("known_cards") or []),
            "enemies": [e.get("name") for e in s.get("enemies") or []],
            "abertura": msgs[-1] if msgs else None,
            "response_message": resp.get("message") or resp.get("response") or resp.get("narrative")}
def dump(name, d):
    json.dump(d, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(d, ensure_ascii=False, indent=1, default=str)[:3500])

fase = sys.argv[1]
if fase == "2a":
    g = new("Smoke397a")
    def m(p):
        for k in ("known_cards", "prepared_cards", "deck"):
            if k == "deck" and k not in p: continue
            lst = p.setdefault(k, [])
            if FARO not in lst: lst.append(FARO)
    ambush(g, m)
    dump("2a.json", summary(g, act(g)))
elif fase == "2b":
    g = new("Smoke397b")
    def m(p):
        for k in ("known_cards", "prepared_cards", "deck"):
            if k in p: p[k] = [x for x in p[k] if x != FARO]
        assert FARO not in json.dumps(p.get("known_cards")) 
    ambush(g, m)
    dump("2b.json", summary(g, act(g)))
elif fase == "3":
    g = new("Smoke397c")
    s = load(g); p = s["player"]
    antes = {"prepared": list(p.get("prepared_cards") or []), "level": p.get("level"), "known": list(p.get("known_cards") or [])}
    p["espolio_pendente"] = {"id": "c1", "ofertas": [FARO], "origem": "vitoria", "turno": 1, "recusa_ouro": 15}
    save(s)
    from services import card_rewards
    pend = card_rewards.public_pending(load(g)["player"])
    vw = c.get("/game/state", params={"game_id": g}).json().get("espolio_pendente")
    r = c.post("/game/espolio", json={"game_id": g, "card_id": FARO})
    body = r.json()
    p2 = load(g)["player"]
    cards = [x for x in (body.get("player_stats", {}) or {}).get("cards", []) if x.get("id") == FARO]
    ev = {"antes": antes, "oferta_antes_de_aceitar": pend, "espolio_pendente_na_API": vw, "status": r.status_code, "resp_keys": sorted(body.keys()),
          "message": body.get("message"), "prepared_depois": p2.get("prepared_cards"),
          "n_prepared": len(p2.get("prepared_cards") or []), "faro_in_prepared": FARO in (p2.get("prepared_cards") or []),
          "faro_in_deck": FARO in (p2.get("deck") or []), "faro_known": FARO in p2.get("known_cards", []),
          "faro_card_in_response": cards,
          "body_excerpt": json.dumps(body, ensure_ascii=False, default=str)[:1500]}
    dump("3-espolio.json", ev)
    ambush(g, lambda p: None)
    dump("3-emboscada.json", summary(g, act(g)))
