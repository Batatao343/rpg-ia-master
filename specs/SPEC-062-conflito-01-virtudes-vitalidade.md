# SPEC — Conflito v2 #01: Virtudes, Vitalidade e Ferimentos (fundação de dados)

> **Status:** `done` (2026-07-22)
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** nenhuma — fundação do épico de migração do sistema de conflitos
> **Desbloqueia:** todas as demais specs `conflito-02` a `conflito-16`
> **Épico:** Migração do Sistema de Conflitos de Valoria — ver `docs/valoria_conflict_migration_v2/` (fonte funcional) e ROADMAP § Migração do Sistema de Conflitos

---

## 1. Contexto & Objetivo

O sistema atual de personagem usa 6 atributos estilo D&D (`str/dex/con/int/wis/cha`,
chaves longas normalizadas por `combat_mechanics.normalize_attr`/`_ATTR_ALIASES`),
HP simples (`hp/max_hp`), Entropia (pool único pós-`refatoracao-sistema-classes`) e
Carga do Abismo (`abyss_charge`) sem Ferimentos localizados.

`docs/valoria_conflict_migration_v2/01_VALORIA_REGRAS_CONSOLIDADAS_CONFLITOS.md`
(§8) substitui os 6 atributos por **5 Virtudes** (Mente/Agilidade/Força/Carisma/Corpo,
0–5) e o HP simples por **Vitalidade + Ferimentos localizados** (Leve/Grave/Crítico)
derivados de Corpo. Esta spec é a fundação de dados do épico inteiro: sem ela,
nenhuma spec seguinte (ataques, dano, cartas, IA tática, preparação de encontro) tem
schema pra escrever em cima.

**Decisão fechada (não reabrir, confirmada com o usuário em 2026-07-22):** corte
definitivo. Saves com `schema_version` anterior ao novo ficam órfãos e são
arquivados — mesmo precedente já usado no projeto (saves pré-2.5b). Não há
heurística de conversão automática dos 6 atributos antigos para as 5 Virtudes.

## 2. Requisitos

- **R1** — `PlayerStats` ganha `virtudes: Dict[str, int]` com chaves exatas
  `mente/agilidade/forca/carisma/corpo`, cada uma 0–5.
- **R2** — Criação de personagem distribui **4/3/2/1/1** livremente entre as 5
  Virtudes. Classe apenas recomenda uma distribuição (flavor), nunca força.
- **R3** — Nível máximo 10. Nos níveis **2, 4, 6, 8, 10** o jogador escolhe +1 em
  uma Virtude, respeitando teto 5.
- **R4** — Vitalidade máxima e espaços de Ferimento (Leve/Grave/Crítico) derivam de
  Corpo via tabela fixa (doc 01 §8.1):

  | Corpo | Vitalidade | Leves | Graves | Críticos |
  |---:|---:|---:|---:|---:|
  | 0 | 6 | 2 | 1 | 1 |
  | 1 | 8 | 3 | 1 | 1 |
  | 2 | 10 | 3 | 2 | 1 |
  | 3 | 12 | 4 | 2 | 2 |
  | 4 | 14 | 4 | 3 | 2 |
  | 5 | 16 | 5 | 3 | 3 |

  Recalcula imediatamente ao subir Corpo (nunca em lazy-load).
- **R5** — Limites de Gravidade (faixa de excedente de dano → categoria de
  Ferimento) derivam de Corpo (doc 01 §8.1):

  | Corpo | Leve | Grave | Crítico |
  |---:|---:|---:|---:|
  | 0 | 1–3 | 4–6 | 7+ |
  | 1 | 1–4 | 5–8 | 9+ |
  | 2 | 1–5 | 6–10 | 11+ |
  | 3 | 1–6 | 7–12 | 13+ |
  | 4 | 1–7 | 8–14 | 15+ |
  | 5 | 1–8 | 9–16 | 17+ |

- **R6** — Carga do Abismo formalizada como reservatório único sem máximo, nunca
  decai automaticamente, sempre visível ao jogador (já existe como `abyss_charge` —
  esta spec só formaliza o contrato, sem mudar o campo).
