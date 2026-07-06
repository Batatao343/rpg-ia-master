# SPEC — Roteamento multi-provider com fallback (produto)

> **Status:** `draft`
> **Criada:** 2026-07-06 · **Atualizada:** 2026-07-06
> **Depende de:** motor estável (Fases 0–7, 10, 11 `done`); `llm_setup.py`,
> Fase 11 (contratos `-m llm_contract` — reusados/estendidos por provider)
> **Desbloqueia:** Fase 5 (playtest + telemetria rodam SOBRE o roteamento novo;
> 5.3 mede provider/modelo/custo por turno)

---

## 1. Contexto & Objetivo

Hoje `llm_setup.py` tem 2 tiers (`FAST`/`SMART`) e escolhe o provider por UM
env global (`LLM_PROVIDER`). O tier só troca o modelo DENTRO daquele provider.
Isso trava três coisas que um **produto pago** precisa:

1. **Granularidade de custo/latência.** Router e parse estruturado rodam TODO
   turno e só classificam 4 rótulos — não precisam do modelo caro que a
   narração usa. Falta um tier baixo dedicado. Narração é output-heavy e hoje
   cai no `gemini-flash-latest` (~$9/1M output) quando modelos equivalentes
   custam $1.20.
2. **Mistura de providers por tier.** Não dá pra classificar no Groq (latência
   mínima), narrar no MiniMax/Qwen (prosa barata) e planejar campanha no Kimi/
   Sonnet (coerência) ao mesmo tempo.
3. **Robustez.** `max_retries=0` (fail-fast) é certo pro MESMO modelo (429 de
   quota não é transitório), mas não há queda para OUTRO provider quando um dá
   429/500/timeout. Com chave paga em vários providers, cair de A→B é o que
   garante uptime — o turno não morre.

Esta spec troca "tier → 1 modelo de 1 provider" por **"tier → lista ordenada de
candidatos (provider, modelo)"**, com fallback em tempo de INVOKE, mantendo a
convenção CRÍTICA de resiliência (último recurso ainda devolve `AIMessage` —
guard de `FallbackLLM` continua obrigatório). Princípio de arquitetura:
**mecânica é Python** — a política de roteamento é código determinístico, não
decisão do LLM; e a abstração `ModelTier` já existe justamente pra trocar
provider sem tocar nos agentes (`REFERENCE.md:38`).

Quase todos os providers-alvo expõem endpoint **OpenAI-compatível** (Groq, Qwen/
DashScope, GLM/Zhipu, MiniMax, Kimi/Moonshot, DeepSeek) → reusam o
`_build_openai` existente, só mudando `base_url`/key/modelo. Único não-compat da
lista é a Anthropic (builder novo, dep opcional).

## 2. Requisitos

- **R1 — Terceiro tier.** `ModelTier` ganha `CLASSIFY` (menor/mais rápido, para
  classificação e parse estruturado temp 0). Fica `CLASSIFY < FAST < SMART`.
- **R2 — Tabela de rotas.** `ROUTES: dict[ModelTier, list[Candidate]]` onde
  `Candidate = (provider: str, model: str)`. 1º = preferido; resto = fallback em
  ordem. Config vive em `llm_setup.py` (código, não LLM). Overridable por env
  (R8) sem editar código.
- **R3 — Registro de providers.** `PROVIDER_ENDPOINTS: dict[str, str]` mapeia
  provider → `base_url` OpenAI-compat. Todos os compat passam pelo
  `_build_openai(base_url=..., api_key=<KEY do provider>)`. Cada provider lê sua
  própria env key (`GROQ_API_KEY`, `QWEN_API_KEY`, `GLM_API_KEY`,
  `MINIMAX_API_KEY`, `KIMI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`).
- **R4 — Builder Anthropic.** `_build_anthropic(temperature, model)` via
  `langchain-anthropic` (extra opcional `uv sync --extra anthropic`). Ausência
  da dep ⇒ candidato pulado (não derruba a chain), igual `ImportError` dos
  outros.
