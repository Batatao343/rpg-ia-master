"""SPEC-317 R2: 200 decisoes shadow da rota NPC deterministica com o CLASSIFY real.
Entradas fixadas ANTES de rodar (6 NPCs x 40 falas); nada ajustado depois do resultado.
Uso: r2.py OUT.json [mock]"""

import copy
import json
import os
import random
import sys

sys.path.insert(0, ".")
if len(sys.argv) > 2 and sys.argv[2] == "mock":
    os.environ["RPG_FORCE_MOCK"] = "1"
else:
    os.environ.pop("RPG_FORCE_MOCK", None)
os.environ["RPG_ROUTER_DETERMINISTIC_NPC"] = "shadow"
from langchain_core.messages import AIMessage, HumanMessage

from agents import router
from playtest.runner import _build_initial_state
from services.interlocutor import optional_entity_ref

NPCS = ["Velho Tomás", "Marta", "Capitã Elira", "Irmão Cassiano", "Duda", "Rolando"]
TALK = [
    "{n}, o que você sabe sobre a estrada para o norte?",
    "{n}, bom dia. Como andam as coisas por aqui?",
    "{n}, você viu alguém estranho passar ontem à noite?",
    "{n}, quanto custa um quarto nesta cidade?",
    "{n}, me conta um pouco da sua história.",
    "{n}, há quanto tempo você mora aqui?",
    "{n}, quem manda nesta região hoje?",
    "{n}, o que aconteceu com a ponte velha?",
    "{n}, você conhece alguém que precise de um viajante?",
    "{n}, por que todos parecem tão nervosos?",
    "{n}, obrigado pela informação.",
    "{n}, até mais, cuide-se.",
    "{n}, o que acha da Legião?",
    "{n}, você ouviu algum boato recente?",
    "{n}, onde posso encontrar um ferreiro?",
    "{n}, desculpe incomodar, posso fazer uma pergunta?",
    "{n}, qual é o caminho mais seguro até o porto?",
    "{n}, você acredita nas histórias sobre o Abismo?",
    "{n}, sua família é daqui?",
    "{n}, o que você faria no meu lugar?",
    "Falo com {n} sobre o tempo frio destes dias.",
    "Converso com {n} sobre as colheitas.",
    "Pergunto a {n} se a estalagem ainda está aberta.",
    "Pergunto a {n} o que tem acontecido na cidade.",
    "Falo com {n} e pergunto pelo templo.",
    "Converso com {n} sobre a guerra antiga.",
    "Pergunto a {n} quem é o dono daquela casa grande.",
    "Falo com {n} sobre o mercado de amanhã.",
    "Pergunto a {n} se conhece a Pradaria das Ruínas.",
    "Converso com {n} sobre as festas da estação.",
    "{n}, você pode me ajudar a encontrar o caminho?",
    "{n}, me empresta um pouco de água?",
    "{n}, se eu fosse você não confiaria nesse mercador.",
    "{n}, não minta para mim. O que você escondeu?",
    "{n}, você parece cansado. Está tudo bem?",
    "{n}, você sabe ler este mapa?",
    "{n}, preciso que você guarde um segredo.",
    "{n}, o que se diz sobre mim por aí?",
    "{n}, tem notícias da capital?",
    "{n}, foi um prazer conversar.",
]
out, rows = sys.argv[1], []
logs = []
orig = router._log_event


def spy(agent, event, **kw):
    if event == "deterministic_shadow":
        logs.append(kw)
    return orig(agent, event, **kw)


router._log_event = spy
random.seed(317)
base = _build_initial_state("diplomatico", 317)
for name in NPCS:
    for tpl in TALK:
        st = copy.deepcopy(base)
        key = optional_entity_ref(name) or name
        st["npcs"] = {
            optional_entity_ref(n) or n: {"name": n, "in_scene": True, "relationship": 0}
            for n in NPCS
        }
        text = tpl.format(n=name)
        st["messages"] = list(st.get("messages") or []) + [
            AIMessage(content="A praça está movimentada; vozes se cruzam."),
            HumanMessage(content=text),
        ]
        n0 = len(logs)
        try:
            payload = router.dm_router_node(st)
        except Exception as exc:
            rows.append({"text": text, "error": type(exc).__name__})
            continue
        det = logs[n0] if len(logs) > n0 else None
        rows.append(
            {
                "text": text,
                "npc": key,
                "logged": det is not None,
                "agree": (det or {}).get("agree"),
                "decided_by": (det or {}).get("decided_by"),
                "route": payload.get("next"),
                "target": payload.get("active_npc_name"),
                "social": payload.get("social_intent"),
            }
        )
open(out, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False, indent=1))
lg = [r for r in rows if r.get("logged")]
print(
    json.dumps(
        {
            "inputs": len(rows),
            "decisions": len(lg),
            "agree": sum(1 for r in lg if r["agree"]),
            "rate": round(sum(1 for r in lg if r["agree"]) / max(1, len(lg)), 4),
            "errors": sum(1 for r in rows if r.get("error")),
            "not_deterministic": len(rows) - len(lg),
        }
    )
)
