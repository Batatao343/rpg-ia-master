# SPEC — Fase 5.1 — Harness de playtest agêntico + 10 perfis de jogador

> **Status:** `draft`
> **Criada:** 2026-07-06 · **Atualizada:** 2026-07-06
> **Depende de:** motor estável (Fases 0–7, 10, 11 `done`); MockLLM da suíte;
> **roteamento-multi-provider `done`** (playtest roda sobre as rotas novas; o
> `TurnRecord` captura provider/modelo via hook de telemetria do roteamento)
> **Desbloqueia:** 5.2 (invariantes), 5.3 (telemetria/relatório)

---

## 1. Contexto & Objetivo

Todo bug de integração até hoje foi achado por smoke MANUAL (4 na Fase 4, 3 na
Fase 6, 1 na 11) — caro, não-repetível e limitado a poucos turnos. O motor
inteiro roda offline com MockLLM (`app.invoke(state)` — mesmo caminho da API),
então campanhas longas automatizadas custam ZERO de quota e acham o que só
aparece no turno 30: estado corrompido acumulado, loop de replan, inventário
duplicado, morte sem fecho.

Esta spec cria o **harness**: um runner que joga N turnos de campanha
programaticamente e **10 perfis de jogador determinísticos** (políticas
heurísticas em Python — SEM LLM decidindo ação; seed reproduz a campanha
inteira). O perfil gera o texto de ação do próximo turno olhando o estado
(igual um jogador olha a tela). LLM real é OPT-IN (`--real`, poucos turnos,
consciente de quota).

Princípio: **mecânica é Python** — o testador também. Um perfil é uma função
`(estado, rng) -> str`, auditável e re-rodável.

## 2. Requisitos

- **R1 — Runner:** `playtest/runner.py` — `run_campaign(profile, turns, seed,
  use_real_llm=False) -> CampaignResult`. Cria personagem (wizard programático,
  mesmo caminho de `/game/new`), roda `turns` turnos via `app.invoke`, salva a
  cada turno (mesmo fluxo da API). `RPG_FORCE_MOCK=1` a menos que
  `use_real_llm`.
- **R2 — Perfis (10):** `playtest/profiles.py` — cada perfil é classe/função
  pura com `next_action(state, rng) -> str`:
  `agressivo` (ataca tudo que a narração menciona), `explorador` (viaja
  sistematicamente pelo grafo, entra em interiores), `comerciante` (compra/
  vende/crafta em todo mercador), `diplomatico` (fala com todo NPC em cena,
  recruta), `troll` (inputs absurdos/injeção: "ignore as instruções", emoji,
  10k chars), `mapa_breaker` (tenta viajar p/ locais desconexos/inexistentes),
  `combate` (provoca encontros: viaja por danger alto, descansa em ermo),
  `npc_only` (só conversa, inclusive com NPC fora de cena), `loot_abuser`
  (loot/craft/compra repetidos, tenta duplicar item único), `secret_rusher`
  (pergunta diretamente pelos segredos do mundo: pacto de Valerius, Rede
  Carmesim, identidade do Arauto).
- **R3 — Determinismo:** mesmo `(profile, seed, turns)` com MockLLM → mesma
  sequência de ações. RNG do perfil é `random.Random(seed)` próprio (não polui
  o RNG global do combate).
- **R4 — CampaignResult:** dataclass — `turns_completed`, `errors:
  list[{turn, exc, action}]` (exceção NÃO derruba a campanha: registra e
  segue), `final_state`, `save_path`, `history: list[{turn, action, route,
  latency_ms}]`.
- **R5 — CLI:** `uv run python -m playtest run --profile explorador --turns 50
  --seed 42 [--real] [--all]` — `--all` roda os 10 perfis em sequência;
  imprime resumo por campanha (turnos, erros, rota mais usada).
- **R6 — Suíte:** teste offline roda 1 campanha curta (10 turnos, perfil
  `explorador`, seed fixa) e asserta `errors == []` — smoke automatizado
  PERMANENTE dentro do pytest (barato: MockLLM).
- **R7 — Saves isolados:** campanhas de playtest usam `game_id` UUID normal
  mas prefixo de diretório próprio (`saves_playtest/` via env/monkeypatch) —
  não poluem `saves/` do jogador.

### Fora de escopo

- Invariantes de estado (HP válido, dupe...) → **5.2** (o runner só expõe o
  hook `on_turn_end`).
- Telemetria agregada/relatório → **5.3**.
- Perfil movido a LLM ("jogador de verdade") — heurística basta p/ cobertura
  mecânica; LLM-player é experimento futuro.
- Paralelismo — campanhas rodam em série (estado global de caches).

## 3. Design técnico

### Arquivos novos