- **R5 — Fallback em tempo de invoke.** `get_llm(tier)` devolve um `RoutedLLM`
  que embrulha os candidatos do tier. Em `.invoke()`/`.stream()` tenta o 1º
  candidato; exceção (429/500/timeout/dep faltando/sem key) → próximo candidato;
  esgotou todos → comportamento `FallbackLLM` (devolve `AIMessage` de erro,
  NUNCA levanta). `with_structured_output(X)`/`bind_tools`/`with_retry`
  propagam para cada candidato e mantêm a mesma semântica de queda.
- **R6 — Convenção de resiliência preservada.** Como o último recurso ainda é
  um `AIMessage` (não instância do modelo Pydantic), o guard obrigatório
  (`isinstance`/`try` em todo `with_structured_output`) continua valendo
  inalterado. RoutedLLM NÃO mascara isso.
- **R7 — Construção preguiçosa + cache.** Candidato só é construído quando a
  chain chega nele (não instanciar 3 clients por chamada). Cache por
  `(provider, model, temperature)` — evita reconstruir cliente a cada turno.
- **R8 — Override por env (produto + dev + offline).**
  - `RPG_FORCE_MOCK=1` continua curto-circuitando tudo (MockLLM) — suíte
    inalterada.
  - `LLM_PROVIDER=<x>` (legado) continua funcionando: força TODOS os tiers a um
    único provider (ex.: `ollama` → jogo 100% local; `gemini` → comportamento
    atual). Quando setado, ignora `ROUTES` e usa o mapa por-tier daquele
    provider (dicts existentes de ollama/openai).
  - `RPG_ROUTES=<caminho.json>` (novo, opcional) sobrescreve `ROUTES` a partir
    de arquivo — permite trocar a stack sem deploy.
  - Sem nada disso: usa `ROUTES` default (R11).
- **R9 — Hook de telemetria.** Após cada invoke bem-sucedido, RoutedLLM chama um
  callback opcional `on_llm_call(provider, model, tier, latency_ms, fell_back:
  bool)` (registrado via `set_llm_telemetry_hook(fn)`; default no-op). É o canal
  que a Fase 5.3 consome para gravar provider/modelo/custo por turno. Zero custo
  quando não registrado.
- **R10 — Contratos por provider.** Estende a suíte `-m llm_contract` (Fase 11):
  para cada provider habilitado numa env allowlist (`RPG_CONTRACT_PROVIDERS`),
  um teste roda o parse estruturado do router (CLASSIFY) e asserta que devolve
  instância Pydantic válida — valida `with_structured_output` no modelo real
  (MockLLM esconde mapeamento). Fora da suíte default (custa requests).
- **R11 — Stack default de produção** (candidatos; ids exatos confirmados na
  doc de cada provider no momento da impl):
  ```
  CLASSIFY: [("groq","openai/gpt-oss-20b"), ("gemini","gemini-flash-lite-latest")]
  FAST:     [("minimax","MiniMax-M2.5"), ("qwen","qwen-plus"), ("groq","llama-3.3-70b-versatile")]
  SMART:    [("groq","moonshotai/kimi-k2"), ("glm","glm-4.6"), ("anthropic","claude-sonnet-4-6")]
  ```

### Fora de escopo

- Roteamento por CONTEÚDO/dificuldade do turno (ex.: "boss → tier maior"). Os
  helpers `_pick_tier` de `bestiary.py`/`npc.py` continuam como estão (escolhem
  tier; a rota do tier é problema desta spec). Roteamento adaptativo = futuro.
- Balanceamento de carga / round-robin entre candidatos saudáveis. A ordem é
  fixa (preferência + fallback), não distribuição.
- Circuit breaker persistente (lembrar que provider X está fora por N min).
  Cada turno tenta do topo. Se virar problema de custo/latência, vira spec
  própria.
- Cache de resposta / dedupe de prompt.
- Migração de `gemini-flash-latest`/`gemini-pro-latest` para ids fixos — segue
  usando aliases `-latest` onde o provider oferece.

## 3. Design técnico

### Arquivos alterados

