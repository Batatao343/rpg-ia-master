# SPEC — Conflito v2 #09: Fuga e Perseguição

> **Status:** `done` (2026-07-23) — motor puro aditivo (`services/chase.py`);
> substituir o fluxo `combat_flee_attempt`/`combat_flee_destination` e ajustar os
> perfis `fujao`/`quester` do playtest vão no cutover `conflito-13`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-23
> **Depende de:** `conflito-03-zonas-cena-objetos`, `conflito-04-turnos-iniciativa-ataques`,
> `conflito-06-reacoes-movimento`, `conflito-07-morte-rendicao-captura`
> (todas `done` antes de iniciar)
> **Desbloqueia:** `conflito-12` (resumo canônico inclui desfecho de fuga)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

A fuga do jogador já existe (`fix-playtest-achados`, perfis `fujao`/`quester`) mas
é simplificada: sem trilha de perseguição, sem teste de sorte dos companheiros,
sem simulação de abandono. `docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md`
§33-34 define uma trilha própria (Pressionado/Afastado/Quase Livre/Escapou), um
condutor (sempre o protagonista, com Virtude escolhida conforme abordagem), Teste
de Sorte por companheiro, abandono de companheiro com simulação automática de
destino, e sacrifício voluntário via traço.

## 2. Requisitos

- **R1** — Fugir custa a Ação. Pode ser declarado Engajado (dispara AoO de cada
  inimigo Engajado e capaz, `conflito-06` R5); se o personagem continua capaz de
  agir, inicia a fuga. Desengajar antes evita os ataques mas normalmente exige
  nova oportunidade pra iniciar a fuga (salvo Carta específica).
- **R2** — Trilha de perseguição: **Pressionado → Afastado → Quase Livre →
  Escapou**. Posição inicial deriva da distância no momento da fuga (Próximo→
  Pressionado, Distante→Afastado, Separado→Quase Livre). Se o fugitivo recuar
  abaixo de Pressionado, é alcançado e o combate normal retorna.
- **R3** — Perseguição só acontece se o perseguidor decidir seguir, conforme seu
  `TacticalProfile` (`conflito-08`) — ex. predador faminto tende a perseguir,
  guardião não abandona o posto, mercenário ferido pode desistir.
- **R4** — Condutor: o protagonista sempre conduz a fuga da party, escolhendo
  abordagem+Virtude coerente (Agilidade=correr/desviar, Mente=rotas/atalhos,
  Força=romper obstáculos, Corpo=resistência prolongada, Carisma=coordenar/
  mobilizar ajuda). Dificuldade depende do perseguidor principal.
- **R5** — Companheiros fazem Teste de Sorte (1d10): 1-2 Complicação, 3-8 Neutro,
  9-10 Ajuda. Ajuda e Complicação se anulam; saldo positivo = Vantagem, negativo =
  Desvantagem, empate = teste normal. Não acumula além de 1 Vantagem/Desvantagem.
- **R6** — Antes do teste principal, jogador pode abandonar um companheiro que
  gerou Complicação — remove a Complicação, separa o NPC da party, altera como
  ele e outros NPCs percebem o protagonista. Destino resolvido por **simulação
  automática completa** (estado, perfil, terreno, perseguidores, seed) com
  resultado ∈ {fuga, captura, rendição, esconderijo, combate, morte, reencontro
  futuro} — tudo determinístico, sem LLM durante a simulação.
- **R7** — Sacrifício voluntário: só um companheiro com traço apropriado (ex.
  `se_sacrifica_pelo_grupo`) em prioridade válida pode se oferecer pra ficar.
  Jogador aceita ou recusa. Percepção dos NPCs depende de valores/relação/
  contexto — sem penalidade automática universal.
- **R8** — Ataques durante perseguição: à distância continua Ação normal. Corpo a
  corpo exige reengajamento — em Pressionado, perseguidor usa Pré-Ação pra
  Engajar (encerra a perseguição, combate normal retorna) e ataca com a Ação. Em
  Afastado/Quase Livre precisa primeiro reduzir distância ou usar Carta
  específica.

### Fora de escopo

