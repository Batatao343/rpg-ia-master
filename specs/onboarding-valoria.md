# SPEC — Onboarding de Valoria (wizard rico de criação)

> **Status:** `approved`
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** nenhuma
> **Desbloqueia:** inicio-personalizado (frontend do passo de prólogo assume este wizard)

---

## 1. Contexto & Objetivo

A criação de personagem hoje é um formulário seco ([CreateScreen.tsx](../web/src/components/CreateScreen.tsx)):
nome, raça, classe, região e nível em selects, backstory numa textarea sem contexto.
O jogador escolhe às cegas — não sabe o que é um "Sangromante", o que existe em
Skallgard nem qual é o momento do mundo. Sem afinidade com o personagem, a
descrição livre sai vazia e o início da campanha não tem gancho.

Esta spec transforma a criação num **wizard multi-passo com lore curado**: o
jogador recebe um breve overview de Valoria (história do mundo, o que cada
região oferece, como cada classe joga) e só então descreve quem quer ser. Todo
o conteúdo é **curado à mão e determinístico** — zero chamada de LLM, zero
dependência de RAG (embeddings hoje indisponíveis), zero risco de vazar
conteúdo `hidden`/`secret`.

Princípio de arquitetura: conteúdo é dado versionado em `data/` (Fase 7.2 —
autoria via `docs/AUTORIA.md`), não geração em runtime.

## 2. Requisitos

- **R1** — Existe `data/onboarding.json` com: `world_intro` (título + 3
  parágrafos), 1 card por **região** de `origins.json` (12), 1 card por
  **classe** de `classes.json` (10), 1 card por **raça** de `origins.json` (6).
- **R2** — Cada card tem `tagline` (≤ 90 chars) e `description` (≤ 400 chars);
  cards de região têm também `hook` (≤ 200 chars); cards de classe têm também
  `playstyle` (≤ 160 chars). Tudo em pt-BR.
- **R3** — Cobertura é **testada**: adicionar região/classe/raça nos JSONs
  canônicos sem card correspondente quebra a suíte.
- **R4** — `GET /data/onboarding` devolve o JSON completo (200, sem
  transformação). `/data/options` permanece intocado.
