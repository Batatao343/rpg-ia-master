# SPEC — Mapa robusto: interiores (masmorras/prédios) + tempo de viagem variável

> **Status:** `draft`
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 2.5b (mapa de Valoria 30 nós) `done`; Fase 6.5 (clima) `done`
> **Desbloqueia:** dungeons com fog of war próprio; ritmo de viagem realista; item "Mapa robusto — restante" do backlog

---

## 1. Contexto & Objetivo

O mapa tem 30 nós (12 regiões + 18 sublocais tipo `na_anel_dourado`), mas é
**plano em custo e em profundidade**: toda viagem custa exatamente 1 período
(`apply_travel` → `advance_clock(world, 1)`), então atravessar Valoria de
Skallgard ao Deserto de Zhur custa o mesmo que ir do Anel de Lama ao Anel de
Ferro — o mundo perde escala. E não existe camada de **interior** (masmorra,
taverna, cripta): tudo que é "dentro" vira narração sem estado, sem fog of war
e sem perigo próprio.

Esta spec entrega os dois itens restantes do backlog "Mapa robusto": (a)
`travel_time` por conexão (dado curado, default 1; movimento dentro da mesma
cidade custa 0 — não vira o relógio), e (b) nós `kind: "interior"` — poucos,
curados, conectados a um sublocal pai, com regras próprias (sem clima, sem
encontro de viagem, revelados só ao entrar). Tudo determinístico em
`world_utils.py`/`data/world_map.json` — zero LLM novo.

Princípio: **mecânica é Python** — custo de viagem e transição de camada são
dados + código, o LLM só narra a chegada.

## 2. Requisitos

- **R1 — travel_time por conexão:** nó pode declarar
  `"travel_times": {"<dest_id>": <int ≥ 0>}`; conexão sem entrada = 1.
  Simetria por fallback: se A define custo p/ B e B não define p/ A, vale o
  de A. `apply_travel` usa o custo da conexão em vez do 1 fixo.
- **R2 — custo 0 é intra-urbano:** viagem com custo 0 NÃO vira o relógio, NÃO
  transiciona clima e NÃO rola encontro de viagem (`check_encounter` só em
  custo ≥ 1). Ainda revela o destino (fog of war) e atualiza danger.
- **R3 — custos curados no mapa real:** conexões entre anéis de Nova Arcádia e
  entre sublocais da mesma região = 0; região↔região vizinha = 1; travessias
  longas curadas ≥ 2 (ex.: `skallgard ↔ montanhas_afiadas` 2,
  `deserto_zhur ↔ ophidia` 3). Tabela completa é entrega da spec (curadoria
  em `data/world_map.json`, revisada à mão).
- **R4 — clima encarece só viagem real:** `travel_cost_extra` do clima (6.5)
  aplica apenas quando custo base ≥ 1 (nevasca não atrasa quem cruza a rua).
- **R5 — nós interior:** campo `"kind": "interior"` + `"parent_id": <sublocal>`;
  conexões de interior só para o pai ou outros interiores do mesmo pai
  (validado); custo sempre 0; SEM clima (conta como abrigo p/ miasma 6.5,
  que já respeita abrigo); `danger` próprio (masmorra perigosa dentro de
  cidade segura).
- **R6 — interiores curados iniciais:** 4–6 no mapa real, ex.:
  `na_taverna_javali` (taverna do Grum, Anel de Lama),
  `pm_cripta_afogada` (masmorra no Pântano), `br_forja_profunda` (Brekmar),
  `sk_salao_jarl` (Skallgard). Ids/nomes finais na implementação, ancorados
  no Codex existente.
- **R7 — mapa do frontend:** interior NÃO aparece no `WorldMap` de Valoria
  (nem como fog); aparece como lista "Locais daqui" do local atual (API
  `/data/map` ganha `interiors` por nó ou endpoint de vizinhos). Dentro de um
  interior, o HUD mostra o caminho de volta ("Sair para <pai>").
- **R8 — validação de dados:** teste offline valida o mapa real: grafo
  conexo na camada não-interior; `travel_times` só referencia conexões
  existentes; interior obedece R5; custo 0 fora de interior só entre nós do
  mesmo `region_id`.
- **R9 — compatibilidade:** save antigo com `current_location_id` válido
  carrega sem mudança; `find_travel_destination` continua achando destinos
  por nome/alias incluindo interiores (quando visíveis: interior só é
  destino válido se o jogador está no pai ou num irmão).

### Fora de escopo

- Geração procedural de dungeons (interiores são autorais, poucos).
- Mapa visual de interior no frontend (lista textual basta nesta fatia).
- Tempo de viagem afetado por montaria/habilidade (não existe montaria).
- Rebalancear economia 6.1 por custo de rota (BFS continua por conexões).

## 3. Design técnico

### Arquivos alterados

- `data/world_map.json` — `travel_times` nos nós (R3), novos nós interior (R6).
- `world_utils.py` — `travel_cost(origem, dest_id)`, `apply_travel` usa custo
  (0 → sem clock/clima/encontro), `find_travel_destination` filtra interior
  fora de alcance; `weather_effects` já tem noção de abrigo (interior conta).
- `gamedata.py` — helpers de mapa: `get_location`, vizinhos com custo,
  `interiors_of(loc_id)`.
