# SPEC — Laboratório de simulação de combate

> **Status:** `done` (2026-08-03 — 1388 offline verdes; build/browser aceitos)
> **Criada:** 2026-08-03 · **Atualizada:** 2026-08-03
> **Depende de:** `conflito-16-frontend-combate-cartas` (`done`)
> **Desbloqueia:** teste manual rápido de Cartas, Reações, Ferimentos e balanceamento

---

## 1. Contexto & Objetivo

O frontend já renderiza o combate tático completo, mas só permite alcançá-lo no
curso de uma campanha. Isso torna lenta a validação manual de classe, Carta,
Reação, inimigo ou ajuste de balanceamento.

Esta spec cria um laboratório isolado que entra diretamente numa arena usando o
mesmo motor determinístico e a mesma UI do jogo. A preparação, a resolução e a
narração mecânica da simulação não fazem chamadas de LLM/RAG e não avançam arco,
memória, crônica ou loot.

## 2. Requisitos

- **R1 — Entrada direta.** As telas iniciais de criação e saves exibem “Simular
  combate”, abrindo uma configuração dedicada sem exigir campanha existente.
- **R2 — Configuração.** O usuário escolhe uma das cinco classes, nível
  `1|3|5|10`, inimigo canônico do bestiário e quantidade `1..3`.
- **R3 — API fechada.** `GET /data/combat-simulator` lista opções públicas e
  `POST /game/combat-simulator` valida IDs/limites e cria uma sessão UUID.
- **R4 — Estado canônico.** A ficha usa a criação determinística oficial, o
  inimigo é clonado do bestiário com IDs únicos, e a cena congelada contém o
  jogador e todos os inimigos.
- **R5 — Zero LLM/RAG.** Com `combat_simulation.enabled=true`, campaign manager,
  preparação/narração LLM, archivist e loot são pulados. Texto livre sem seleção
  estruturada degrada deterministicamente para ataque básico.
- **R6 — Mesmo motor/UI.** Cartas, Reações, manobras, Ruptura, Vitalidade,
  Ferimentos, zonas e IA tática usam os componentes e serviços de produção.
- **R7 — Identidade visível.** `GameResponse.combat_simulation` identifica o
  laboratório; a UI mostra selo “Laboratório” e permite reiniciar voltando à
  configuração.
- **R8 — Persistência isolada.** A sessão pode usar o save normal para sobreviver
  a reload, mas é marcada como simulação e não gera checkpoint/campanha/memória.

### Fora de escopo

- Editor de fichas ou inimigos campo a campo.
- Simulação estatística em lote (o harness `playtest/` continua responsável).
- Recompensas, XP, loot, crônica, checkpoints ou continuidade narrativa.
- Alterar as regras de combate ou balanceamento.

## 3. Design técnico

- **`api.py`** — schemas `CombatSimulatorRequest` e opções; builders puros de
  jogador, inimigos, cena e estado; endpoints GET/POST; extensão estruturada de
  `ActionRequest` para manobras/ataque básico; resposta expõe metadados.
- **`character_creator.py`** — opção keyword-only para omitir flavor/RAG/LLM sem
  mudar o fluxo clássico.
- **`state.py`** — campo opcional `combat_simulation: Dict`.
- **`agents/campaign_manager.py` / `agents/combat.py` / `main.py`** — gates que
  mantêm o turno do laboratório dentro do combate e encerram o grafo antes de
  loot/archivist; fallback narrativo é o log mecânico.
- **`web/src/components/CombatSimulatorScreen.tsx`** — formulário acessível de
  configuração.
- **`web/src/App.tsx`, `CreateScreen.tsx`, `SaveScreen.tsx`, `PlayScreen.tsx`,
  `api.ts`, `types.ts`, `styles.css`** — navegação, contrato e identificação.

Contrato resumido:

```json
POST /game/combat-simulator
{"class_name":"Sangromante","level":3,"enemy_id":"mon_cao_rebite","quantity":2}

GameResponse.combat_simulation = {
  "enabled": true,
  "enemy_id": "mon_cao_rebite",
  "quantity": 2
}
```

## 4. Plano passo a passo

### Etapa 1 — Contratos e estado

1. **Testes** (`tests/test_combat_simulator.py`): opções só expõem IDs canônicos;
   request inválido retorna 422; builder cria player/cena/inimigos válidos.
2. **Implementação:** schemas, builders e endpoints.
3. **Verificação:** testes focados verdes.

### Etapa 2 — Isolamento mecânico

1. **Testes:** monkeypatch de `get_llm`/RAG que falha se chamado; turno de Carta e
   texto livre continuam funcionando; vitória não passa por loot/archivist.
2. **Implementação:** gates do grafo, narração mecânica e declaração fallback.
3. **Verificação:** teste e2e via API com zero LLM/RAG.

### Etapa 3 — Frontend

1. **Testes/build:** contrato TypeScript e build Vite.
2. **Implementação:** tela de configuração, entradas nas telas iniciais, selo e
   reinício; reutilizar `PlayScreen` e dock tático existentes.
3. **Verificação:** smoke browser desktop + 390 px, console limpo.

### Etapa 4 — Fechamento

1. `uv run pytest` completo, lint de conteúdo e `npm run build` verdes.
2. Atualizar esta spec, `ROADMAP.md` e `ESTADO_ATUAL.md`.

## 5. Critérios de aceite

- [x] Configuração abre diretamente pelas telas iniciais.
- [x] Classe, nível, inimigo e quantidade chegam validados ao backend.
- [x] Sessão começa com combate ativo, Cartas e alvos canônicos visíveis.
- [x] Um turno estruturado altera o estado pelo motor real.
- [x] Nenhuma chamada de LLM/RAG, loot ou archivist ocorre no laboratório.
- [x] Vitória/derrota e reinício são visíveis e não contaminam campanha.
- [x] Frontend desktop/mobile sem erro de console e com controles acessíveis.
- [x] Saves/campanhas antigas continuam funcionando.
- [x] `uv run pytest` e `npm run build` verdes.

## 6. Smoke test

Esta feature é deliberadamente zero-LLM; o smoke proporcional é browser + API:

1. Abrir “Simular combate”, escolher Sangromante nível 3 × 2 Cães de Rebite.
2. Jogar Carta com alvo, selecionar Reação e executar uma manobra.
3. Confirmar mudança de Vitalidade/Ferimentos/Entropia e round sem request LLM.
4. Reiniciar, conferir nova arena e responsividade em 390 px.

**Executado:** sessão `9f3193bd-2f42-4ad9-a24d-a76661846960`; desktop com
Sangromante nível 3 × 2 Cães de Rebite confirmou alvo, Reação, Carta, round,
Vitalidade, Ferimento, Entropia e log mecânico. Mobile 390×844 confirmou
configuração, carrossel de uma Carta por vez e manobra Guardar. Console/page
errors limpos; axe WCAG 2 A/AA = 0 violações. Nenhuma request LLM é necessária
por contrato e pelos testes fail-loud.

## 7. Riscos & compatibilidade

- Saves antigos não têm `combat_simulation` e seguem no fluxo atual.
- O modo usa save normal por UUID, mas seu marcador impede campanha/arquivamento.
- O bestiário pode crescer sem mudar o contrato; opções são geradas dos dados.
- A flag que omite flavor é opt-in e não altera criação normal.