- **R5** — `CreateScreen` vira wizard de 5 passos com estado preservado e
  navegação livre (voltar/avançar): (1) O Mundo — intro skippável ("Pular
  introdução" salta ao passo 2); (2) Origem — cards de raça com tagline +
  traits mecânicos (já vêm de `races_full`); (3) Vocação — cards de classe com
  tagline + passiva + playstyle; (4) Região — cards com tagline + hook + bônus
  inicial (de `origins.json`); (5) Identidade — nome, nível e descrição livre.
- **R6** — A textarea do passo 5 orienta a descrição: placeholder/label do tipo
  "Quem é você? De onde veio, o que busca?" (substitui o campo backstory seco).
- **R7** — Payload enviado ao `POST /game/new` continua com o mesmo shape atual
  (`name/race/class_name/region/level/backstory`) — backend intocado.
- **R8** — Wizard funciona em mobile 390px (padrão do projeto, spec
  polish-sessao) e o botão "Continuar jornada" (save existente) permanece
  acessível a partir do passo 1.
- **R9** — Conteúdo do `onboarding.json` não menciona nenhuma entidade cujo
  documento do Codex seja `visibility: hidden|secret` (curadoria manual;
  regra de autoria registrada em `docs/AUTORIA.md`).

### Fora de escopo

- CLI (`game_engine.py`) mantém o wizard textual atual.
- Nenhuma chamada de LLM, nenhum uso de RAG.
- Imagens/arte por região ou classe (Fase 8).
- Prólogo personalizado e passo 6 do wizard (spec `inicio-personalizado`).

## 3. Design técnico

### Arquivos novos

- `data/onboarding.json` — conteúdo curado do overview (formato abaixo).
- `tests/test_onboarding.py` — cobertura, limites e endpoint.
- `web/src/components/create/` (opcional, se `CreateScreen.tsx` passar de
  ~300 linhas): subcomponentes `StepIntro`, `StepRace`, `StepClass`,
  `StepRegion`, `StepIdentity`.

### Arquivos alterados

- `api.py` — novo endpoint `GET /data/onboarding` (leitura via
  `gamedata.load_json_data("onboarding.json")`, cache em memória como os demais).
- `web/src/api.ts` — `getOnboarding(): Promise<OnboardingData>`.
- `web/src/types.ts` — tipos `OnboardingData`, `RegionCard`, `ClassCard`, `RaceCard`.
- `web/src/components/CreateScreen.tsx` — wizard 5 passos (estado local:
  `step: 0..4`; campos atuais preservados).
- `web/src/styles.css` (ou equivalente) — layout de cards + stepper, mobile 390px.
- `docs/AUTORIA.md` — seção curta: como editar cards do onboarding (R9).

### Formato de `data/onboarding.json` (exemplo real, ids canônicos)

```json
{
  "world_intro": {
    "title": "Valoria",
    "paragraphs": [
      "<parágrafo 1 — o que é o mundo>",
      "<parágrafo 2 — o momento atual (pós-Inundação, Praga de Ferro...)>",
      "<parágrafo 3 — o que espera um aventureiro>"
    ]
  },
  "regions": {
    "nova_arcadia": {
      "tagline": "A capital que sobrou — ouro, intriga e muros altos.",
      "description": "<2-3 frases sobre a região>",
      "hook": "Quem começa aqui costuma se enredar em dívidas, cortes e conspirações."
    },
    "skallgard": { "tagline": "...", "description": "...", "hook": "..." }
  },
  "classes": {
    "Sombra da Corte": {
      "tagline": "Lâmina invisível da política.",
      "description": "<2-3 frases>",
      "playstyle": "Furtividade, manipulação e golpes precisos — evita o confronto aberto."
    }
  },
  "races": {
    "race_cinzeus": { "tagline": "...", "description": "..." }
  }
}
```

Chaves: `regions.*` e `races.*` usam os **ids** de `origins.json`
(`nova_arcadia`, `race_cinzeus`, ...); `classes.*` usa os **nomes** exatos de
`classes.json` ("Cavaleiro da Vigília", ...), pois classes não têm id.

### Assinaturas

- `api.py`: `@app.get("/data/onboarding") def get_onboarding() -> dict` —
  404 com detalhe amigável se o arquivo não existir (defesa; em produção existe).
- Frontend: componente controlado; `useState` para `step` + campos; dados de
  `getOnboarding()` + `getOptions()` carregados em paralelo no mount.

## 4. Plano passo a passo

### Etapa 1 — Conteúdo curado + testes de cobertura

1. **Testes** (`tests/test_onboarding.py`):
   - `test_onboarding_regions_cover_origins` — toda região de `origins.json`
     tem card em `onboarding.json["regions"]` (e vice-versa: sem card órfão).
   - `test_onboarding_classes_cover_classes_json` — idem para `CLASSES`.
   - `test_onboarding_races_cover_origins` — idem para raças.
   - `test_onboarding_field_limits` — tagline ≤ 90, description ≤ 400,
     hook ≤ 200, playstyle ≤ 160; `world_intro.paragraphs` tem 3 itens.
2. **Implementação:** escrever `data/onboarding.json` completo (28 cards +
   intro), seguindo `docs/AUTORIA.md`; consultar `lore_nova/` via Grep para
   fidelidade (sem copiar conteúdo de `secrets.txt`/docs `hidden`).
3. **Verificação:** `uv run pytest tests/test_onboarding.py` verde.

### Etapa 2 — Endpoint

1. **Testes:** `test_api_onboarding_endpoint` — `GET /data/onboarding` → 200,
   shape com as 4 chaves (`world_intro/regions/classes/races`).
2. **Implementação:** endpoint em `api.py`.
3. **Verificação:** suíte verde + `bash scripts/smoke_api.sh` ainda passa.

### Etapa 3 — Wizard no frontend

1. **Testes:** frontend não tem suíte — verificação manual guiada (checklist §6).
2. **Implementação:** stepper de 5 passos em `CreateScreen.tsx`; cards
   clicáveis substituem selects (select permanece como fallback acessível
   ou os cards têm role/aria adequados); "Pular introdução"; estado preservado
   ao voltar; textarea com prompt novo (R6).
3. **Verificação:** `cd web && npm run build` sem erro; smoke manual.

## 5. Critérios de aceite

- [ ] `data/onboarding.json` com 12 regiões + 10 classes + 6 raças + intro (R1-R2)
- [ ] Testes de cobertura falham ao remover um card (R3)
- [ ] `GET /data/onboarding` → 200 com shape completo (R4)
- [ ] Wizard 5 passos navegável, estado preservado, mobile 390px (R5, R8)
- [ ] Criar personagem pelo wizard produz o mesmo payload/fluxo atual (R7)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] `npm run build` verde
- [ ] Saves antigos continuam carregando (nada de estado tocado)

## 6. Smoke test com LLM real

Não se aplica — spec sem LLM. Smoke **manual de UI** (substitui):

1. `uv run uvicorn api:app --port 8000` + `web` buildado → abrir `/`.
2. Navegar os 5 passos; voltar do 4 ao 2 e conferir seleções preservadas.
3. "Pular introdução" salta ao passo 2.
4. Criar personagem (MockLLM ok) → jogo abre normalmente.
5. DevTools em 390px → passos legíveis, cards sem overflow horizontal.

## 7. Riscos & compatibilidade

- **Saves antigos:** intocados — spec não altera estado nem persistência.
- **MockLLM/FallbackLLM:** irrelevante — zero LLM.
- **Quota/latência:** zero impacto; 1 fetch estático a mais no mount.
- **Drift de conteúdo:** classe/região nova sem card quebra a suíte (R3) — o
  drift é ruidoso por construção.
- **Vazamento de lore:** mitigado por curadoria manual + regra em AUTORIA.md
  (R9); conteúdo novo é escrito, não extraído.