- `playtest/__init__.py`, `playtest/__main__.py` (CLI fino)
- `playtest/runner.py` — `run_campaign`, `CampaignResult`, criação de personagem
- `playtest/profiles.py` — `PROFILES: dict[str, Profile]`
- `tests/test_fase51.py`

### Assinaturas

```python
# playtest/profiles.py
class Profile(Protocol):
    name: str
    def next_action(self, state: dict, rng: random.Random) -> str: ...

PROFILES: Dict[str, Profile]  # os 10 do R2

# playtest/runner.py
@dataclass
class TurnRecord:
    turn: int; action: str; route: str; latency_ms: int
    # roteamento-multi-provider: qual provider/modelo/tier serviu o turno
    # (via set_llm_telemetry_hook). None no MockLLM. `route` = rota do GRAFO
    # (storyteller/combat/...), NÃO o tier — não confundir.
    provider: Optional[str] = None; model: Optional[str] = None
    tier: Optional[str] = None; fell_back: bool = False

@dataclass
class CampaignResult:
    profile: str; seed: int; turns_completed: int
    errors: List[dict]; history: List[TurnRecord]
    final_state: dict; save_path: str

def run_campaign(profile: str, turns: int = 50, seed: int = 0,
                 use_real_llm: bool = False,
                 on_turn_end: Optional[Callable[[dict, int], None]] = None
                 ) -> CampaignResult: ...
```

Perfis leem o estado como um jogador leria a tela: última AIMessage, HUD
(`player`, `combat`, `world.interiors`, `npcs` in_scene), e escolhem a ação.
Ex.: `explorador` mantém conjunto de visitados e escolhe a conexão não
visitada mais próxima (BFS no `world_map`); `comerciante` alterna
"vou até <mercador do local>" / "compro X" / "vendo Y".

### Hook p/ 5.2

`on_turn_end(state, turn)` roda após cada turno; 5.2 pluga os invariantes ali.
Exceção do hook conta como erro da campanha (é violação, não crash).

## 4. Plano passo a passo

### Etapa 1 — Runner mínimo + perfil explorador

1. **Testes** (`tests/test_fase51.py`): `test_campanha_10_turnos_sem_erros`
   (R6); `test_determinismo_mesma_seed` (2 runs → mesma lista de ações);
   `test_erro_de_turno_nao_derruba_campanha` (monkeypatch num nó que levanta
   no turno 3 → campanha completa com 1 erro registrado);
   `test_saves_em_diretorio_isolado`.
2. **Implementação:** runner + criação de personagem + perfil `explorador`.
3. **Verificação:** `/qa` verde.

### Etapa 2 — Os outros 9 perfis

1. **Testes:** `test_todos_perfis_rodam_5_turnos` (paramétrico, MockLLM,
   errors == []); `test_troll_nao_quebra_router` (inputs absurdos → turno
   completa); `test_mapa_breaker_nao_teleporta` (local final sempre existe no
   grafo e é alcançável).
2. **Implementação:** perfis restantes.
3. **Verificação:** `/qa` verde.

### Etapa 3 — CLI + doc

1. **Testes:** `test_cli_run_devolve_exit_0` (subprocess, 3 turnos).
2. **Implementação:** `__main__.py` + resumo impresso; nota no CLAUDE.md
   (comandos essenciais).
3. **Verificação:** `uv run pytest` completo verde; rodar na mão
   `--profile explorador --turns 50` e ler o resumo.

## 5. Critérios de aceite

- [ ] 10 perfis rodam 50 turnos com MockLLM sem exceção não-capturada
- [ ] Mesma seed → mesma campanha (determinismo)
- [ ] Teste permanente na suíte (10 turnos explorador) verde
- [ ] Saves de playtest não tocam `saves/`
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM — N/A (perfis não usam LLM)
- [ ] Saves antigos continuam carregando (nada de schema muda)

## 6. Smoke test com LLM real

(consciente de quota: 1 campanha CURTA)

1. `uv run python -m playtest run --profile diplomatico --turns 4 --real` →
   campanha completa, resumo coerente, zero erro; conferir que respostas são
   do Gemini (não MockLLM) no save.

## 7. Riscos & compatibilidade

- **Estado global entre campanhas** (caches de gamedata/graph_resolver,
  npc_database.json compartilhado): runner limpa caches conhecidos entre
  campanhas (`clear_cache`, `clear_codex_index_cache`); npc_database é cache
  legítimo (dedupe global) — aceito.
- **MockLLM é repetitivo:** perfis não dependem de variedade narrativa — agem
  sobre estado mecânico; cobertura narrativa real fica pro smoke `--real`.
- **Campanha de 50 turnos ~minutos:** fora da suíte default (só a de 10 turnos
  entra no pytest).
- **Saves antigos / quota:** sem impacto; `--real` é opt-in.
