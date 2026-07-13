# SPEC — Polish de sessão: saves, chips de combate, crônica, onboarding, mobile

> **Status:** `approved` (design refinado com o usuário em 2026-07-13 — chips
> viraram 100% mecânicos de COMBATE; sugestões de exploração via LLM adiadas p/ v2)
> **Criada:** 2026-07-13 · **Atualizada:** 2026-07-13
> **Depende de:** Fase 10 fatia local `done` (save_path/UUID); Fase 3.1 `done` (crônica)
> **Desbloqueia:** demo apresentável; base de UX p/ Fase 8 (arte) e 10b (público)

---

## 1. Contexto & Objetivo

O motor está sólido (729 testes, playtest agêntico, multi-provider), mas a CASCA
tem fricções de produto que custam pouco a remover:

1. O frontend só sabe carregar "o save mais recente" — quem tem 2+ campanhas não
   consegue escolher, continuar nem excluir pela UI (a API já aceita `game_id`).
2. Toda ação exige DIGITAR — em mobile é penoso; o pior caso é o COMBATE, onde
   o jogador precisa digitar o nome exato da habilidade/poção. (Decisão de
   refinamento 2026-07-13: v1 ataca o combate com chips MECÂNICOS derivados da
   ficha — zero LLM; sugestões de exploração via LLM ficam p/ v2.)
3. Crônica (Fase 3.1) não exporta nem busca — os dois itens estão no backlog do
   ROADMAP desde a Fase 3.
4. O 1º turno não ensina os comandos que o motor entende (viajar/descansar/
   equipar/falar/atacar) — o jogador descobre por tentativa.
5. `web/` nunca teve passe mobile — jogo de texto é caso de uso natural de celular.

Princípio: tudo aqui é view/transporte — ZERO mudança de mecânica e **ZERO
mudança de schema LLM** (os chips derivam da ficha em Python puro).

## 2. Requisitos

- **R1 — `GET /game/saves`.** Lista os saves de `saves/*.json`:
  `[{game_id, name, class_name, level, location, day, game_over, updated_at}]`,
  ordenado por `updated_at` desc. Leitura TOLERANTE: save corrompido/ilegível é
  pulado (não derruba a lista). Não pagina (uso local).
- **R2 — `DELETE /game/save/{game_id}`.** UUID validado por `save_path()` (400
  se inválido — mesmo padrão da Fase 10), 404 se não existe, 200 remove o save
  E o índice de memória da sessão (`data/saves_memory/{game_id}/` — senão vira
  lixo órfão). Sem confirmação server-side (a confirmação é da UI). Entra no
  rate limit.
- **R3 — Tela "Continuar jornada".** Frontend: tela inicial lista as campanhas
  (nome, classe/nível, local, dia, badge `⚰ memorial` p/ game_over), com
  Continuar / Excluir (modal de confirmação com o nome do herói) / Nova jornada.
  Save memorial abre em modo leitura (crônica visível, input bloqueado — a API
  já devolve 409).
- **R4 — Chips de combate (100% mecânicos, zero LLM).** *(Refinado 2026-07-13.)*
  Em combate ativo, o bloco `combat` do `GameResponse` ganha
  `suggestions: List[str]` derivadas da FICHA em Python puro
  (`combat_mechanics.combat_suggestions`):
  - habilidades conhecidas FORA de cooldown e com recurso suficiente
    (mana/stamina — condition_modifiers da 4.2 contam), pelo nome exibível;
  - "Beber <poção>" se houver consumível de cura no inventário;
  - "Fugir" se o herói não estiver enredado (root da 4.2 bloqueia — mesma regra
    da fuga real do fix-playtest-achados);
  - máx 5 chips; ordem: habilidades por tier desc → poção → fugir.
  Frontend renderiza os chips SÓ no modo combate; click envia o texto como ação
  normal (o parser do combate já casa nome→id canônico via `normalize`). Fora
  de combate: sem chips. Zero campo novo em schema de LLM; zero mudança no
  MockLLM; contratos da Fase 11 intocados.