- **`llm_setup.py`** — núcleo da spec:
  - `ModelTier` ganha `CLASSIFY = "classify"`.
  - `PROVIDER_ENDPOINTS`, `ROUTES`, loaders de override (`LLM_PROVIDER`,
    `RPG_ROUTES`).
  - `_build_openai` ganha parâmetro explícito de `base_url`/`api_key`/`model`
    (hoje já lê env; passa a aceitar por-provider).
  - `_build_anthropic` novo.
  - `_PROVIDERS` vira `provider → builder` cobrindo groq/qwen/glm/minimax/kimi/
    deepseek (todos `_build_openai` com endpoint próprio) + `anthropic`.
  - `RoutedLLM` (classe nova) + `set_llm_telemetry_hook`.
  - `get_llm(temperature=0.1, tier=ModelTier.FAST)` reescrita: resolve os
    candidatos do tier (respeitando overrides) e devolve `RoutedLLM`. Assinatura
    pública inalterada (back-compat total nos call sites).
- **`mock_llm.py`** — `MockLLM` precisa responder a `CLASSIFY` como responde a
  `FAST` (dados fictícios por agente independem de tier; conferir que nada
  quebra com o valor novo do enum).
- **Agentes** (migração de `tier=`, etapa 2): `router.py`, `combat.py` (parse/
  spawn), `loot.py` (TradeIntent), `librarian.py` → `ModelTier.CLASSIFY`.
  Narração (`storyteller`, combat narração, `npc`, loot narração,
  `world_simulator`, `bestiary`) → `FAST`. Coerência (`campaign_manager`,
  `archivist`, `character_creator`) → `SMART`. (Ver tabela §Etapa 2.)
- **`pyproject.toml`** — extra opcional `anthropic = ["langchain-anthropic"]`.
- **`.env.example`** — seção nova por provider (keys + endpoints comentados).
- **`tests/test_contracts_llm.py`** — contratos por provider (R10).
- **`CLAUDE.md`** / **`ESTADO_ATUAL.md`** — tabela de tiers atualizada (2→3) +
  nota de roteamento/fallback.

### Schemas / assinaturas

```python
# llm_setup.py
class ModelTier(Enum):
    CLASSIFY = "classify"   # menor/rápido: router, parse estruturado (temp 0)
    FAST = "fast"           # narração/roleplay
    SMART = "smart"         # coerência: campanha, archivist, criador

Candidate = tuple[str, str]                 # (provider, model)
ROUTES: dict[ModelTier, list[Candidate]]    # R11
PROVIDER_ENDPOINTS: dict[str, str]          # provider -> base_url OpenAI-compat
PROVIDER_KEY_ENV: dict[str, str]            # provider -> nome da env da key

class RoutedLLM:
    """Embrulha candidatos ordenados; fallback em tempo de invoke.
    Último recurso: AIMessage de erro (nunca levanta) — guard segue obrigatório.
    """
    def __init__(self, tier: ModelTier, temperature: float,
                 candidates: list[Candidate]): ...
    def with_structured_output(self, schema, **kw) -> "RoutedLLM": ...
    def bind_tools(self, *a, **kw) -> "RoutedLLM": ...
    def with_retry(self, *a, **kw) -> "RoutedLLM": ...
    def invoke(self, input): ...            # tenta candidatos em ordem
    def stream(self, input): ...            # idem; 1º candidato que não levanta

def set_llm_telemetry_hook(fn: Callable[[str, str, ModelTier, int, bool], None] | None) -> None: ...

def get_llm(temperature: float = 0.1, tier: ModelTier = ModelTier.FAST) -> RoutedLLM: ...
```

### Semântica de fallback (o coração)

`RoutedLLM.invoke` percorre `self.candidates`:
1. Constrói (lazy, cache R7) o client do candidato via `_PROVIDERS[provider]`.
   Falha de build (ImportError da dep, key ausente) ⇒ pula pro próximo.
2. `client.invoke(input)`. Sucesso ⇒ dispara hook R9 (`fell_back = índice > 0`)
   e retorna.
3. Exceção (429/500/timeout/etc.) ⇒ registra warning, tenta próximo.
4. Todos falharam ⇒ retorna `AIMessage(content="[LLM] todos os provedores do
   tier {tier} falharam: ...")`. `with_structured_output` ativo ⇒ mesmo
   `AIMessage` (não instância Pydantic) — guard do nó captura.

