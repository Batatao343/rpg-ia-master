# SPEC-370 — Fauna viva nas 11 regiões restantes: backfill autorado por lotes, eval por região e ajustes de escala do motor (filha 360-B)

> **Status:** `in-review` (código e conteúdo prontos; falta a revisão Sol, o playtest e o smoke) — aprovada pelo dono em 03/11 via pedido de execução imediata ("transforme em spec e execute agora"); os defaults da §8 valem até ele dizer o contrário.
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Depende de:** SPEC-360 (`done`: schema, lint E1–E16, `services/fauna.py`, `scripts/fauna/*`, flags `RPG_FAUNA`/`RPG_FAUNA_SINAIS`, Nova Arcádia com 38 entradas aprovadas). SPEC-349 (`done`: fichas das 12 regiões em `data/bestiario/fichas/*.yaml` e o legado em `curadoria_legado.yaml`, na `main`).
> **Desbloqueia:** SPEC-372 (`fauna-tramas`, filha 360-D) nas regiões que ganharem catálogo de trama; ligar `RPG_FAUNA`/`RPG_FAUNA_SINAIS` em staging fora de Nova Arcádia; a filha 360-C (saber e telegrafo) passa a ter sinais em todas as regiões.
> **EXECUTOR_MODEL:** `Terra` (Sonnet, `spec-executor`) integra: rascunho, build, sementes de rumor, ajustes do motor, testes e rodada do eval. **Opus** (`claude-opus-5-5`, `spec-author`) escreve o bloco de fauna, um agente por lote. Nunca Fable (dono, 28/10). **REVIEW_MODEL:** revisor de fauna Opus independente (`spec-reviewer`, nunca o autor do lote), um por lote, e `Sol` técnico (motor, caps, determinismo, integridade de eval). **REVIEW_REQUIRED:** `true`.
> **EVAL_AUTHORING_REQUIRED:** `true`. O avaliador da 360 é protegido (`evals/protected-paths.txt:15-16`). A generalização por região e a correção do oráculo do M1 (P2-8) são escritas por um autor de eval que **não** é o executor de produto, em commit próprio, antes de qualquer conteúdo (Etapa 1).

Rótulos: **[F]** fato no HEAD `86cb7bb8` · **[D?]** decisão aberta (§8, com default) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

A SPEC-360 entregou a fauna viva (sinal antes da luta, ecologia determinística, caça, rumor sem nome) só em Nova Arcádia: 27 fichas e 11 legados, 38 entradas em `data/bestiario/fauna/nova_arcadia.yaml` e `data/world/fauna.json` [F]. As outras 11 regiões já têm fichas na `main` (SPEC-349 `done`), mas nenhuma entrada de fauna. Com as flags `on`, o jogador que sai de Nova Arcádia volta ao encontro de hoje: luta no mesmo turno, texto genérico e rastro que nomeia a criatura. Esta spec faz o backfill das 11 regiões com o processo da 360 §3.7 e corrige o que só aparece em escala (12 regiões em vez de 1).

**Problemas, com evidência [F]:**

| # | Problema | Evidência |
|---|---|---|
| P1 | Só Nova Arcádia tem bloco de fauna. As outras 11 regiões têm 254 fichas e o legado da região sem entrada; o motor dá fator neutro a elas e nunca cria presença | `data/bestiario/fauna/` só tem `nova_arcadia.yaml`; contagem `Grep "^  - id: "` nas fichas: 281 no total, 27 em NA; `curadoria_legado.yaml`: 88 `classe: valoria`, 11 deles em NA (SPEC-360 §9) |
| P2 | O avaliador é fixo em Nova Arcádia | `scripts/fauna/eval.py:39` (`REGION = "nova_arcadia"`), `:45` (relatório único) |
| P3 | O M1 "precedido" lê `sinais_mostrados`, que o próprio produto escreve. Um `scene_block` que gravasse o sinal sem emitir texto passaria (P2-8 do Sol) | `scripts/fauna/eval.py:284-286`; `handoffs/SPEC-360-sol-review.md:24-31`, `:58` |
| P4 | O teste do M7 roda só 3 seeds × 12 dias, menor que o relatório (20 × 60) | `handoffs/SPEC-360-sol-review.md:58`; `tests/test_spec360_eval.py:78` |
| P5 | O cap global de 12 presenças guarda as ativas em ordem de inserção: acima de 12, a recém-nascida é descartada depois do log `presenca_nasce` (P2-4). Com 12 regiões frequentadas isso acontece | `services/fauna.py:140-150`; `handoffs/SPEC-360-sol-review.md:54` |
| P6 | O cap por região (4) foi calibrado como "1 por nó de Nova Arcádia". Ophidia tem 1 nó raiz; Pântano, Zhur, Floresta, Aethelgard, Costa Negra e Brekmar têm 2. Com 4 presenças em 1–2 nós, todo nó tem presença sempre e o "evitar" (R19 da 360) some (P2-1) | `data/world/fauna_config.json:15`; `data/world_map.json` (nós sem `parent_id` por `region_id`); `services/fauna.py:466`; `handoffs/SPEC-360-sol-review.md:51` |
| P7 | O migrante entra com peso fixo 0,5, fora do fator neutro relativo do P1-1, então pesa mais quando a fauna cai fora do território (P2-9). Em NA o limiar não dispara; em regiões com fauna rala, pode | `world_utils.py:1157-1166` vs `:1147-1153`; `handoffs/SPEC-360-sol-review.md:109-111` |
| P8 | `presas` entre humanos é supressão, não fome: matar o Soldado libera o Degolador (bom), mas suprimir o Degolador deixa o Soldado "faminto" (×0,45), o que não faz sentido (F-16) | `handoffs/SPEC-360-independent-review.md:82`; `services/fauna.py:305-364` (`_suppressed`, `eco_multiplier`) |
| P9 | A carcaça (R11 da 360) só tem teste unitário em `record_kill`, nenhum pelo `_combat_node` (P2-7) | `handoffs/SPEC-360-sol-review.md:57` |
| P10 | O calendário pesa 7 legados em 4 regiões numa tabela à mão. Quando o legado ganhar fauna, a estação da ficha substitui o calendário (R8 da 360); se o autor não carregar a estação, ela se perde | `data/world/calendar.json:44-49`; SPEC-360 R8 (estação) |