- **R5 — Crônica: exportar + buscar.** `GET /game/chronicle/export?game_id=` →
  `text/plain` (download `.txt`) com separadores por capítulo (formato da 3.1);
  busca CLIENT-SIDE na aba Crônica (filtro de texto local sobre entries — zero
  endpoint, zero RAG; o item "busca via RAG" do backlog fica explicitamente
  adiado). Botão de download na aba.
- **R6 — Onboarding do 1º turno.** Painel dismissible no frontend quando
  `turn_count ≤ 1`: 5 exemplos de comando que o motor entende (viajar para X,
  descansar, equipar Y, falar com Z, atacar W) + dica dos chips. 100% frontend
  (zero motor, zero LLM); estado "dispensado" em localStorage por game_id.
- **R7 — Passe mobile.** `web/` utilizável em 390px de largura: layout 1 coluna
  (log em cima, input fixo embaixo), HUD vira drawer/aba colapsável, chips do R4
  como principal input de toque, sem overflow horizontal em nenhuma aba.
  Critério: build + smoke manual em viewport 390×844.

### Fora de escopo

- Auth/multiusuário/Postgres (Fase 10b).
- Compressão de capítulo antigo pelo archivist (segue no backlog).
- Busca da crônica via RAG/embeddings (v1 é filtro local).
- **Sugestões de EXPLORAÇÃO via LLM** (campo no StoryUpdate) — DESCARTADO no
  refinamento 2026-07-13 (YAGNI).
- Prólogo guiado (tutorial jogado nos 2-3 primeiros turnos) — DESCARTADO no
  refinamento 2026-07-13; o painel do R6 é a solução.
- Renomear save/campanha; export de save.
- PWA/offline.

## 3. Design técnico

**Arquivos alterados**
- `persistence.py` — `list_saves() -> List[dict]` (glob + json.load tolerante,
  extrai os campos do R1 + `os.path.getmtime`); `delete_save(game_id) -> bool`
  (via `save_path`; remove save + `shutil.rmtree(data/saves_memory/{id}, ignore_errors=True)`).
- `api.py` — endpoints R1/R2 (DTOs de resposta); `_combat_block` inclui
  `suggestions` (R4); export da crônica (R5, `PlainTextResponse` com
  `Content-Disposition: attachment`); rate limit inclui o DELETE.
- `combat_mechanics.py` — `combat_suggestions(player, enemies, combat) ->
  List[str]` (função PURA — lê ficha/cooldowns/recursos/condições; testável
  sem grafo).
- `web/src/` — `SaveScreen.tsx` (R3), `ActionChips.tsx` (R4, modo combate),
  `OnboardingHint.tsx` (R6), aba Crônica (busca + download, R5), CSS mobile (R7),
  `api.ts` (novas rotas), `types.ts`.
- `state.py` / `agents/storyteller.py` / `mock_llm.py` — **SEM mudança**
  (decisão de refinamento: nada de campo novo em schema de LLM).

**Schemas**
```python
# api.py — resposta do GET /game/saves
class SaveSummary(BaseModel):
    game_id: str
    name: str
    class_name: str
    level: int
    location: str
    day: int
    game_over: bool
    updated_at: float  # epoch (mtime)
```

**Assinaturas**
```python
# persistence.py
def list_saves() -> List[Dict[str, Any]]: ...
def delete_save(game_id: str) -> bool:  # ValueError se não-UUID (padrão save_path)

# combat_mechanics.py
def combat_suggestions(player: dict, enemies: list[dict],
                       combat: Optional[dict]) -> list[str]:
    """Chips do turno: habilidades prontas (cooldown 0, recurso ok) por nome,
    'Beber <poção>' se houver, 'Fugir' se não enredado. Máx 5. [] fora de combate."""
```

## 4. Plano passo a passo

