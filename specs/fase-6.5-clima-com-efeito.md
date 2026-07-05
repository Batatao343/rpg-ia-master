# SPEC — Fase 6.5: Clima com efeito real — cadeias por região e mecânica

> **Status:** `done` (2026-07-05 — smoke com LLM real executado; ver ESTADO_ATUAL)
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 0 (relógio/período) · 4.2 (condições tipadas) · 6.4 (detecção — clima modifica)
> **Desbloqueia:** fenômenos de campanha (Tempestade de Éter como beat de clímax)

---

## 1. Contexto & Objetivo

`world.weather` existe desde a Fase 0 como STRING decorativa — o storyteller
inventa "chove" e nada muda. Clima de verdade em Valoria é material temático
puro (o Pântano tem miasma, o Deserto tem vendavais de vidro, Aethelgard tem
chuva de Éter) e mecânica barata: já temos condições tipadas (4.2), detecção
(6.4) e viagem com relógio (Fase 0).

Esta spec: **cadeias de clima por região** (transição determinística por período
do relógio, rng semeável), **efeitos mecânicos declarativos** (mesmo vocabulário
`effects` da 4.2 aplicados como modificadores de cena, não condição no corpo) e
**fenômenos globais** raros que o campaign_manager pode invocar em beat de
clímax (única ponte com LLM — validada, é claro).

## 2. Requisitos

- **R1 (dados)** — `data/weather.json`: por REGIÃO, cadeia de estados com pesos
  de transição por período (`{"limpo": {"limpo": 60, "nublado": 30, ...}}`) +
  efeitos por estado. Regiões sem entrada usam `default`. ~6 estados temáticos
  curados (limpo, nublado, chuva, neblina, miasma [pântano], vendaval [deserto/
  montanha], nevasca [skallgard]).
- **R2 (avanço)** — `world_utils.advance_weather(world, rng) -> world`: transição
  na mudança de PERÍODO do relógio (já existe hook de viagem/descanso) — cadeia
  de Markov simples, determinística com rng semeado. `world.weather` continua
  string (compat), `world.weather_state` guarda o id canônico.
- **R3 (efeitos mecânicos)** — cada estado declara `effects` (vocabulário 4.2):
  - `perception_mod` (int): soma no `detection_check` da 6.4 (neblina -3);
  - `travel_cost_extra` (int períodos): vendaval/nevasca encarecem viagem;
  - `combat_mods` `{attack: int}`: aplicado a AMBOS os lados no combate
    (chuva -1 acerto — simétrico, sem favorecer ninguém);
  - `rest_block` (bool): miasma impede descanso seguro ao relento;
  - `dot_outdoor` opcional: miasma denso = 1 dano/turno em combate ao ar livre
    (locais com tag `urbano`/`abrigo` imunes).
- **R4 (aplicação)** — TODOS os consumos são leituras pontuais (função
  `weather_effects(world)`), nunca condição gravada no player — mudou o clima,
  mudou o efeito, zero limpeza de estado.
- **R5 (fenômeno global)** — `campaign_manager` PODE proposear `weather_event`
  estruturado (ex.: "Tempestade de Éter") APENAS de uma lista curada em
  `weather.json[global_events]`; validator rejeita nome fora da lista; aplica
  como estado que SOBREPÕE a região por N períodos e entra no `event_log`
  (auditável, vira milestone da crônica — é raro e épico por construção).
- **R6 (visibilidade)** — HUD: ícone/rótulo do clima no topbar (junto do
  relógio); narrador recebe estado+efeito no context pack; CLI mostra na
  status line.
- **R7** — Offline-testável: cadeias, efeitos, sobreposição global — zero LLM
  além do R5 (que tem validator + guard).

### Fora de escopo

- Clima afetando ECONOMIA (colheita/estoque — encaixa na 6.1 depois).
- Previsão do tempo como habilidade/serviço.
- Estações do ano (só dia/período por ora).
- Clima em combate INDOOR (tag `urbano`/`abrigo`/dungeon anula tudo).