`with_structured_output(X)` guarda o schema e reaplica a cada candidato dentro
do loop (cada provider tem seu método; langchain resolve por client). Se um
candidato devolver instância válida de X, retorna; se levantar, próximo.

### Formato de `RPG_ROUTES` (override, R8)

```json
{
  "classify": [["groq", "openai/gpt-oss-20b"], ["gemini", "gemini-flash-lite-latest"]],
  "fast":     [["minimax", "MiniMax-M2.5"], ["groq", "llama-3.3-70b-versatile"]],
  "smart":    [["glm", "glm-4.6"], ["anthropic", "claude-sonnet-4-6"]]
}
```

## 4. Plano passo a passo

### Etapa 1 — Infra de rotas + fallback (sem tocar agentes)

1. **Testes** (`tests/test_routing.py`, offline, providers FAKE por
   monkeypatch):
   - `test_classify_tier_existe` — enum + `ROUTES[CLASSIFY]` não-vazio.
   - `test_get_llm_devolve_routed` — instância de `RoutedLLM`.
   - `test_fallback_pula_candidato_que_levanta` — 1º candidato monkeypatchado
     pra levantar; 2º responde → resposta vem do 2º; hook recebe `fell_back=True`.
   - `test_todos_falham_devolve_aimessage` — todos levantam → `AIMessage`, NÃO
     exceção (convenção CRÍTICA).
   - `test_with_structured_output_todos_falham_nao_e_instancia` — garante que o
     guard do nó ainda é necessário (retorno é `AIMessage`).
   - `test_key_ausente_pula_provider` — candidato sem env key é pulado.
   - `test_build_cacheado` — mesmo `(provider, model, temp)` constrói 1×.
   - `test_force_mock_curto_circuita` — `RPG_FORCE_MOCK=1` → MockLLM, ignora
     ROUTES.
   - `test_llm_provider_legado_forca_provider_unico` — `LLM_PROVIDER=ollama`
     usa mapa por-tier do ollama, ignora ROUTES.
   - `test_rpg_routes_override` — `RPG_ROUTES` aponta JSON → rotas trocadas.
2. **Implementação:** `ModelTier.CLASSIFY`, `PROVIDER_ENDPOINTS`,
   `PROVIDER_KEY_ENV`, `ROUTES`, `_build_openai` parametrizado, `_build_anthropic`,
   `RoutedLLM`, `set_llm_telemetry_hook`, `get_llm` reescrita, overrides.
3. **Verificação:** `/qa` verde.

### Etapa 2 — Migração dos agentes para 3 tiers

Migrar cada `get_llm(tier=...)` conforme a tabela. Nenhum agente muda de lógica;
só o tier.

| Nó / arquivo | Hoje | Vira | Motivo |
|---|---|---|---|
| `router.py:53` | FAST | **CLASSIFY** | só classifica intenção |
| `combat.py:100,234` (parse/spawn) | FAST | **CLASSIFY** | identifica ação/inimigos |
| `loot.py:40` (TradeIntent) | FAST | **CLASSIFY** | parse de transação |
| `librarian.py:48` | FAST | **CLASSIFY** | dedupe semântico |
| `bestiary.py` (enemy pequeno) | FAST | **FAST** | mantém |
| `storyteller` narração | FAST | **FAST** | mantém |
| `combat.py:292` (narração) | SMART | **FAST** | narração ≠ coerência global |
| `npc.py:280` | SMART | **FAST** | roleplay, não planejamento |
| `loot.py:58` (narração) | SMART | **FAST** | idem |
| `world_simulator.py:96` | SMART | **FAST** | narração off-screen |
| `campaign_manager.py:87` | SMART | **SMART** | planeja arcos |
| `archivist.py:80` | SMART | **SMART** | extração de fato (coerência) |
| `character_creator.py:162` | SMART | **SMART** | ficha canônica |

1. **Testes:** `test_router_usa_classify` e afins — monkeypatch em `get_llm`
   capturando o `tier` passado por cada nó; assert bate a tabela. (Barato,
   offline, blinda regressão de tier.)
