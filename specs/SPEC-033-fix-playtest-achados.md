# SPEC — Correções de achados do playtest agêntico (Fase 5)

> **Status:** `done` (2026-07-13)
> **Criada:** 2026-07-08 · **Atualizada:** 2026-07-13
> **Depende de:** Fase 5 (harness + invariantes + telemetria) `done`
> **Desbloqueia:** playtest real mais fiel; qualidade de prompt

---

## 1. Contexto & Objetivo

O transcrito real do playtest (`playtest transcript`, run `20260708-233833`, 4 perfis
no LLM real) expôs 5 defeitos que o MockLLM escondia — 3 de PROMPT, 1 de MOTOR, 1 de
BALANCEAMENTO. Nenhum é crash (a Fase 5 já garante `erros=0`), mas todos degradam a
experiência real. Esta spec junta os 5 num único ciclo de conserto (spec-driven,
`ROADMAP.md` § Princípios: "estado sólido antes de features").

Evidência (transcrito):
- NPC Eryndor repetiu a fala VERBATIM em 2 turnos com a mesma pergunta.
- Beats do `campaign_manager` saíram em INGLÊS ("Explore the mysteries of Nova Arcádia").
- Perfil `quester` (do harness) colou a PROSA inteira do beat no texto da ação.
- Personagem MORTO (combate, turno 4, 0 HP + milestone) continuou descansando/viajando/
  lutando nos turnos 5-6 — o grafo não tem gate de `game_over` (só a API tem, via 409).
- 1 elite (Necromante, Toque Gélido 13-14 dano) matou um nível-1 em 3 golpes: o teto de
  budget da Fase 5 corta QUANTIDADE, não o TIER por-inimigo num encontro forçado.

## 2. Requisitos

- **R1 — Beats em português.** `campaign_manager` produz `beats`/`climax`/`arc_title`
  SEMPRE em pt-BR. Hoje o schema `CampaignPlan` tem `Field(description=...)` em inglês
  (`agents/campaign_manager.py:20-27`) e o system prompt não força idioma → o LLM às
  vezes responde em inglês. Fix: descrições dos campos em pt-BR + instrução explícita
  "responda SEMPRE em português do Brasil" no system prompt.
- **R2 — NPC não repete a própria fala.** `npc_actor` recebe no prompt a ÚLTIMA
  resposta que ELE deu (além da `<MEMORIA>` de fatos, `agents/npc.py:282+`) + instrução
  "varie; não repita literalmente sua fala anterior". Alvo: com a MESMA pergunta 2×, a
  2ª resposta difere da 1ª (não idêntica byte-a-byte).
- **R3 — Perfil `quester` usa objetivo CURTO.** `playtest/profiles.py::Quester` hoje
  cola `beats[step]["description"]` inteiro (prosa longa) no texto da ação. Fix: usar só
  a 1ª frase / ≤ ~80 chars do objetivo; ação nunca deve exceder ~160 chars.
- **R4 — Gate de `game_over` no grafo.** Com `state.game_over=True`, o grafo NÃO
  processa turno novo (retorna cedo / `END`, estado inalterado). Hoje só `api.py` barra
  (409) — runner/CLI e qualquer chamador direto de `app.invoke` seguiam o jogo com um
  morto. Fix no nó de entrada (`main.py` / `campaign_manager` / gate condicional a
  partir de `START`). Invariante 5.2 nova: `state.game_over=True` no turno anterior ⇒
  estado do turno seguinte é idêntico (nenhuma ação de morto foi processada).