**Objetivo.** Cobrir as 11 regiões com o mesmo contrato da 360 (R1–R7, E1–E16), sem chamada LLM nova, em 4 lotes sequenciais com autor e revisor Opus, e ajustar o motor para 12 regiões: caps, migrante e supressão entre humanos. O eval passa a medir por região, com oráculo próprio no M1.

## 2. Requisitos

### A. Dados (backfill)

- **R1 — Cobertura das 11 regiões.** Existe `data/bestiario/fauna/<regiao>.yaml` para `pantano_melancolia`, `brekmar`, `skallgard`, `pradaria_ruinas`, `montanhas_afiadas`, `aethelgard`, `floresta_sussurros`, `selva_xylos`, `deserto_zhur`, `costa_negra` e `ophidia`. As chaves de cada arquivo são exatamente {ids das fichas da região} ∪ {legado `classe: valoria` com `regions[0] == <regiao>`}, como no R2 da 360. Inclui o `enemy_assassino_cinzeu` na Pradaria (SPEC-360 §9, Etapa 0). O teste `test_cobertura_regiao` (já parametrizado pelas regiões com arquivo) passa nas 12.
- **R2 — Mesmo contrato.** Toda entrada segue §3.2 da 360 e passa no lint E1–E16 (`scripts/fauna/lint.py --regiao <r>` com 0 erro), mais as regras novas E17 (R11) e E18 (R6). `contra_jogo` das fichas é igual ao da ficha (E13).
- **R3 — Autoria e revisão por lote.** Processo da 360 §3.7: rascunho por script, autor Opus, revisor Opus independente com o checklist da 360 §3.8 mais os itens novos de §3.4 desta spec, lint. Ao fim de cada lote, todas as entradas do lote estão `revisao: aprovada` com `revisor_fauna` ≠ `autor`. O parecer fica em `handoffs/SPEC-370-independent-review.md`, uma seção por lote (o lint de nome de handoff só aceita `SPEC-NNN[-papel]-tipo`, `scripts/check_handoff_names.py:18-20`).
- **R4 — Estação do calendário preservada.** Para cada legado listado em `data/world/calendar.json:44-49` que ganhar entrada, `ecologia.estacoes` reproduz o `encounter_mult` do calendário, ou o desvio é justificado no parecer. Teste: `test_calendario_legado_carregado`.
- **R5 — Contra-jogo do legado como conselho tático.** No legado, `contra_jogo` descreve o que o jogador pode fazer com as Cartas e ações que existem hoje (distância, cobertura, interromper, fugir), sem prometer efeito que o baralho do inimigo não tem (antecipa X-02 da 360, `handoffs/SPEC-360-independent-review.md:104`). É item do revisor, não do lint.
- **R6 — Densidade de `imediato` e ligação trófica por região.** E14 (≤ 30 % `imediato`) e E15 (≥ 60 % das não-BOSS com ≥ 1 ligação trófica) valem por região. Regra nova **E18**: nenhuma região com mais de 2 criaturas `imediato` cujo território inclua o nó de chegada mais usado da região (o nó raiz com o mesmo id da região, quando existir), para evitar emboscada sem sinal no hub (ressalva do Degolador, SPEC-360 §9).
- **R7 — Sementes de rumor.** `scripts/build_rumor_seeds.py` regenera `data/world/rumor_seeds.json` ao fim de cada lote: as sementes `avistamento` das criaturas novas ganham `sinal_rumor` (R21 da 360). Overrides preservados; fração de falsos na faixa da SPEC-312 (`tests/test_spec312_seeds.py` verde).
- **R8 — Fonte única intocada.** `data/bestiary.json` e as fichas (`data/bestiario/fichas/*.yaml`) ficam byte-idênticos (`git diff --exit-code` no pouso). `fauna.json` é regenerado e fresco (`test_fauna_json_fresco`).

### B. Motor em escala (atrás das flags existentes)