Rendição/captura em si (já coberto por `conflito-07`); resumo canônico da fuga pra
LLM (`conflito-12`); Reações durante perseguição além das já definidas em
`conflito-06`.

## 3. Design técnico

**Arquivos novos:**
- `services/chase.py` — `ChaseState = {trilha: Literal["pressionado","afastado",
  "quase_livre","escapou"], perseguidores: List[str]}`, `start_chase(scene,
  fugitive_id) -> ChaseState`, `resolve_chase_round(chase, condutor_virtude,
  companion_luck_rolls) -> ChaseState`, `simulate_abandoned_companion(companion,
  scene_state, seed) -> AbandonOutcome` (determinístico, reusa RNG seeded como o
  resto do playtest/harness).

**Arquivos alterados:**
- `agents/combat.py`/nó de fuga — integra `services/chase.py`; substitui o fluxo
  simplificado atual de `combat_flee_attempt`/`combat_flee_destination`.

**Schema:**
```python
class AbandonOutcome(TypedDict):
    resultado: Literal["fuga","captura","rendicao","esconderijo",
                        "combate","morte","reencontro_futuro"]
    fatos_relacionais: List[str]  # pra conflito-12 (resumo canônico)
```

## 4. Plano passo a passo

### Etapa 1 — Trilha de perseguição
1. **Testes** (`tests/test_conflito_fuga.py`): `test_posicao_inicial_deriva_da_distancia`;
   `test_recuar_abaixo_de_pressionado_e_alcancado`; `test_perseguidor_so_persegue_se_perfil_permitir`.
2. **Implementação:** `services/chase.py`.

### Etapa 2 — Condutor + Virtude
1. **Testes:** `test_condutor_e_sempre_protagonista`; `test_dificuldade_depende_do_perseguidor_principal`.
2. **Implementação:** idem.

### Etapa 3 — Teste de Sorte dos companheiros
1. **Testes:** `test_1d10_faixas_complicacao_neutro_ajuda`; `test_ajuda_e_complicacao_se_anulam`;
   `test_nao_acumula_alem_de_uma_vantagem`.
2. **Implementação:** idem.

### Etapa 4 — Abandono + simulação automática
1. **Testes:** `test_abandonar_remove_complicacao_separa_npc`; `test_simulacao_e_deterministica_por_seed`
   (mesma seed → mesmo resultado); `test_resultado_gera_fatos_relacionais`.
2. **Implementação:** `simulate_abandoned_companion`.

### Etapa 5 — Sacrifício voluntário + ataques em perseguição
1. **Testes:** `test_sacrificio_so_com_traco_e_prioridade_valida`; `test_jogador_pode_recusar_sacrificio`;
   `test_ataque_distancia_continua_acao_normal_em_perseguicao`; `test_reengajar_em_pressionado_encerra_perseguicao`.
2. **Implementação:** idem.

## 5. Critérios de aceite

- [x] Trilha de perseguição avança/recua corretamente conforme testes/ações
  (`resolve_chase_round`; abaixo de Pressionado = alcançado).
- [x] Teste de Sorte dos companheiros aplica Vantagem/Desvantagem corretamente
  (`luck_roll`/`luck_to_advantage`, cap ±1).
- [x] Abandono simula destino automaticamente e de forma reproduzível (mesma
  seed = mesmo resultado) — `simulate_abandoned_companion` com `random.Random(seed)`.
- [x] `uv run pytest` verde — **1199 passed** (+17 `test_conflito_fuga`).

## 6. Smoke test com LLM real

1. Combate real: jogador foge Engajado, sofre AoO, entra em perseguição
   Pressionado, reengaja e retorna ao combate normal.
2. Abandonar companheiro num teste real — confirmar narração reflete o resultado
   da simulação (não inventa outro desfecho).

## 7. Riscos & compatibilidade

- Substitui o fluxo de fuga simplificado atual (`combat_flee_attempt`/
  `combat_flee_destination`, spec `fix-playtest-achados`) — os perfis de playtest
  `fujao`/`quester` precisam de ajuste coordenado com `conflito-13`.
- Simulação de abandono precisa ser determinística por seed pra manter a garantia
  de reprodutibilidade do épico (doc 03, Cenário 53) — não introduzir
  `random.random()` sem seed.