- **R5 — Letalidade: perigo efetivo por nível em encontro FORÇADO (com ressalva de
  zona apex + fuga).** Abordagem **B** (decidida com o usuário): o encontro forçado
  (`check_encounter`) ainda DISPARA pelo perigo REAL da zona (zona perigosa te embosca),
  mas a FORÇA (criatura escolhida + budget) usa `eff_danger` escalado pelo nível — o
  mesmo knob `danger` que `pick_encounter_enemy` já consome, então um sub-nível pesca
  fauna MAIS FRACA da MESMA zona (nada de rebaixar tier na mão).
  - **Ressalva (crítica):** zonas `apex` (as 5 proibidas/endgame do mapa — `cn_o_trono`
    leviatã/proibido, `ma_boca` Rei Subterrâneo, `dz_borda_do_vazio` fim do mundo,
    `sx_profundezas` dragão, `sk_fortaleza_vorr` Sopro de Vorr) NÃO escalam: perigo
    CHEIO. Nível-1 que acampa numa zona apex MORRE — é o "você não pertence aqui".
    Marcadas com a tag `"apex"` em `data/world_map.json`.
  - **Curva:** `eff = danger_real if apex else min(danger_real, (nível + 3) // 2)`
    (nível 1→2, 3→3, 5→4, 7+→cheio).
  - **Escopo:** só encontro FORÇADO. Combate DELIBERADO (jogador digita "ataco") e boss
    roteirizado usam perigo cheio (escolheu / é história).
  - **Fuga:** ACHADO ao testar (perfil `fujao`) — a fuga do jogador era VESTIGIAL:
    `combat.py:396` só BLOQUEAVA o caso ENREDADO; a fuga em si nunca era resolvida (o
    texto virava um ataque). **Implementada de verdade:** intent `fuj|fugir|escap|retir|
    recu|corr[oe]` (não-enredado) vira `action={"flee": True}` → `hero_fled` ENCERRA o
    combate (sem vitória/espólio/XP; inimigos ficam para trás). Quem age antes do herói
    na iniciativa ainda dá o golpe de despedida (risco justo). Storyteller sinaliza a
    saída quando o herói PERCEBE o encontro (`detection_check` ok). Perfil `fujao` (12º)
    e testes cobrem; smoke real: nível-1 fugiu de 2 Sapo-Boi e sobreviveu (14 HP).

### Fora de escopo

- Reescrever a economia de combate (dano base das criaturas) — R5 mexe só em TIER de
  spawn de encontro forçado, não em stats de criatura.
- Memória de longo prazo conversacional do NPC além da já existente (`query_npc_memory`).
- Traduzir lore já gerada (só a GERAÇÃO nova de beats; docs do Codex são separados).
- Qualidade narrativa subjetiva (só os 5 defeitos objetivos acima).

## 3. Design técnico

### Arquivos alterados

- `agents/campaign_manager.py` — R1: `Field(description=...)` → pt-BR; system prompt
  ganha linha "Responda SEMPRE em português do Brasil (pt-BR). NUNCA em inglês."
- `agents/npc.py` — R2: monta `<ULTIMA_FALA_SUA>` a partir de `npc_data['memory']` /
  histórico e injeta no system prompt + instrução anti-repetição.
- `playtest/profiles.py` — R3: `Quester._objetivo_curto(texto) -> str` (1ª frase, corta
  em ~80 chars, sem quebra de linha).
- `main.py` — R4: gate `game_over` na entrada do grafo (conditional edge de `START` ou
  short-circuit em `campaign_manager`/`dm_router` → `END`).
- `playtest/invariants.py` — R4: check novo `lifecycle.acts_after_game_over`
  (usa `prev_state`).
- `world_utils.py` — R5: `forced_encounter_danger(loc, danger_real, player_level)`;
  `check_encounter` recebe `player_level`, usa `eff` p/ `pick_encounter_enemy` E carimba
  `world["encounter_eff_danger"]` (one-shot, como `encounter_surprise`). O TRIGGER
  segue no danger REAL (encontro ainda dispara). Nudge de fuga quando `perceived`.
- `agents/storyteller.py` — R5: passa `player_level` ao `check_encounter`.
- `agents/combat.py` — R5: spawn lê `danger = world.pop("encounter_eff_danger", danger_level)`
  (forçado usa eff; deliberado usa danger_level cheio).
- `data/world_map.json` — R5: tag `"apex"` nas 5 zonas proibidas.

### Assinaturas

```python
# world_utils.py
def forced_encounter_danger(loc: dict, danger_real: int, player_level: int) -> int:
    """eff = danger_real se zona apex, senão min(danger_real, (nível+3)//2).
    Só a FORÇA do encontro escala; o TRIGGER continua no danger real."""

# playtest/profiles.py
class Quester(_Base):
    @staticmethod
    def _objetivo_curto(texto: str) -> str: ...
```

## 4. Plano passo a passo

### Etapa 1 — R3 + R1 (perfil + idioma; baratos, sem risco de motor)