- **R7** — `EnemyStats`/companheiros ganham campo opcional `virtudes` (mesmo
  formato). Preenchimento completo (Vitalidade/Ferimentos por criatura) é escopo da
  `conflito-05` e `conflito-15` — aqui só o campo existir no schema.
- **R8** — `attributes` (6 chaves antigas) e `normalize_attr`/`_ATTR_ALIASES` saem de
  todo caminho de produção do **jogador**. `mana/max_mana`+`stamina/max_stamina`
  residuais do jogador (não lidos desde a Entropia) são removidos do schema do
  jogador — `EnemyStats` pode manter até a `conflito-04`/`05` decidirem o destino
  final desses campos para inimigos.
- **R9** — `schema_version` avança para **v4**. A migração v3→v4 é um
  "hard cutover": detecta versão antiga, **não** tenta inventar Virtudes a partir de
  atributos, marca o save como órfão.
- **R10** — Saves com `schema_version<4` não são jogáveis no fluxo normal. A API/CLI
  oferece só leitura/arquivamento (mesmo padrão comunicado em `ESTADO_ATUAL.md` para
  saves pré-2.5b: "ficam órfãos, arquivar"), nunca crash.

### Fora de escopo

Fórmula de ataque e resolução de dano (`conflito-04`/`05`); Ferimentos efetivamente
aplicados em combate (`conflito-05`); Cartas e recursos de preparo (`conflito-02`);
UI (`conflito-16`); conversão de `EnemyStats`/bestiário completo (`conflito-15`).

## 3. Design técnico

**Arquivos alterados:**
- `state.py` — `PlayerStats.virtudes: Dict[str,int]` substitui `attributes`;
  remove `mana/max_mana/stamina/max_stamina` do jogador; `EnemyStats.virtudes:
  Optional[Dict[str,int]]` novo campo.
- `combat_mechanics.py` — remove `normalize_attr`/`_ATTR_ALIASES` e todo callsite
  que lê `attributes` do jogador (grep exaustivo antes de deletar — dezenas de
  callsites hoje, ex. `compute_player_combat_stats`).
- `gamedata.py` — novas constantes `VITALIDADE_POR_CORPO`, `ESPACOS_FERIMENTO_POR_CORPO`
  (`{leve,grave,critico}`), `LIMITES_GRAVIDADE_POR_CORPO` (`{leve:(min,max),
  grave:(min,max), critico:(min,None)}`), valores da tabela acima.
- `character_creator.py` — distribuição de Virtudes 4/3/2/1/1 na criação (validação
  determinística, rejeita distribuição fora do multiset); Cartas de Virtude ficam
  como placeholder vazio até `conflito-02`.
- `persistence.py` — nova entrada em `_MIGRATIONS[4]`: função pura que detecta
  `schema_version<4`, retorna save marcado `archived=True` (não converte).
- `data/classes.json` — `base_stats.attributes` (6 chaves) vira
  `base_stats.virtudes` (5 chaves), valor = recomendação de distribuição por
  classe (não vinculante).
- `api.py`/`game_engine.py` — wizard de criação usa Virtudes em vez de atributos.

**Schema novo:**
```python
class Virtudes(TypedDict):
    mente: int
    agilidade: int
    forca: int
    carisma: int
    corpo: int
```

## 4. Plano passo a passo

### Etapa 1 — Tabelas em `gamedata.py`
1. **Testes** (`tests/test_conflito_virtudes.py`): `test_vitalidade_por_corpo` checa
   as 6 linhas; `test_espacos_ferimento_por_corpo`; `test_limites_gravidade_por_corpo`.
2. **Implementação:** constantes conforme R4/R5.
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — Schema `PlayerStats`/`EnemyStats`
1. **Testes:** cria `PlayerStats` mínimo com `virtudes`, Vitalidade derivada bate
   com a tabela; `EnemyStats.virtudes` aceita `None`.
2. **Implementação:** editar `state.py`.

### Etapa 3 — `character_creator.py`
1. **Testes:** distribuição válida aceita; distribuição inválida (ex. `4,4,2,1,1`
   ou soma errada) rejeitada com erro claro.
2. **Implementação:** validação determinística da distribuição 4/3/2/1/1.

### Etapa 4 — Progressão por nível par
1. **Testes:** subir Corpo 2→3 no nível 4 aumenta Vitalidade 10→12 na hora; escolha
   acima do teto 5 é rejeitada; níveis ímpares não oferecem a escolha.