- **R9 — Cap por região proporcional aos nós.** O teto de presenças ativas por região passa a ser `min(MAX_PRESENCAS_REGIAO, nós raiz da região × PRESENCAS_POR_NO)`, com `PRESENCAS_POR_NO = 1` em `fauna_config.json` `[BALANCEAR]` [D?] (D3). Em Nova Arcádia (4 nós) o valor continua 4, então o eval de NA não muda. Teste: Ophidia nunca passa de 1 presença ativa; NA continua com até 4.
- **R10 — Cap global que não descarta a recém-nascida (P2-4).** O `day_hook` respeita `MAX_PRESENCAS` **antes** de criar presença: se o cap está cheio, primeiro descarta as não-ativas (`dispersa`/`encontrada`/`cacada`, mais antigas primeiro); se ainda cheio, descarta a ativa mais antiga de região que não é a atual nem a mais frequentada, **nunca** uma presença da região atual com `sinais_mostrados` não vazio. Se nada pode sair, não nasce, e o log `presenca_nasce` não é emitido. Testes: `test_cap_global_preserva_recem_nascida`, `test_cap_global_nunca_descarta_presenca_lida`, `test_cap_global_sem_log_fantasma`.
- **R11 — Supressão entre humanos (F-16).** Campo opcional novo `ecologia.suprime: [ids]` [D?] (D4). Semântica: se um supressor da criatura tem `hunt_pressure ≤ 0,3`, a criatura ganha `PRESA_LIBERADA`; o inverso (todas as suprimidas sumirem) **não** aplica `PREDADOR_FAMINTO` ao supressor. `suprime` conta como ligação trófica no E15. Lint **E17**: `suprime` segue E5/E7/E8 (existe, ≠ si, sem ciclo de 2, mesma região ou adjacente) e um id não pode estar em `presas` e `suprime` ao mesmo tempo. As duas relações sociais de NA citadas no F-16 (`enemy_soldado_legiao_ferro` → `enemy_degolador_mao_sombria`, `nova_arcadia.yaml:690`; `mon_sorvedouro_do_codigo` → `enemy_iniciado_chama_azul`, `:391`) migram de `presas` para `suprime`. Se a migração tirar a única ligação trófica de alguma das quatro, o E15 continua satisfeito porque `suprime` conta. Testes: `test_suprime_libera_sem_fome`, `test_suprime_no_e15`, `test_e17_*`.
- **R12 — Migrante no fator neutro (P2-9).** Com `RPG_FAUNA=on`, o peso do migrante passa a ser `MIGRANT_WEIGHT × neutral` (o mesmo fator médio que o P1-1 dá a quem não tem fauna, `world_utils.py:1149`). Com `off`/`shadow`, nada muda. Teste: num local com o limiar de migrante disparado, a fatia do migrante com `on` fica ≤ 1,5× a do `off`.
- **R13 — Carcaça pelo combate (P2-7).** Teste de integração: a morte de uma criatura com fauna no `_combat_node` (`agents/combat.py`, chamador de `record_kills`) devolve `world_sim.fauna.carcacas` com `{loc, day, creature_id}`; com `RPG_FAUNA=off` ou `shadow`, não grava.
- **R14 — Flags.** Nenhuma flag nova. Com `RPG_FAUNA=off` e `RPG_FAUNA_SINAIS=off`, comportamento byte-idêntico (golden de `tests/fixtures/spec360_flags_off_golden.json`, que joga em Skallgard, continua igual).
- **R15 — Custo e latência.** 0 chamada LLM nova por turno (R26 da 360). Com ~370 entradas em `fauna.json`, `eco_multiplier` + `scene_block` + `day_hook` seguem em média < 5 ms por chamada (teto de teste 20 ms). O loader carrega o JSON uma vez por processo.

### C. Eval (autor de eval, não o executor de produto)

- **R16 — Avaliador por região.** `scripts/fauna/eval.py` ganha `--regiao <r>` (default `nova_arcadia`, saída e limiares de NA idênticos) e `--todas`. O relatório por região vai para `docs/spec360/eval-<regiao>.md`; o global, para `docs/spec360/eval-global.md`. Limiares por região: os mesmos de D4 da 360 (M1 ≥ 0,70 e aproximação 1,0; M2 ≤ 0,35×; M3 ≥ 1,5× / ≤ 0,6×; M4 ≥ 0,80; M6 = 0; M7 byte-idêntico). Exceções declaradas no avaliador, não no produto:
  - **M4 N/A** em região com < 2 nós raiz (Ophidia): não há "fora do território" na região;
  - **M3 N/A** em região sem par predador–presa elegível no porte forçado (o relatório lista o motivo).
- **R17 — M5 global e por região.** O M5 que **barra** é o global: combates de fauna por 100 ações, somando as 12 regiões, com as flags `on`, entre −20 % e +5 % do `off` nas mesmas seeds. Por região, o M5 é informativo, com alerta fora de [−30 %, +10 %] [D?] (D5).
- **R18 — Oráculo próprio no M1 (P2-8).** O avaliador conta "precedido" pelo que ele mesmo viu: registra cada texto de sinal devolvido por `scene_block`, `convert_to_signal` e `track_signal`, atribui o texto à criatura comparando-o com os campos de `sinais` da entrada em `data/world/fauna.json` (leitura do arquivo de dados, não do estado da presença) e marca o combate como precedido se um sinal daquela criatura, no mesmo local ou território, saiu numa ação anterior desde o nascimento da presença. `presence.sinais_mostrados` deixa de ser oráculo. O relatório mostra os dois números (oráculo novo e o antigo) para NA.
- **R19 — M7 no tamanho do relatório.** O relatório roda o M7 com as seeds e dias do próprio relatório (20 × 60) e compara o hash das duas execuções. O teste de pytest roda o M7 reduzido (3 × 12) por região, e o tamanho cheio só em NA, marcado `slow` [D?] (D6).
- **R20 — Densidade de sinal (M8, novo).** Fração das ações com sinal novo (cena + conversão + rastro) ≤ **0,40** por região [D?] (D7). Em NA a 360 mediu 0,298 (SPEC-360 §9). Guarda o "evitar" (P2-1 do Sol), que nenhuma métrica media.
- **R21 — Congelamento e proteção.** O avaliador alterado e `tests/test_spec370_eval.py` são commitados **antes** do primeiro commit de conteúdo ou motor desta spec, com handoff `handoffs/SPEC-370-eval-authoring.md`. `tests/test_spec370_eval.py` entra em `evals/protected-paths.txt` no mesmo commit. Depois disso, o executor de produto não toca nesses arquivos; ajuste de produto só por conteúdo (autor, com revisão) ou constante `[BALANCEAR]` de `fauna_config.json`, registrado na §9.
- **R22 — NA não regride.** `tests/test_spec360_eval.py` continua verde do começo ao fim, e o relatório de NA (com o oráculo antigo) fica dentro dos limiares. Se o oráculo novo (R18) der M1 < 0,70 em NA, a execução **para** e vai ao coordenador: não se mexe no limiar nem no oráculo para passar (§7).

### D. Playtest

- **R23 — Playtest deixa de ser vácuo.** O `explorador` (seed 0) joga em Skallgard (golden, `location: sk_fortaleza_vorr`, P1-2 do Sol). Com as flags `on` e Skallgard coberta, `playtest run --profile explorador --turns 50` termina com 0 violação `error` **e** com ≥ 1 evento `fauna.sinal` na telemetria.

### Fora de escopo