2. **Implementação:** trocar os `tier=` listados. Atualizar tabela do CLAUDE.md.
3. **Verificação:** `/qa` verde + `tests/test_mvp.py`/`test_fase*` seguem verdes
   (comportamento idêntico no MockLLM).

### Etapa 3 — Anthropic, contratos por provider, env, docs

1. **Testes:** `test_anthropic_pulado_sem_dep` (sem `langchain-anthropic` →
   candidato pulado, chain segue); contrato `-m llm_contract` parametrizado por
   `RPG_CONTRACT_PROVIDERS` (R10) — fora da suíte default.
2. **Implementação:** `_build_anthropic` + extra no `pyproject`; contratos;
   `.env.example` + `.env` (placeholders de key por provider); atualizar
   `ESTADO_ATUAL.md` (tabela de tiers 2→3, roteamento/fallback).
3. **Verificação:** `uv run pytest` completo verde; `uv run pytest -m
   llm_contract` com pelo menos Groq+Gemini reais (§6).

## 5. Critérios de aceite

- [ ] `ModelTier.CLASSIFY` existe; `get_llm` devolve `RoutedLLM` com fallback
- [ ] Fallback pula candidato que levanta e usa o próximo (teste com fakes)
- [ ] Todos os candidatos falharem ⇒ `AIMessage` (nunca exceção) — guard segue
      obrigatório e testado
- [ ] `RPG_FORCE_MOCK`, `LLM_PROVIDER` legado e `RPG_ROUTES` todos funcionam
- [ ] Cada nó no tier certo (tabela Etapa 2) — teste de tier por nó
- [ ] Build de candidato cacheado por `(provider, model, temp)`
- [ ] Hook de telemetria dispara com `(provider, model, tier, latency_ms,
      fell_back)` — consumido pela 5.3
- [ ] `.env.example` + `.env` listam as keys por provider
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM em todo `with_structured_output` (inalterado; RoutedLLM
      não mascara)
- [ ] Saves antigos continuam carregando (nada de schema de save muda)

## 6. Smoke test com LLM real

(consciente de custo — poucos requests por provider)

1. `RPG_CONTRACT_PROVIDERS=groq,gemini uv run pytest -m llm_contract -v -s` →
   router (CLASSIFY) devolve instância Pydantic válida em CADA provider.
2. Turno real da stack default: setar keys de Groq + MiniMax (ou Qwen) + um SMART,
   jogar 1 turno de narração + 1 de combate + 1 que dispare campaign_manager;
   conferir no log de telemetria que CLASSIFY foi no Groq, narração no FAST,
   planejamento no SMART.
3. **Fallback real:** setar key inválida no 1º candidato de um tier → conferir
   que o turno completa pelo 2º candidato e o hook marca `fell_back=True`.

## 7. Riscos & compatibilidade

- **Structured output desigual entre providers.** Nem todo endpoint OpenAI-compat
  suporta `with_structured_output` igual (function-calling/json mode). Mitigação:
  CLASSIFY só em provider validado pelo contrato R10 (Groq/Gemini na default);
  narração (FAST) tolera texto livre. Provider que falha o contrato NÃO entra em
  tier com structured output.
- **Latência de endpoints CN.** Beijing é mais barato mas lento do Brasil; usar
  endpoint Internacional (Singapura) da Qwen; Groq/Anthropic são US/global.
- **MockLLM esconde mapeamento.** Cada provider novo exige smoke real (R10 + §6);
  nome de campo/JSON só quebra no modelo vivo.
- **Custo real com fallback.** Fallback repetido a um tier caro (ex.: SMART cair
  no Sonnet toda hora porque Groq está fora) infla custo silenciosamente — a
  telemetria da 5.3 (`fell_back`, custo por provider) é o alarme; circuit breaker
  fica pra spec futura se necessário.
- **Convenção CRÍTICA:** RoutedLLM preserva o retorno `AIMessage` no pior caso —
  não remove a necessidade do guard `isinstance`/`try` em nenhum nó.
- **Saves antigos / MockLLM / quota:** sem impacto no schema de save; suíte segue
  offline com `RPG_FORCE_MOCK`.