2. **Implementação:** hook de level-up.

### Etapa 5 — Migração v3→v4 (hard cutover)
1. **Testes:** carregar save `schema_version=3` não crasha, retorna
   estado somente-leitura marcado `archived`; tentar `/game/action` num save
   arquivado recusa com mensagem clara (não 500).
2. **Implementação:** `_MIGRATIONS[4]` + guard na API/engine.

### Etapa 6 — Remoção de `attributes`/`normalize_attr` do jogador
1. **Testes:** suíte completa continua verde sem nenhum acesso a `attributes` de
   jogador em produção (grep de auditoria como teste, similar ao `HANDLED_KINDS`).
2. **Implementação:** remoção + ajuste de todo callsite.

## 5. Critérios de aceite

- [x] Personagem novo nasce com Virtudes 4/3/2/1/1 distribuídas pelo jogador,
  Vitalidade/espaços de Ferimento corretos para o Corpo escolhido.
- [x] Subir de nível par aumenta 1 Virtude (jogador escolhe), nunca passa de 5,
  recalcula Vitalidade na hora.
- [x] Save `schema_version<4` não é jogável no fluxo normal — mensagem clara de
  arquivamento, sem crash.
- [x] Nenhum consumidor de produção lê mais `attributes`/chaves longas do jogador
  (teste de auditoria `test_nenhum_read_de_attributes_do_jogador_em_producao`).
- [x] `uv run pytest` verde — **1045 passed, 1 skipped** (suíte completa offline).

## 5.1 Desvios de implementação (registrados no mesmo commit — CLAUDE.md §3)

- **`normalize_attr`/`_ATTR_ALIASES` PERMANECEM** em `combat_mechanics.py`: R8
  mantém `attributes` no `EnemyStats` até a `conflito-04/05`, e o inimigo ainda
  usa `attr_mods`/`normalize_attr`. A remoção do JOGADOR foi feita via ponte
  `actor_mods(actor)` (Virtude→mod para o player; `attr_mods` para o inimigo) +
  `virtude_mods`. A remoção total desses helpers volta na `conflito-04/05`.
- **`hp/max_hp` legado CONVIVE com `vitalidade/max_vitalidade`**: spec 01 é
  fundação de dados; o motor antigo (removido só no cutover `conflito-13`) ainda
  lê `hp`. A criação espelha `hp = max_hp` e adiciona a Vitalidade nova. A
  `conflito-05` aposenta `hp` quando os Ferimentos virarem a saúde real.
- **Raça NÃO altera Virtudes**: `attr_bonus` racial (dados D&D legado) foi
  DESLIGADO — num Virtude 0–5 um +1/+2 é salto grande demais e quebra a
  distribuição 4/3/2/1/1. Raça segue pesando em hp/defesa/resist/save/itens;
  bônus racial de Virtude fica para um rework de raças dedicado. `save_bonus`
  racial passou a ser chaveado por Virtude (`con→corpo`, `wis→mente`).
- **Level gains do jogador**: mana/stamina saíram; o jogador sobe **hp + Entropia**
  por nível (curva da classe). `MAX_LEVEL` caiu de 20 para 10 (R3).

## 6. Smoke test com LLM real

N/A nesta spec — 100% determinístico, sem `with_structured_output` novo. Único
ponto de contato com LLM é `character_creator` (nome/descrição textual, já
existente); confirmar manualmente que a criação real ainda produz personagem
plausível com Virtudes preenchidas.

## 7. Riscos & compatibilidade

- Quebra **todos** os saves existentes de propósito (decisão fechada com o
  usuário) — comunicar claramente na UI/CLI, nunca crash silencioso.
- Toda spec seguinte do épico depende deste schema — atraso aqui atrasa o épico
  inteiro; priorizar revisão rápida.
- Superfície de remoção de `attributes` é ampla (`combat_mechanics.py` tem dezenas
  de callsites hoje) — grep exaustivo antes de deletar, não confiar em memória.
- `EnemyStats` mantém `attributes` residual até `conflito-04`/`05` decidirem —
  documentar isso explicitamente no código para não confundir sessões futuras.