- Tramas (`tramas` com efeito, estágio de trama): SPEC-372.
- Exibir sinais vistos, telegrafo e contra-jogo; revelação do contra-jogo do legado (X-02); "carcaça arrastada" de R11 e encontro de rumor com `criatura_avistada` usando presença (desvios 5 e 7 da 360 §9): filha 360-C.
- Bloco de fauna para criatura gerada em runtime (SPEC-361): segue com o fator neutro relativo.
- Mudar taxa de gatilho, cooldown, tabela de tipos, porte, orçamento de encontro, `bestiary.json`, fichas, Cartas, arte.
- Ligar flag em staging ou produção (coordenador, depois do smoke).
- X-03 (codex público de NA cita a Velha Magda): follow-up de lore, fora da fauna.
- Fichas novas da SPEC-359 (onda 2 do Pântano, `approved`): se pousarem depois, a cobertura (R1) falha e o Pântano recebe as entradas novas num lote extra.

## 3. Design técnico

### 3.1 Arquivos

**Novos**

| Arquivo | Responsabilidade |
|---|---|
| `data/bestiario/fauna/<regiao>.yaml` × 11 | Bloco de fauna autorado (R1) |
| `docs/spec360/eval-<regiao>.md` × 11, `docs/spec360/eval-global.md` | Relatórios (R16, R17) |
| `handoffs/SPEC-370-eval-authoring.md` | Registro do autor de eval (R21) |
| `handoffs/SPEC-370-independent-review.md` | Parecer de fauna, uma seção por lote (R3) |
| `handoffs/SPEC-370-sol-review.md` | Revisão técnica |
| `tests/test_spec370_eval.py` | Asserts por região + M5 global + M8 (protegido, R21) |
| `tests/test_spec370_{cobertura,caps,suprime,migrante,carcaca,latencia}.py` | §4 |

**Alterados**

| Arquivo | O que muda | Quem |
|---|---|---|
| `scripts/fauna/eval.py` | `--regiao`, `--todas`, oráculo do M1, M7 cheio, M8, N/A de M3/M4 | **autor de eval** (Etapa 1) |
| `evals/protected-paths.txt` | `+ tests/test_spec370_eval.py` | autor de eval |
| `services/fauna.py` | cap por região (R9), cap global (R10), `suprime` (R11) | executor |
| `services/fauna_lint.py` | E17, E18; `suprime` no E1 e no E15 | executor |
| `scripts/fauna/build.py` | `suprime` no `fauna.json`; `suprimidos_por` derivado (como `predadores`) | executor |
| `scripts/fauna/rascunho.py` | Só se faltar algo para regiões ≠ NA (ex.: legado com `regions[0]`); hoje aceita `--regiao` (`rascunho.py:82`) | executor |
| `world_utils.py` | Migrante × `neutral` com `RPG_FAUNA=on` (R12) | executor |
| `data/world/fauna_config.json` | `PRESENCAS_POR_NO` (R9) | executor |
| `data/bestiario/fauna/nova_arcadia.yaml` | Só a migração `presas` → `suprime` das 2 relações do F-16 (R11) e o R2-02 opcional (Víbora: tirar a faca do `resto`) [D?] (D8) | autor do lote 1 + revisor |
| `data/world/fauna.json`, `data/world/rumor_seeds.json` | Regenerados | executor |

### 3.2 Lotes (sequenciais)

Ordem pela fila de ondas de trama da SPEC-350 (`data/world/plot_threads.json:12-58`), para que a 372 encontre fauna pronta nas próximas regiões com trama. Contagem de fichas [F]; legado por região na Etapa 0 (77 no total fora de NA).

| Lote | Regiões (nós raiz) | Fichas |
|---|---|---|
| 1 | `pantano_melancolia` (2), `brekmar` (2), `skallgard` (3) | 22 + 20 + 23 = 65 |
| 2 | `pradaria_ruinas` (4), `montanhas_afiadas` (3), `aethelgard` (2) | 22 + 27 + 25 = 74 |
| 3 | `floresta_sussurros` (2), `selva_xylos` (3), `deserto_zhur` (2) | 25 + 22 + 26 = 73 |
| 4 | `costa_negra` (2), `ophidia` (1) | 22 + 20 = 42 |

Por lote: **1 autor Opus** escreve as regiões uma de cada vez (lint da região com 0 erro antes da próxima, para não carregar 3 fichas no contexto) → **1 revisor Opus** (outro agente) → correções pelo mesmo autor até `aprovada` → executor regenera `fauna.json` e `rumor_seeds.json` e roda o eval das regiões do lote. Só um lote em voo por vez; nunca autor e revisor ao mesmo tempo (regra de RAM do dono, 03/11). O executor Sonnet roda testes com `-n 2` no máximo.

Presas e `foge_de` podem apontar para região adjacente (E8). Se o alvo ainda não tem fauna (lote futuro), vale do mesmo jeito: o E5 só exige o id no `bestiary.json`, e a relação inversa é derivada no build.

### 3.3 Formato

Igual à 360 §3.2, mais o campo opcional:

```yaml
    ecologia:
      presas: []
      suprime: [enemy_degolador_mao_sombria]   # opcional; ids; supressão sem fome (R11)
```

`fauna.json` ganha `suprime` e o derivado `suprimidos_por` (ordenados). Entradas sem `suprime` não mudam de bytes no JSON além da ordenação já existente [R]: o build só emite a chave quando não está vazia, para o diff de NA ficar mínimo.

### 3.4 Itens novos no checklist do revisor (além da 360 §3.8)

8. Legado: `contra_jogo` é conselho tático executável hoje (R5).
9. Legado com entrada no calendário: estação carregada ou desvio justificado (R4).
10. `suprime` só entre quem se combate por posição social ou ordem (patrulha, culto, gangue), nunca entre bicho e presa (R11).
11. `imediato` no nó raiz da região: no máximo 2 e justificados (R6, E18).
12. Sem reskin de sinal **entre regiões vizinhas** para criaturas de família parecida (o E12 só compara dentro da região; aqui é leitura humana, por amostra).

### 3.5 Assinaturas novas ou alteradas