- `api.py` — `/data/map` exclui `kind == "interior"` dos nós do mapa e expõe
  `interiors` do local atual em `/game/state` (bloco `world`).
- `web/` — lista "Locais daqui" + botão "Sair para <pai>" (componente pequeno
  no painel de localização; sem mexer no `WorldMap` além do filtro).
- `tests/test_mapa_interiores.py` — novo.

### Formato de dado (exemplo real)

```json
{
  "id": "na_anel_lama",
  "name": "Anel de Lama",
  "region_id": "nova_arcadia",
  "connections": ["nova_arcadia", "na_anel_ferro", "na_taverna_javali"],
  "travel_times": {"nova_arcadia": 0, "na_anel_ferro": 0, "na_taverna_javali": 0}
},
{
  "id": "na_taverna_javali",
  "name": "Taverna do Javali Dourado",
  "kind": "interior",
  "parent_id": "na_anel_lama",
  "region_id": "nova_arcadia",
  "danger": 0,
  "connections": ["na_anel_lama"],
  "tags": ["taverna", "abrigo"],
  "lore_seed": "A taverna de Grum no Anel de Lama; um barril no canto esquerdo guarda mais do que cerveja."
}
```

### Assinaturas

```python
# world_utils.py
def travel_cost(world: dict, dest: dict) -> int:
    """Custo em períodos da conexão atual->dest (R1: travel_times, fallback
    simétrico, default 1). Interior -> sempre 0."""

def apply_travel(world: dict, dest: dict) -> dict:
    """Como hoje, mas: custo = travel_cost; custo 0 pula advance_clock/
    advance_weather/extra de clima; custo N vira o relógio N vezes."""

# gamedata.py
def interiors_of(loc_id: str) -> list[dict]: ...
```

## 4. Plano passo a passo

### Etapa 1 — travel_cost + apply_travel

1. **Testes** (`tests/test_mapa_interiores.py`): `test_custo_default_1`;
   `test_custo_declarado_e_usado` (mapa fixture custo 3 → relógio anda 3);
   `test_custo_simetrico_fallback`; `test_custo_zero_nao_vira_relogio`
   (clock/clima intactos, visited atualiza); `test_encontro_so_em_custo_1_mais`;
   `test_clima_extra_so_em_custo_1_mais`.
2. **Implementação:** `travel_cost` + mudanças no `apply_travel`.
3. **Verificação:** `/qa` verde (suíte de Fase 0/6.5 intacta).

### Etapa 2 — camada interior

1. **Testes:** `test_interior_so_alcancavel_do_pai`;
   `test_interior_nao_alcancavel_de_outra_regiao`;
   `test_interior_conta_como_abrigo` (miasma 6.5 não morde);
   `test_interior_tem_danger_proprio`; `test_sair_para_o_pai`.
2. **Implementação:** filtro em `find_travel_destination` + `interiors_of`.
3. **Verificação:** `/qa` verde.

### Etapa 3 — dados reais + validação R8

1. **Testes:** `test_mapa_real_valido` (R8 completo — conexo, travel_times
   íntegros, interiores bem formados, custo 0 só intra-região).
2. **Implementação:** curadoria do `world_map.json` (custos + 4-6 interiores
   ancorados no Codex).
3. **Verificação:** `uv run pytest` completo.

### Etapa 4 — API + frontend

1. **Testes:** `test_data_map_sem_interiores`; `test_game_state_lista_interiores`.
2. **Implementação:** api.py + componente web + `npm run build`.
3. **Verificação:** suíte + `bash scripts/smoke_api.sh` + jogar 3 turnos no
   navegador (entrar/sair da taverna).

## 5. Critérios de aceite

- [ ] Viagem Skallgard→Montanhas custa 2 períodos; Anel de Lama→Anel de Ferro custa 0 (relógio parado)
- [ ] Entrar na taverna: sem encontro, sem transição de clima, miasma não morde (abrigo)
- [ ] Interior não aparece no mapa de Valoria; aparece em "Locais daqui"; "Sair" volta ao pai
- [ ] `test_mapa_real_valido` verde (dados curados íntegros)
- [ ] `uv run pytest` verde (suíte completa offline) + `npm run build` ok
- [ ] Guard de FallbackLLM — N/A (zero LLM novo)
- [ ] Saves antigos continuam carregando (R9)

## 6. Smoke test com LLM real

(2–3 requests FAST)

1. Novo jogo em Nova Arcádia; "vou até a Taverna do Javali Dourado" →
   storyteller narra a entrada; relógio NÃO virou; HUD mostra o interior.
2. "saio da taverna e viajo para o Pântano da Melancolia" → narração de
   viagem; relógio virou 1+ período; clima pode ter transicionado.
3. Conferir no save: `visited` contém o interior; `current_location_id` correto.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo removido; locais existentes intactos —
  interiores são nós NOVOS. Save em nó antigo carrega igual.
- **Balanceamento:** custo 0 intra-urbano remove descanso "grátis" de andar
  de anel em anel? Não — descanso é ação própria (`apply_rest`), inalterada.
  Viagens longas (custo 3) consomem mais recursos/clima — desejado, observar
  no playtest.
- **`find_travel_destination` por texto:** interior com nome longo precisa de
  alias curto ("taverna") — usar o mesmo fold de acentos já existente.
- **MockLLM/FallbackLLM:** irrelevante (mecânica pura). **Quota:** smoke 2-3
  requests.
