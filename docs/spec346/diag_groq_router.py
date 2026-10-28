"""SPEC-346 Etapa 0: reproduz o HTTP 400 do Groq gpt-oss-20b no schema do router.

Uso: bash scripts/dev/py.sh docs/spec346/diag_groq_router.py [caminho/.env]
Maximo de 5 requests (so a chave GROQ e lida; nenhum valor e impresso).
"""

import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

env_path = sys.argv[1] if len(sys.argv) > 1 else ".env"
key = dotenv_values(env_path).get("GROQ_API_KEY")
if not key:
    sys.exit("sem GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = key
os.environ["RPG_ROUTES"] = json.dumps({"classify": [["groq", "openai/gpt-oss-20b"]]})
os.environ.pop("RPG_FORCE_MOCK", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

import llm_setup  # noqa: E402
from agents.router import RouterDecision  # noqa: E402

events = []
llm_setup.set_llm_attempt_telemetry_hook(events.append)

FALAS = [
    "Saco a espada e ataco o bandido mais proximo",
    "Avanco pela galeria escura com a lamina em punho e ataco a primeira criatura hostil que surgir",
]
sys_msg = "Roteador de RPG. Classifique a intencao da ULTIMA mensagem. COMBAT se o jogador ataca."
budget = 5
for fala in FALAS:
    for _ in range(2):
        if budget <= 0:
            break
        budget -= 1
        llm = llm_setup.get_llm(temperature=0.0, tier=llm_setup.ModelTier.CLASSIFY)
        out = llm.with_structured_output(RouterDecision).invoke(
            [SystemMessage(content=sys_msg), HumanMessage(content=fala)]
        )
        print(type(out).__name__, getattr(out, "route", None))
for ev in events:
    print(
        ev.provider,
        ev.model,
        ev.outcome,
        "http",
        ev.http_status,
        "code",
        ev.provider_error_code,
        "fail",
        ev.structured_failure_code,
        ev.error_type,
    )