```python
# services/fauna.py
def region_cap(region_id: str) -> int: ...  # R9: min(MAX_PRESENCAS_REGIAO, nós_raiz * PRESENCAS_POR_NO)
def _make_room(fauna: FaunaSim, region: str, here_region: str, frequented: list[str], day: int) -> bool: ...  # R10
# eco_multiplier: `suprime` entra em _suppressed() só para PRESA_LIBERADA (R11)

# scripts/fauna/eval.py (autor de eval)
def run(seeds: int = DEFAULT_SEEDS, days: int = DEFAULT_DAYS, region: str = "nova_arcadia") -> dict: ...
def run_all(seeds: int = DEFAULT_SEEDS, days: int = DEFAULT_DAYS) -> dict: ...  # M5 global
```

## 4. Plano passo a passo

### Etapa 0 — Sondas (executor; sem código)

1. Listar o legado `classe: valoria` por `regions[0]` (curadoria × `bestiary.json`), por região, e os BOSS de cada região. Registrar a tabela na §9.
2. Rodar `scripts/fauna/rascunho.py --regiao <r>` nas 11 regiões em memória (sem gravar) para confirmar que funciona fora de NA; anotar o que faltar.
3. Baseline: `tests/test_spec360_*.py` e `tests/test_spec312_seeds.py` com `-n 2`; eval de NA (`scripts/fauna/eval.py`) e o hash do relatório.
4. Escolher a criatura `cedo` não-BOSS de Skallgard para o smoke (§6) depois do lote 1.

### Etapa 1 — Avaliador por região (autor de eval; commit próprio, antes do produto)

Agente separado (Sol/Opus), que **não** executa o produto.

1. `scripts/fauna/eval.py`: R16–R20. O caminho `--regiao nova_arcadia` com o oráculo antigo reproduz o relatório atual byte a byte (teste).
2. `tests/test_spec370_eval.py`: parametrizado pelas regiões com `fauna/<regiao>.yaml`; asserts literais de M1–M8 com os N/A de R16; M5 global; M7 de NA em tamanho cheio (`slow`). As regiões sem arquivo são puladas (`skip` com motivo), então o teste nasce verde só com NA.
3. `evals/protected-paths.txt` + handoff `handoffs/SPEC-370-eval-authoring.md`. Commit `test(fauna): per-region evaluator and M1 oracle for SPEC-370`.
4. Rodar o M1 de NA com o oráculo novo. Se < 0,70, parar (R22).

### Etapa 2 — Motor em escala (TDD; executor)

1. **Testes:** `tests/test_spec370_caps.py` (`test_region_cap_ophidia_1`, `test_region_cap_na_4`, `test_cap_global_preserva_recem_nascida`, `test_cap_global_nunca_descarta_presenca_lida`, `test_cap_global_sem_log_fantasma`); `tests/test_spec370_suprime.py` (`test_suprime_libera_sem_fome`, `test_suprime_no_e15`, `test_e17_ciclo`, `test_e17_presa_e_suprime_juntos`, `test_e18_imediato_no_hub`); `tests/test_spec370_migrante.py` (R12); `tests/test_spec370_carcaca.py` (R13, pelo `_combat_node`); `tests/test_spec370_latencia.py` (R15, com `fauna.json` sintético de 400 entradas).
2. **Implementação:** `fauna.py`, `fauna_lint.py`, `build.py`, `world_utils.py`, `fauna_config.json`.
3. Migração do F-16 em `nova_arcadia.yaml` (2 entradas) + rebuild + eval de NA dentro dos limiares (R22) + `tests/test_spec360_eval.py` verde.
4. **Verificação:** os testes da etapa + `tests/test_spec360_*.py` com `-n 2`; golden `off` byte-idêntico.

### Etapas 3–6 — Lotes 1 a 4 (um por vez)

Para cada lote:

1. **Rascunho** (executor): `rascunho.py --regiao <r>` para cada região do lote; commit do rascunho (`revisao: pendente`).
2. **Autor Opus** (`spec-author`, `model: opus`): por região, lê a ficha (Grep pelo id + Read do bloco, nunca o arquivo inteiro) e o legado (Grep no `bestiary.json` e no Codex); escreve `sinais`, `presas`, `suprime`, `foge_de`, `reage`, `estacoes`, `horario`, `permanencia` e o `contra_jogo` do legado. Lint da região com 0 erro antes da próxima. Hand-back com contagem por região.
3. **Revisor Opus** (`spec-reviewer`, outro agente): checklist 360 §3.8 + §3.4 daqui; seção do lote em `handoffs/SPEC-370-independent-review.md`, com veredito por criatura. `CHANGES_REQUIRED` → o autor corrige → rodada 2.
4. **Executor:** `build.py`, `build_rumor_seeds.py`, `validate_content.py` (0 ERRO), `lint.py` (0 erro), `scripts/fauna/eval.py --regiao <r>` por região do lote, `tests/test_spec370_eval.py` e `tests/test_spec360_build.py` com `-n 2`. Se M1, M4 ou M8 falhar: ajustar **conteúdo** (permanência, território, `antecedencia`), com o autor e nova leitura do revisor, ou uma constante `[BALANCEAR]` global com o eval de NA rodado de novo; registrar na §9. Nunca o avaliador.
5. Commit do lote (`feat(fauna): backfill lot N (<regiões>)`).

### Etapa 7 — Global e playtest

1. `scripts/fauna/eval.py --todas` → `docs/spec360/eval-global.md`; M5 global dentro da faixa.
2. `playtest run --profile explorador --turns 50` com as flags `on` (R23).
3. `scripts/check_handoff_names.py` exit 0.

### Etapa 8 — Revisão Sol

Motor (R9–R13), determinismo, flags `off`, integridade de eval (o diff dos arquivos protegidos depois do commit da Etapa 1 é vazio). Handoff `handoffs/SPEC-370-sol-review.md`.

### Etapa 9 — Smoke real (§6) e pouso