1. **Testes:** `test_quester_acao_curta` (ação ≤ 160 chars mesmo com beat-prosa longa);
   `test_campaign_plan_descricoes_em_pt` (schema não tem descrição em inglês —
   heurística de palavras EN comuns). (`tests/test_fixes_playtest.py`)
2. **Implementação:** R3 em profiles.py, R1 em campaign_manager.
3. **Verificação:** `/qa` verde.

### Etapa 2 — R2 (NPC anti-repetição)

1. **Testes:** `test_npc_prompt_inclui_ultima_fala` (o system prompt do npc_actor contém
   a fala anterior do NPC quando há memória); mock exercita o caminho sem repetir campo.
2. **Implementação:** npc.py injeta última fala + instrução.
3. **Verificação:** `/qa` verde.

### Etapa 3 — R4 (gate de game_over)

1. **Testes:** `test_grafo_nao_processa_apos_game_over` (invoke com `game_over=True` →
   mensagens/estado inalterados, `next==END`); `test_invariante_acts_after_game_over`
   (prev game_over + estado mudou → violação).
2. **Implementação:** gate no grafo + invariante.
3. **Verificação:** `/qa` verde.

### Etapa 4 — R5 (perigo efetivo por nível + apex + fuga)

1. **Testes:** `test_eff_danger_escala_por_nivel` (nível-1 danger-4 → eff 2; nível-7 → 4);
   `test_eff_danger_apex_nao_escala` (zona com tag apex → eff = danger_real mesmo nível-1);
   `test_forcado_carimba_eff_deliberado_nao` (encontro forçado seta `encounter_eff_danger`,
   combate deliberado não → spawn no danger cheio); `test_zonas_apex_no_mapa` (as 5 ids
   têm tag apex).
2. **Implementação:** `forced_encounter_danger` + `check_encounter(player_level)` +
   spawn do combat + tags no mapa + nudge de fuga.
3. **Verificação:** `uv run pytest` completo; smoke real (§6).

## 5. Critérios de aceite

- [x] Beat gerado no LLM real vem em pt-BR (smoke: "Descreva o amanhecer sobre Nova Arcádia")
- [x] NPC com a MESMA pergunta 2× não devolve resposta idêntica (smoke: Eryndor variou/avançou)
- [x] Ação do `quester` ≤ 160 chars mesmo com beat-prosa longa (`test_r3_quester_acao_curta`)
- [x] Grafo com `game_over=True` não processa turno (smoke: morto congelou; invariante `lifecycle.acts_after_game_over` pega)
- [x] Nível-1 em encontro forçado danger-4 não enfrenta elite/boss (smoke: 2 Sapo-Boi minions, não Necromante); zona apex NÃO escala (`test_r5_apex_nao_escala`)
- [x] Fuga do jogador ENCERRA o combate (implementada; smoke: fujao fugiu vivo)
- [x] `uv run pytest` verde (715 testes, 0 falhas)
- [x] Guard de FallbackLLM — R5/fuga é 100% Python; R1/R2 são prompt (sem novo structured output)
- [x] Saves antigos continuam carregando (nada de schema muda)

## 6. Smoke test com LLM real

(consciente de quota; reusar `playtest transcript`)

1. `run --profile quester --turns 5 --real` → beats em pt-BR; `transcript` legível.
2. `run --profile diplomatico --turns 5 --real` (perguntar 2× a mesma coisa) → 2ª fala do
   NPC difere da 1ª.
3. `run --profile combate --turns 6 --real` → nível-1 não é one-shot por elite em encontro
   forçado; se morrer, é por atrito/escolha, não emboscada de elite.

## 7. Riscos & compatibilidade

- **Saves antigos:** R4 lê `game_over` (já existe desde a Fase 4.6); sem mudança de schema.
- **MockLLM:** R1/R2 são de prompt — o mock não muda (segue determinístico); os testes
  de R1/R2 checam o PROMPT/estrutura, não a saída do mock. R3/R4/R5 são 100% Python,
  cobertos offline.
- **Balanceamento (R5):** rebaixar tier deixa encontro forçado mais fácil no início —
  intencional (viajar sub-nivelado ≤ atacar tudo). Boss de história intacto (scripted).
- **Quota:** smoke reusa o harness `--real` (Groq free cobre).