### Etapa 1 — Saves na API (R1, R2)
1. **Testes** (`tests/test_polish_sessao.py`): `test_list_saves_ordena_por_mtime`;
   `test_list_saves_pula_corrompido` (arquivo lixo no dir não derruba);
   `test_delete_save_remove_save_e_memoria`; `test_delete_save_uuid_invalido_400`;
   `test_delete_save_inexistente_404`.
2. **Implementação:** persistence + endpoints.
3. **Verificação:** suíte verde.

### Etapa 2 — Chips de combate (R4)
1. **Testes:** `test_combat_suggestions_habilidade_pronta_vira_chip`;
   `test_habilidade_em_cooldown_ou_sem_recurso_nao_vira_chip`;
   `test_pocao_no_inventario_vira_chip`;
   `test_fugir_some_quando_enredado`;
   `test_fora_de_combate_lista_vazia`;
   `test_sugestoes_no_combat_block_da_api`;
   `test_chip_clicado_resolve_no_parser` (texto do chip → CombatAction mapeia
   pro ability_id certo, via MockLLM).
2. **Implementação:** função pura + `_combat_block` + `ActionChips.tsx`.
3. **Verificação:** suíte verde (zero mudança em schema de LLM).

### Etapa 3 — Crônica (R5)
1. **Testes:** `test_chronicle_export_txt` (content-type, separadores de
   capítulo, attachment); `test_chronicle_export_game_id_invalido_400`.
2. **Implementação:** endpoint + botão/busca na aba.
3. **Verificação:** verde + download manual abre legível.

### Etapa 4 — Frontend (R3, R6, R7)
1. **Testes:** `npm run build` (gate); smoke manual roteirizado (abaixo).
2. **Implementação:** SaveScreen → chips → onboarding → passe mobile (nesta
   ordem; cada um é PR/commit separado e utilizável sozinho).
3. **Verificação:** build ok; smoke manual em desktop + viewport 390px.

## 5. Critérios de aceite

- [ ] Duas campanhas criadas → tela inicial lista as duas; excluir pede confirmação e some da lista (e `data/saves_memory/` da excluída sumiu)
- [ ] Save memorial abre como leitura (crônica visível, input bloqueado)
- [ ] Chips aparecem SÓ em combate, derivados da ficha (cooldown/recurso respeitados); click executa a ação certa; fora de combate não há chips
- [ ] Download da crônica gera .txt legível com capítulos
- [ ] Busca local da crônica filtra entries em tempo real
- [ ] Painel de onboarding aparece no 1º turno e não volta depois de dispensado
- [ ] Nenhuma aba com overflow horizontal em 390px; input utilizável no touch
- [ ] `uv run pytest` verde + `npm run build` ok
- [ ] Guard de FallbackLLM: nenhum `with_structured_output` novo (spec não toca em LLM)
- [ ] Saves antigos continuam carregando (nenhuma mudança de schema de save)
- [ ] ESTADO_ATUAL.md + ROADMAP.md atualizados

## 6. Smoke test com LLM real

1. Combate REAL: chips mostram as habilidades certas da ficha; clicar num chip
   de habilidade executa ELA (CombatAction mapeia nome→id — é o mapeamento que
   o MockLLM esconde); "Beber poção" consome a poção; "Fugir" encerra o combate.
2. Criar 2ª campanha real → tela de saves mostra as duas com dados corretos;
   excluir uma não afeta a outra.
3. Download da crônica de uma campanha real abre legível.

## 7. Riscos & compatibilidade

- **Parser do combate:** o chip envia TEXTO (nome exibível) e o fluxo existente
  (CLASSIFY → gate determinístico por id) resolve; se o smoke mostrar mismatch
  nome→id em algum provider, endurecer o chip p/ mandar o id canônico junto
  ("uso <nome>") — o gate por id já protege contra alucinação.
- **DELETE é destrutivo:** UUID + 404 + confirmação na UI com nome do herói;
  não há undo (aceito — uso local).
- **Saves antigos:** intocados (nenhuma mudança de schema).
- **MockLLM/FallbackLLM:** chips independem de LLM (função pura) — suíte e
  harness seguem determinísticos; modo degradado mostra chips normalmente.