Smoke pelo coordenador; `/spec-land` (suíte completa 1×, pelo coordenador).

## 5. Critérios de aceite

- [ ] 11 arquivos `data/bestiario/fauna/<regiao>.yaml`; `test_cobertura_regiao` verde nas 12 regiões (R1)
- [ ] `lint.py` sem `--regiao` com 0 erro; `validate_content.py` com 0 ERRO; E17 e E18 com fixtures boas e ruins (R2, R6, R11)
- [ ] Toda entrada das 11 regiões com `revisao: aprovada` e `revisor_fauna` ≠ `autor`; parecer por lote no handoff (R3)
- [ ] Estação do calendário carregada nos legados de `calendar.json:44-49` (R4)
- [ ] `rumor_seeds.json` regenerado, overrides preservados, `test_spec312_seeds.py` verde (R7)
- [ ] `bestiary.json` e fichas byte-idênticos; `fauna.json` fresco (R8)
- [ ] Cap por região e cap global com teste; Ophidia ≤ 1 presença; NA inalterada (R9, R10)
- [ ] `suprime` com teste; 2 relações de NA migradas; eval de NA verde depois da migração (R11, R22)
- [ ] Migrante × neutro com teste (R12); carcaça pelo `_combat_node` com teste (R13)
- [ ] Golden `off` byte-idêntico; 0 chamada LLM nova; latência no teto com ~370 entradas (R14, R15)
- [ ] Avaliador por região commitado antes do produto, com handoff de eval e `tests/test_spec370_eval.py` protegido; diff dos protegidos vazio depois disso (R16–R21)
- [ ] Eval por região verde (M1, M2, M3, M4, M6, M7, M8, com os N/A declarados) nas 11 regiões; M5 global em [−20 %, +5 %]; relatórios publicados (R16–R20)
- [ ] `tests/test_spec360_eval.py` verde do começo ao fim (R22)
- [ ] Playtest `explorador` 50 turnos `on`: 0 violação `error` e ≥ 1 `fauna.sinal` (R23)
- [ ] Revisão Sol `APPROVED` ou `APPROVED_WITH_FOLLOWUPS`
- [ ] `uv run pytest` verde (suíte completa, no pouso, pelo coordenador)
- [ ] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo)
- [ ] Saves antigos continuam carregando (presença de criatura de região nova em save antigo: não existe; `normalize_fauna_sim` inalterado)
- [ ] Smoke real da §6 executado e registrado na §9

## 6. Smoke test com LLM real

Coordenador, API local, rotas `ROUTES` de hoje (DeepSeek primário), `RPG_WORLD_ENGINE=on`, `RPG_FAUNA=on`, `RPG_FAUNA_SINAIS=on`. ≤ 6 turnos (cerca de 3 chamadas por turno, ~18 chamadas).

1. Save scratch (não versionado) em Skallgard, no nó do território da criatura escolhida na Etapa 0, com presença ativa dela e 0 sinal mostrado; período dentro do `horario`.
2. Chegar ao nó: o prompt do narrador (log de debug) tem `<SINAIS_NA_CENA>` com um dos `{marca, rastro, resto}`. A narração traz o vestígio e **não** contém o nome, o id nem a família da criatura (fold sem acento).
3. "fico observando": no máximo 1 sinal novo; sem combate.
4. "sigo o rastro": combate com surpresa do jogador; `COMBAT START` com a `aproximacao`; spawn resolve no id da presença.
5. `GET /game/state`: `bestiary_knowledge.<id>.sinais_vistos` igual aos tipos mostrados.
6. Viajar para um nó de Ophidia (save com acesso; se a rota for longa, trocar a região do save): confirmar no estado que há no máximo 1 presença ativa na região.
7. Custo: chamadas por turno com flags `on` iguais às do mesmo roteiro com `off` (telemetria `set_llm_telemetry_hook`), exceto o turno da caça, que custa um início de combate comum.

## 7. Riscos & compatibilidade

- **Volume de autoria.** ~331 entradas (254 fichas + 77 legados). O lote de ~3 regiões e ~100 entradas é grande para um agente: o autor trabalha região a região, com lint entre elas, e devolve hand-back por lote. Se o contexto apertar, o coordenador divide o lote em dois agentes **sequenciais**.
- **Eval falha numa região pequena.** Com 2 nós, o M4 fica fácil e o M8 fica difícil (presença em todo nó). As alavancas são o cap por nó (R9) e a permanência (conteúdo). Constante global mexe em NA: qualquer ajuste roda o eval de NA de novo e é registrado.
- **Oráculo novo do M1 rebaixa NA.** Se o M1 de NA com o oráculo próprio cair abaixo de 0,70, a decisão é do coordenador ou do dono (aceitar, como no P2-11, ou recalibrar). O executor não mexe.
- **Integridade de eval.** O avaliador muda nesta spec, mas por um autor de eval, antes do produto, com handoff. Depois disso, `git diff` dos protegidos tem que ser vazio no pouso (o Sol confere).
- **Conflito com a SPEC-372.** As duas mexem em `services/fauna.py`, `services/fauna_lint.py`, `nova_arcadia.yaml` (aqui só 2 entradas do F-16 e a Víbora) e regeneram `fauna.json`. Quem pousa depois faz rebase e roda `build.py` de novo; `fauna.json` nunca se resolve à mão.
- **SPEC-359 (onda 2 do Pântano).** Se trocar fichas do Pântano depois do lote 1, a cobertura falha no CI e o Pântano ganha um lote extra.
- **Saves antigos.** Nada muda de forma: presenças e carcaças só ganham criaturas novas. `suprime` é opcional.
- **MockLLM / FallbackLLM.** Nenhum caminho novo de LLM. Vazamento de nome na prosa só aparece no smoke.
- **Quota e latência.** 0 chamada nova; o prompt cresce ≤ 60 tokens nas cenas com sinal. Autoria é offline.
- **RAM.** Um agente Opus por vez; testes do executor com `-n 2`; suíte completa só no pouso.

