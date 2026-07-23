# SPEC — Conflito v2 #02: Cartas, Acervo e Preparação

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-01-virtudes-vitalidade` (`done` antes de iniciar)
> **Desbloqueia:** `conflito-04` (ataques usam Carta+Virtude), `conflito-06`
> (Reação é tipo de Carta), `conflito-14`/`conflito-15` (autoria de conteúdo usa
> este schema)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Hoje `known_abilities: List[str]` + `data/player_abilities.json` (101 habilidades:
41 ativas + 35 passivas + 25 utilitárias, `ability_kind`) definem o que o jogador
pode fazer em combate; `ability_cooldowns: Dict[str,int]` controla recarga por
habilidade individual.

`docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md` §9–10 substitui isso por
**Cartas**: um Acervo (conhecidas) maior que os slots **Preparados** (4/5/6/7 por
faixa de nível), frequência por carta (Livre / 1×turno / 1×cena / 1×descanso curto
/ 1×descanso longo — não mais cooldown numérico solto), **Ruptura** (versão extrema
declarada antes da rolagem, Caminho A/B a partir do nível 4) e **Cartas de
Virtude** (2 escolhidas na criação, permanentes, fora da preparação, evoluem com a
Virtude relacionada).

Esta spec define o **schema e o motor de gestão** de Cartas (Acervo/Preparação/
Ruptura/frequência). Não autora as ~100+ cartas de conteúdo — isso é
`conflito-14-autoria-cartas-classes` — mas cria ~3-5 cartas de exemplo por
classe suficientes para os testes do motor.

## 2. Requisitos

- **R1** — Nova estrutura `Carta` (substitui o formato de `player_abilities.json`):
  `id, name, tipo ("ativa"|"passiva"|"utilitaria"|"reacao"), classe, subclasse,
  patamar ("inicial"|"avancado"|"superior"), custo_entropia, frequencia ("livre"|
  "turno"|"cena"|"descanso_curto"|"descanso_longo"), virtude_permitida: List[str],
  efeito: {kind, ...} (mesmo catálogo fechado usado pela preparação de cena —
  `conflito-03`), ruptura: Optional[{caminho_a, caminho_b}]`.
- **R2** — Acervo (`known_cards: List[str]`) vs Preparadas (`prepared_cards:
  List[str]`, tamanho máximo por nível):

  | Nível | Cartas preparadas |
  |---|---:|
  | 1–3 | 4 |
  | 4–6 | 5 |
  | 7–9 | 6 |
  | 10 | 7 |

- **R3** — Nível 1: escolhe 6 cartas (classe+subclasse) para o Acervo, prepara 4.
  Sem divisão mínima obrigatória entre classe/subclasse.
- **R4** — A cada nível, escolhe: nova carta de classe/subclasse **ou** evolução de
  carta já conhecida (Caminho A/B a partir do nível 4, substituição permanente e
  única — sem mistura, sem segunda evolução).
- **R5** — Reorganização da preparação é livre fora de combate, quando seguro e sem
  ameaça imediata (gate determinístico reaproveitando a mesma noção de "zona
  segura" já usada em `world_utils`/`recovery_rest_safe`).
- **R6** — Frequência é por carta, controlada por contador próprio (substitui
  `ability_cooldowns` genérico): `card_usage: Dict[str, {used_this_turn, used_this_scene,
  used_since_short_rest, used_since_long_rest}]`, resetado no gatilho certo
  (turno/cena/descanso).
- **R7** — Cartas de Virtude: exatamente 2 escolhidas na criação (mesma Virtude ou
  diferentes), permanentes, fora dos slots preparados, nunca reconquistadas depois,
  evoluem por estágio da Virtude relacionada (1–2 = Estágio I, 3–4 = Estágio II, 5 =
  Estágio III).
- **R8** — Ruptura: declarada antes da rolagem; paga custo normal + gera 1 Carga do
  Abismo mesmo em falha; a Carga gerada não afeta a própria Ruptura; sem limite
  geral por cena (só frequência/custo/recurso limitam).
- **R9** — Quando uma carta permite mais de uma Virtude (ex. arma versátil), a
  escolha é feita ao preparar e persiste até a próxima reorganização.

### Fora de escopo

Resolução de ataque em si (`conflito-04`); autoria completa das ~100 cartas de
conteúdo (`conflito-14`); Reações em cadeia (`conflito-06` — aqui só o `tipo:
"reacao"` existe no schema); UI de gestão de mão/Acervo (`conflito-16`).

## 3. Design técnico

**Arquivos novos:**
- `services/cards.py` — `prepare_slots_for_level(level) -> int`, `can_reorganize
  (state) -> bool`, `use_card(state, card_id) -> Result` (checa frequência+custo,
  incrementa `card_usage`), `reset_card_usage(state, scope)` (turno/cena/descanso),
  `evolve_card(state, card_id, caminho: Literal["A","B"])`.
- `data/cards/` (novo diretório) — cartas de exemplo por classe/subclasse no schema
  R1 (3-5 por classe pra cobrir os testes; substitui incrementalmente
  `data/player_abilities.json` — o arquivo antigo só é removido na
  `conflito-13-cutover`).

**Arquivos alterados:**
- `state.py` — `PlayerStats.known_cards/prepared_cards/card_usage/virtue_cards:
  List[{card_id, virtude, estagio}]` substituem `known_abilities`/
  `ability_cooldowns`.
- `character_creator.py` — fluxo de escolha das 6 cartas iniciais + preparo de 4 +
  2 Cartas de Virtude.
- `gamedata.py` — tabela `PREPARED_SLOTS_BY_LEVEL`.

## 4. Plano passo a passo

### Etapa 1 — Schema `Carta` + `services/cards.py`
1. **Testes** (`tests/test_conflito_cartas.py`): `test_prepare_slots_for_level`
   (4/5/6/7); `test_use_card_respects_frequency` (1×cena não pode 2x na mesma
   cena); `test_use_card_respects_custo_entropia`.
2. **Implementação:** módulo novo + 3-5 cartas de exemplo por classe em
   `data/cards/`.

### Etapa 2 — Criação de personagem com Cartas
1. **Testes:** nível 1 escolhe 6, prepara 4; distribuição livre entre
   classe/subclasse aceita; 2 Cartas de Virtude escolhidas e marcadas permanentes.
2. **Implementação:** `character_creator.py`.

### Etapa 3 — Progressão e evolução
1. **Testes:** nível 4 pode evoluir Caminho A **ou** B (não ambos); segunda
   tentativa de evolução na mesma carta é rejeitada; escolha de carta nova vs
   evolução é mutuamente exclusiva por nível.
2. **Implementação:** hook de level-up.

### Etapa 4 — Reorganização fora de combate
1. **Testes:** reorganização permitida em zona segura sem ameaça; rejeitada em
   combate ativo ou zona perigosa com ameaça iminente.
2. **Implementação:** gate reaproveitando lógica de segurança existente.

### Etapa 5 — Ruptura
1. **Testes:** Ruptura declarada antes da rolagem gera 1 Carga mesmo em falha; a
   Carga gerada não pode ser gasta pela própria Ruptura que a gerou (ordem de
   aplicação testada).
2. **Implementação:** `services/cards.py` + integração com `abyss_charge`.

## 5. Critérios de aceite

- [ ] Personagem nível 1 tem 6 cartas no Acervo, 4 preparadas, 2 Cartas de Virtude
  permanentes.
- [ ] Preparar/trocar carta fora de combate funciona; em combate/perigo é
  bloqueado.
- [ ] Frequência por carta é respeitada (turno/cena/descanso curto/longo).
- [ ] Ruptura gera Carga mesmo em falha, carga nova não afeta a própria Ruptura.
- [ ] Evolução Caminho A/B é permanente e única a partir do nível 4.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

N/A — módulo 100% determinístico. Validar manualmente que `character_creator` real
ainda gera personagem plausível com o novo fluxo de escolha de cartas (sem
`with_structured_output` novo para as cartas em si, que são catálogo fechado).

## 7. Riscos & compatibilidade

- `data/player_abilities.json` atual (101 habilidades) fica temporariamente órfão
  até `conflito-14` reautorar tudo no schema novo — não apagar até lá.
- `ability_cooldowns` é usado por vários callsites de `combat_mechanics.py` hoje
  (spend_resources, tick_cooldowns) — precisa de auditoria de remoção coordenada
  com `conflito-04`.
- Reorganização fora de combate depende de uma noção de "seguro" que hoje vive
  espalhada (`world_utils.recovery_rest_safe`, danger_level) — reusar, não duplicar.