## 3. Design técnico

| Arquivo | Mudança |
|---|---|
| `data/weather.json` | cadeias por região + efeitos + `global_events` curados |
| `world_utils.py` | `advance_weather`, `weather_effects(world, loc)`; hooks em viagem/descanso (rest_block, custo extra) |
| `state.py` | `WorldState.weather_state: str` + `weather_global: Optional[{id, until_day_period}]` |
| `agents/combat.py` | `combat_mods.attack` simétrico nos rolls |
| `world_utils.detection_check` (6.4) | + `perception_mod` |
| `agents/campaign_manager.py` | pode propor `weather_event` (structured output EXISTENTE ganha campo opcional — **dentro do guard**) |
| `services/world_validators.py`/`event_processor`/`chronicle` | `weather_event`: lista curada, aplica sobreposição, milestone |
| `api.py` + `web/` + CLI | rótulo/ícone do clima |
| `tests/test_fase65.py` | suíte |

Formato (`weather.json`, exemplo pântano):

```json
"pantano_melancolia": {
  "states": {
    "neblina": {"label": "Neblina baixa", "perception_mod": -3,
                 "transitions": {"neblina": 50, "miasma": 30, "nublado": 20}},
    "miasma":  {"label": "Miasma denso", "perception_mod": -2,
                 "dot_outdoor": 1, "rest_block": true,
                 "transitions": {"miasma": 40, "neblina": 40, "nublado": 20}}
  },
  "start": "neblina"
}
```

Decisões:
1. **Efeito é leitura, não estado no corpo** (R4) — elimina toda a classe de
   bugs "condição de clima órfã depois que parou de chover".
2. **Combate simétrico** — clima não é buff disfarçado; -1 acerto pra todos.
3. **Global só de lista curada** — LLM escolhe o MOMENTO, nunca inventa o
   fenômeno (mesmo princípio do gate de eventos).

## 4. Plano passo a passo

1. **Etapa 1 (TDD):** dados + `advance_weather` (cadeia semeada, região default,
   troca só em mudança de período).
2. **Etapa 2:** `weather_effects` + consumo em detecção/viagem/descanso
   (rest_block nega descanso ao relento com log claro).
3. **Etapa 3:** combate (attack mod simétrico; dot_outdoor com tag de abrigo).
4. **Etapa 4:** fenômeno global (validator lista curada + guard no campaign_manager
   + milestone); teste de rejeição de fenômeno inventado.
5. **Etapa 5:** HUD/CLI/context pack + suíte completa + build.

## 5. Critérios de aceite

- [ ] Clima transiciona por período segundo a cadeia da REGIÃO (pântano ≠ deserto)
- [ ] Neblina reduz detecção (6.4); nevasca encarece viagem; miasma nega descanso e pinga dano outdoor
- [ ] Chuva: -1 acerto para AMBOS os lados no combate
- [ ] Fenômeno fora da lista curada proposto pelo LLM → rejeitado; da lista → sobrepõe + milestone
- [ ] Parou o clima → efeito some sozinho (nenhuma condição órfã no player)
- [ ] `uv run pytest` verde; saves antigos ok (`weather_state` backfill do string atual ou "limpo")

## 6. Smoke test com LLM real

1. Viajar sob miasma → narração usa o estado (context pack) e o log mecânico.
2. Beat de clímax → campaign_manager propõe (ou não) `weather_event` da lista —
   validar mapeamento do campo novo no Gemini (guard).

(≈ 3 requests.)

## 7. Riscos & compatibilidade

- **Campo novo em structured output do campaign_manager** — guard de FallbackLLM
  obrigatório (isinstance/try — convenção CRÍTICA); MockLLM ganha caso.
- Saves antigos: `weather_state` derivado de `weather` string por matching
  simples, senão "limpo".
- Excesso de modificadores empilhados (clima+condição+passiva) — todos logados
  no log mecânico; narrador explica; playtest calibra números.