## 8. Decisões abertas (default; o coordenador decide)

- **D1 — Ordem dos lotes.** Default: a fila de ondas de trama da 350 (§3.2). Alternativa: por número de nós (as pequenas primeiro, para calibrar R9 cedo).
- **D2 — Tamanho do lote.** Default: 3 regiões (4 lotes; o último com 2), como pediu o dono. Alternativa: 1 região por lote, mais handoffs e mais rodadas de revisão.
- **D3 — Cap por região.** Default: `min(4, nós raiz × 1)`. Alternativa: manter 4 fixo e aceitar saturação nas regiões de 1–2 nós (o M8 deve barrar).
- **D4 — F-16.** Default: campo `suprime` (R11) e migração das 2 relações de NA. Alternativa: regra derivada "entre humanoides só vale `PRESA_LIBERADA`", sem campo novo (exige classificar humanoide no legado, que não tem família).
- **D5 — M5 por região.** Default: informativo, com alerta fora de [−30 %, +10 %]; só o global barra. Alternativa: barrar por região com a faixa da 360.
- **D6 — M7 cheio no pytest.** Default: só NA em tamanho cheio, marcado `slow`; as outras reduzidas. Alternativa: todas cheias (a suíte fica bem mais lenta).
- **D7 — M8 (densidade).** Default: ≤ 0,40 das ações com sinal novo por região. Alternativa: ≤ 0,35 (NA mediu 0,298) ou sem M8.
- **D8 — R2-02 (Víbora).** Default: aplicar no lote 1 (tirar a faca do `resto`), já que o arquivo de NA é tocado pelo F-16. Alternativa: deixar como está (era opcional).

## 9. Registro de execução

### Etapa 0 — sondas (03/11, executor)

Contagens do HEAD (fichas = `status` nova/reinventada/adotada; legado = `classe: valoria` com `regions[0]` = região; BOSS = `encounter_budget.is_boss`; nós raiz = sem `parent_id`). Total fora de NA: 254 fichas + **76** legados = 330 entradas (a spec dizia 77; a contagem por `regions[0]` dá 76, o `lint --regiao` é a fonte).

| Região | Fichas | Legado | BOSS (fichas+legado) | Nós raiz | Rascunho sugere `imediato` |
|---|---|---|---|---|---|
| pantano_melancolia | 22 | 8 | 2 | 2 | 1 |
| brekmar | 20 | 6 | 1 | 2 | 2 |
| skallgard | 23 | 8 | 3 | 3 | 2 |
| pradaria_ruinas | 22 | 11 | 1 | 4 | 1 |
| montanhas_afiadas | 27 | 6 | 1 | 3 | 4 |
| aethelgard | 25 | 5 | 1 | 2 | 2 |
| floresta_sussurros | 25 | 4 | 1 | 2 | 2 |
| selva_xylos | 22 | 8 | 2 | 3 | 3 |
| deserto_zhur | 26 | 6 | 3 | 2 | 4 |
| costa_negra | 22 | 7 | 2 | 2 | 3 |
| ophidia | 20 | 7 | 2 | 1 | 3 |

- `rascunho.py --regiao <r>` funciona nas 11 regiões (em memória; 0 território vazio). Mudança: o rascunho agora emite `suprime: []`. As sugestões de `imediato` por emboscador são só ponto de partida: o teto E14 é 30 % da região e o E18 limita 2 no nó-hub (nó raiz com o id da região, que existe nas 12 regiões).
- Nó-hub (E18) existe em todas as regiões (`<regiao>` raiz). Montanhas e Zhur sugerem 4 `imediato` no rascunho: o autor precisa baixar para ≤ 2 no hub.
- Calendário (R4, `calendar.json` `encounter_mult`): `skallgard` (`enemy_lobo_invernal` e `enemy_yeti`, inverno 1,5), `montanhas_afiadas` (`enemy_yeti` inverno 1,5; `enemy_wyvern_jovem` verão 1,5), `deserto_zhur` (`enemy_verme_areia_jovem` verão 1,5; `enemy_escorpiao_cristal` verão 1,3), `selva_xylos` (`enemy_hospedeiro_fungico` primavera 1,3). Cada um que for legado ou ficha da região leva `estacoes` com o mesmo valor.
- Baseline antes do motor: `tests/test_spec360_*.py` + `test_spec312_seeds.py` verdes; eval de NA com o oráculo novo (Etapa 1): M1 0,7508 (legado 0,7542), M8 0,3146.

### Etapa 2 — motor em escala (03/11, executor)

- R9 `region_cap` (`min(4, nós raiz × PRESENCAS_POR_NO)`; `PRESENCAS_POR_NO = 1` em `fauna_config.json`): Ophidia 1, Skallgard 3, NA 4. Região sem nó raiz conhecido volta ao teto fixo.
- R10 `_make_room` (cap global antes de criar, também no caminho `_add_presence` da conversão/rastro): descarta não-ativas, depois a ativa mais antiga de região que não é a atual nem a mais recente em `region_presence`; sem vaga, não nasce nem loga. `_cap_presences` ganhou `protect` para o caminho da conversão.
- R11 `suprime`: lint E17 (E5 de existência/si mesmo, ciclo de 2, região/adjacente, presas∩suprime) e E15 conta `suprime`; `build.py` emite `suprime` só quando há e deriva `suprimidos_por`; `eco_multiplier` usa `suprimidos_por` só para `PRESA_LIBERADA`. F-16 migrado em `nova_arcadia.yaml` (`enemy_soldado_legiao_ferro` → `enemy_degolador_mao_sombria`; `mon_sorvedouro_do_codigo` → `enemy_iniciado_chama_azul`); o diff de `fauna.json` são 4 linhas.
- R12: `neutral` sai de `_weighted_pool`; com `on` o migrante pesa `MIGRANT_WEIGHT × neutral` (teste falha sem a mudança). R13: teste pelo `_combat_node` (`normalize_bestiary_id` é trocado no teste porque o roster do encontro só aceita o goblin da cena).
- Eval de NA depois da migração e do motor: todos os limiares verdes (M1 0,7508, M3 sem os 2 pares migrados, M5 −16,9 %, M7 igual, M8 0,3146); `docs/spec360/eval-nova_arcadia.md` regenerado. `test_spec360_eval.py` e `test_spec370_eval.py` verdes (25 passed, 99 skipped por falta de fauna das outras regiões).
- **Achado `services/ecology.py:59` (`random.Random()` sem semente): NÃO corrigido.** O caminho `on` com `why` vazio (pool sem fauna) e todo o `off` usam o RNG global de propósito; semear só o `on` desloca o sorteio relativo ao `off` e quebra `test_zero_chamada_llm_nova` (72 × 64 chamadas na mesma seed), e semear o `off` quebra o byte-idêntico. Fica como follow-up (precisa decidir se o `off` pode mudar de fonte de acaso); o `on` com fauna no pool já é semeado desde a 360.
- D8 (Víbora, R2-02) não aplicado: é prosa já aprovada; fica para o autor do lote 1.

