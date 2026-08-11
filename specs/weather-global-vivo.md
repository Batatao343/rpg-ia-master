# SPEC — Weather global vivo (fenômenos sistêmicos determinísticos)

> **Status:** `done`
> **Criada:** 2026-07-19 · **Atualizada:** 2026-08-02
> **Depende de:** Fase 6.5 (clima local) `done`
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Auditoria de mecânica-morta (2026-07-19) achou `world_utils.trigger_global_weather`
**sem callsite de produção** — a máquina de clima GLOBAL estava 90% pronta mas
nada a acionava: `advance_weather` já **tica/expira** o `weather_global` e
`weather_effects` já **aplica** os efeitos (perception/combat/dot/rest_block/
travel_cost) por cima do clima local, mas nenhum evento global jamais começava
em jogo (só nos testes). Pedido do usuário: "queria que tivesse, acho bem legal
ter e que impactasse no jogo."

Alinhado ao princípio "mecânica é Python": o gatilho é **determinístico** (nada
de canal LLM — o docstring antigo pedia LLM; descartado). Fenômenos globais
(`data/weather.json:global_events`: Tempestade de Éter, Noite Sem Estrelas) são
eventos raros que varrem Valoria por alguns períodos, sobrepondo o clima local.

## 2. Requisitos

- **R1 — Trigger sistêmico determinístico.** Em cada mudança de PERÍODO
  (`advance_weather`, já chamado em viagem/descanso/combate), SEM evento global
  ativo, há chance de iniciar um — via o `rng` recebido (reprodutível). Chance
  base + escala por `danger_level`.
- **R2 — Sem sobreposição.** Enquanto um evento global está ativo
  (`weather_global` setado), NÃO inicia outro (só rola quando o campo é None
  após o tick).
- **R3 — Impacto real (já fiado, garantir).** O evento iniciado aparece em
  `weather_effects` (label + modificadores) e portanto afeta combate
  (`combat_attack_mod`), percepção/encontros (`perception_mod`), descanso
  (`rest_block`) e viagem (`travel_cost_extra`) — como o clima local.
- **R4 — Expira sozinho.** `periods_left` decrementa a cada período
  (comportamento existente); ao zerar, volta a None e pode rolar de novo.
- **R5 — Chance tunável e marcada `[BALANCEAR]`.** Constantes no módulo, não
  mágicas espalhadas.

### Fora de escopo

- Canal LLM p/ o narrador escolher o evento (descartado — é Python).
- Novos eventos globais em `weather.json` (usar os 2 existentes; autoria de
  conteúdo é outro fluxo).
- Elegibilidade por região/estação (os 2 eventos valem em qualquer lugar; se um
  dia precisar, cada `global_event` ganha `regions:[...]` e o pick filtra).
- Gancho de clímax de campanha (podia coexistir; fica p/ depois se quiserem).

## 3. Design técnico

**Arquivo alterado:** `world_utils.py`
- Constantes:
  ```python
  GLOBAL_WEATHER_BASE_CHANCE = 0.06   # [BALANCEAR] por período sem evento ativo
  GLOBAL_WEATHER_DANGER_STEP = 0.03   # [BALANCEAR] +chance por nível de perigo >1
  ```
- Nova função:
  ```python
  def maybe_start_global_weather(world: dict, rng=None) -> Optional[str]:
      """R1/R2: sem evento global ativo, rola p/ iniciar um (chance escala com
      danger_level). Determinístico via rng. Retorna a desc do evento iniciado
      ou None. Reusa trigger_global_weather p/ setar o estado."""
  ```
- `advance_weather` chama `maybe_start_global_weather(world, rng)` DEPOIS do tick
  de expiração (quando `weather_global` já é None). Retorno inalterado (`world`).

## 4. Plano passo a passo

### Etapa 1 — Trigger determinístico (testes primeiro)

1. **Testes** (`tests/test_weather_global.py`):
   - `test_inicia_com_rng_favoravel` — rng forçando abaixo da chance → evento
     global setado, `periods_left` = duration do evento.
   - `test_nao_inicia_com_rng_alto` — rng acima da chance → `weather_global` None.
   - `test_nao_sobrepoe_ativo` — com evento ativo, `advance_weather` decrementa
     mas NÃO troca de evento (R2).
   - `test_chance_escala_com_danger` — danger 4 > danger 1 (mesma seed, mais
     inícios em N amostras).
   - `test_evento_afeta_weather_effects` — evento iniciado aparece em
     `weather_effects` (label + um modificador não-zero) (R3).
   - `test_expira_e_pode_reiniciar` — após `periods_left` períodos volta a None (R4).
2. **Implementação:** constantes + `maybe_start_global_weather` + chamada em
   `advance_weather`.
3. **Verificação:** `uv run pytest` verde.

## 5. Critérios de aceite

- [x] Evento global inicia sozinho em jogo (viagem/descanso/combate) de forma
  reprodutível por seed
- [x] Não sobrepõe evento ativo; expira sozinho
- [x] Efeitos do evento afetam combate/percepção/descanso/viagem
- [x] Chance tunável marcada `[BALANCEAR]`
- [x] `uv run pytest` verde (suíte completa offline)
- [x] Guard de FallbackLLM: N/A (zero structured output)
- [x] Saves antigos continuam carregando (campo `weather_global` já existe no schema)

## 6. Smoke test com LLM real

1. Jogar viajando/descansando várias vezes até um evento global iniciar
   (ou baixar `GLOBAL_WEATHER_BASE_CHANCE` temporariamente p/ forçar) → a
   narração/HUD mostram o clima global e o combate/percepção sentem o modificador.
   (Determinístico — o smoke é confirmação de que o label chega ao narrador.)

## 7. Riscos & compatibilidade

- **Saves antigos:** `weather_global` já é campo do schema (`state.py`); ausente
  = None = sem evento. Sem migração.
- **MockLLM/FallbackLLM:** N/A (puro Python).
- **Determinismo do playtest:** o roll usa o `rng` do turno — reprodutível; o
  harness de playtest não quebra (o campo entra na telemetria de estado se
  desejado, mas não é obrigatório).
- **Frequência:** base 6%/período (+3%/perigo) → evento raro mas presente; se
  incomodar, é só baixar a constante.

## 8. Registro de execução (2026-08-02)

- O trigger, a expiração e os modificadores determinísticos foram revalidados.
- A auditoria do smoke encontrou que o modificador de acerto chegava ao motor
  legado, mas não à resolução v4. `agents/combat.py`, `conflict_turn.py` e
  `conflict_orchestrator.py` agora aplicam clima/luz no total real do ataque.
- A API expõe o rótulo global efetivo e o storyteller recebe
  `<CLIMA_GLOBAL>`, inclusive no fallback seguro de structured output.
- Smoke real forçado com **Tempestade de Éter** confirmou os modificadores
  (`perception=-3`, `attack=-1`, `dot_outdoor=1`) e uma narração que descreveu o
  fenômeno cobrindo Valoria de horizonte a horizonte.
- Suíte integral: **1.313 passed, 1 skipped, 14 deselected**.
