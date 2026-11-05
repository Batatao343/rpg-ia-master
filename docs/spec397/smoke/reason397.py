import json, os, glob, copy
os.environ.update({"RPG_CARD_DECK":"on","RPG_CARD_REWARDS":"on","RPG_RUNTIME_PROFILE":"legacy"})
import persistence
from services import card_rewards
FARO="cor1_tro_faro_do_abismo"
gid=json.load(open("out/3-emboscada.json",encoding="utf-8"))["game_id"]
s=persistence.load_game_state(persistence.save_path(gid)); p=copy.deepcopy(s["player"])
p["known_cards"]=[x for x in p["known_cards"] if x!=FARO]
p["espolio_pendente"]={"id":"c1","ofertas":[FARO],"origem":"vitoria","turno":1,"recusa_ouro":15}
out={"acervo_reason_antes":card_rewards.acervo_reason(p,FARO),"prepared_antes":len(p["prepared_cards"])}
r=card_rewards.accept({"player":p,"world":s.get("world",{})},FARO)
out["accept_return"]={k:r.get(k) for k in ("ok","destino","motivo","log")}
out["prepared_depois"]=len(p["prepared_cards"]); out["faro_in_prepared"]=FARO in p["prepared_cards"]
json.dump(out,open("out/3-motivo.json","w",encoding="utf-8"),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False))