### Etapas finais de código (03/11, executor)

- **Ophidia (dono, 03/11):** em região de 1 nó raiz toda presença nova deixa 1 sinal antes de virar luta. Implementação: `fauna.anuncia_presenca_nova(region)` (`ANUNCIA_PRESENCA_NOVA` ou região com 1 nó raiz) e `_fauna_encounter` converte a presença ainda sem sinal em sinal (também `imediato`, que nas outras regiões segue sem anúncio). Nas outras regiões nada muda (golden `off` e eval de NA idênticos; `tests/test_spec370_solo.py`). Ophidia M1: 0,6229 → **0,9845** sem tocar no avaliador; M5 da região −37 % (informativo, alerta; o global barra).
- **H-03:** `test_bloco_sem_nome` checa só o texto do sinal; teste novo prova que o nome no texto ainda é pego. **H-02:** o E9 mede `len(render_block(texto))/4 ≤ 60` para `rastro/resto/som/cheiro/marca` (constante `MAX_BLOCK_TOKENS`); 12 regiões com 0 erro.
- **`test_zero_chamada_llm_nova` (70 × 64):** diagnóstico por origem da chamada: 0 chamadas em `services/fauna.py`; as 6 a mais vêm de turnos de história a mais (a fauna converte o encontro em sinal, a trajetória muda: off 19 história/11 combate, on 24/6; o `archivist`/`storyteller` chamam 1× por turno de história). O teste agora exige 0 chamadas da fauna e custo por turno (história e combate) ≤ 1,15× o do `off`; o lockstep `test_campanha_na_lama_exercita_fauna_sem_chamada_extra` segue provando igualdade no mesmo estado.
- **Eval global (12 regiões):** M5 global −19,51 % (faixa −20 % a +5 %: passa com folga de 0,5 pt), combates/100 ações off 15,06 → on 12,12. `docs/spec360/eval-global.md` e `eval-ophidia.md` regenerados.
- Rebase em `main` (371 incluída): `build.py --check` fresco.
- **Playtest e smoke (04/11):** `explorador` 50 turnos, `on`, seeds 0 e 1 (mock): 0 erro, 0 violação, eventos `fauna.sinal` (5 e 7), `fauna.conversao`, 1 `fauna.encontro`. Smoke real §6 (DeepSeek, em processo) em Skallgard e Ophidia: sinal antes da luta, sem nome na narração, caça com aproximação, `sinais_vistos` igual aos mostrados; evidência e limites (presença injetada; passos 6–7 parciais) em `docs/spec370/smoke-real.md`. `eval-nova_arcadia.md` regenerado (M1 0,7366).
- **Smoke real, rodada 2 (04/11):** presença nascida pelo `day_hook` (Brekmar, dia 4), viagem para Ophidia com presença que já chega com 1 sinal e teto de 1, e custo `on` = `off` (29 = 29 chamadas, idênticas por turno, 0 da fauna). Detalhe em `docs/spec370/smoke-real.md`. Lacunas do smoke fechadas.

### Correções da revisão Sol (04/11, executor)

- **P2-1:** `test_zero_chamada_llm_nova` com tolerância de 1,05× por rota (história e combate) e conferência do roteador por turno; a igualdade estrita mora no lockstep.
- **P2-3:** `fauna.solo_region()` (substitui `anuncia_presenca_nova`): região de 1 nó raiz converte **qualquer** presença sem sinal, mesmo com `ANUNCIA_PRESENCA_NOVA` ligada; a constante global segue valendo só para `cedo` nas demais (teste novo). Custo aceito da decisão do dono: Ophidia perde ~1/3 das lutas (M5 da região −37 %, só alerta).
- **P2-4/P2-5:** `_cap_presences(protect=)` removido. `_add_presence` (conversão e rastro) respeita `region_cap` (sai a ativa mais antiga ainda não lida da região) e o cap global (sai a ativa mais antiga não lida; nunca uma lida). Sem vaga, não cria presença e não devolve sinal órfão (turno calmo). Testes em `test_spec370_caps.py`.
- **P2-6:** com pesos legados em uso (fauna zerou), o migrante não multiplica por um neutro 0 (teste novo).
- **P2-7:** a spec diz "mais frequentada"; o motor só guarda o último dia por região, então vale "visitada mais recente" (comentário e docstring ajustados).
- **P2-2 (risco, sem mexer no limiar):** M5 global −19,41 % depois destes ajustes (antes −19,51 %); folga de ~0,6 pp. Qualquer conteúdo novo que troque luta por sinal (`cedo`/presença, `P_PRESENCA`, `ANUNCIA`) deve recalcular o M5 global no PR; se a folga ficar < 1 pp, o coordenador decide entre devolver luta (Ophidia anunciar só `cedo`) e reabrir a faixa com o autor de eval. Relatórios de todas as regiões regenerados.
