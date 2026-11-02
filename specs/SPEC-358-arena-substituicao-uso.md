# SPEC-358 — Arena de Cartas por substituição (`lote-v2`) e uso do bot como aviso

> **Status:** `done` (revisão Sol APPROVED_WITH_FOLLOWUPS, P2 fechados; v2 opt-in, default v1 — D6)
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Épico:** SPEC-327
> **Depende de:** SPEC-336 (`sim.py`, `promote.py`, `--protocolo lote`), SPEC-339 (`done`: desempate por hash no `full_deck`, motor corrigido), SPEC-341 (`done`: sementes 0–19 de ajuste e 20–99 de confirmação).
> **Desbloqueia:** os follow-ups de balanço da SPEC-336 (`specs/SPEC-336-cartas-09-esteira-continua-autoria-cartas.md:100`); uma futura troca do protocolo default da esteira (D5); SPEC-355 §8 D16 (citada pelo coordenador; neste worktree a SPEC-355 ainda é o template, `specs/SPEC-355-cartas-pendencias-abertas.md:1-69`).
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` (integridade do avaliador e estatística da arena) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` (a spec muda o avaliador e **nada** do produto)

Rótulos: **[F]** fato com evidência · **[H]** hipótese que o reprocessamento confirma ou derruba · **[D]** decisão do dono (§8).

O dono mandou "abre e executa" (28/10). Por isso a spec já nasce `approved`, com as recomendações do §8 adotadas. O dono pode trocar qualquer uma no hand-back.

---

## 1. Contexto & Objetivo

[F] **O delta de vitória mede "Carta vs. nada", não "Carta vs. uma Carta equivalente".**
- `build_arms` monta o braço "sem" com `reserve=copies` vagas livres. O braço "com" é o "sem" com as cópias da Carta somadas (`scripts/cards/sim.py:319-331`, reserva em `:87` e `:113`).
- O protocolo de lote ainda tira as irmãs do lote do catálogo (`sim.py:394-413`).
- Quando o baralho base é fino, **qualquer** Carta jogável ajuda, e o delta infla. Evidência:
  - **Bênção do Aço:** base de nível 4 vence só 33–38 %. Cortar dano ou Vigília "quase não move o número"; ela foi aceita a ~+9,4 pp, com o follow-up registrado: "medir o delta por substituição de uma básica de mesmo custo" (`docs/spec335/RELATORIO-arena-lote3.md:67-76`).
  - **Controle sintético de só dano** (`docs/spec335/confirmar_lote5.py:40-61`, `:84-91`): `dano 4 marcial`, sem efeito nenhum além de dano, deu **+10,0 pp** em 320 lutas (`docs/spec335/RELATORIO-arena-lote5.md:64-69`). Uma Carta "vazia" passaria do limiar de `dominante` (+8 pp). O relatório já mediu "sobra" = delta − controle à mão.
  - **Tronco sem subclasse:** misturado, o braço base fica fraco e infla o delta. `arc1_tro_centelha_ressoante` deu +26,2 pp em 80 lutas e +11,2 em 320; por subclasse, +2,5 a +5,0 (`docs/spec335/RELATORIO-arena-lote6.md:77`).
  - **Deltas que caíram para dentro do ruído com mais sementes** (`RELATORIO-arena-lote4.md:48`, `RELATORIO-arena-lote3.md:51-56`). Houve também ajuste de poder feito "para mover o delta" e depois desfeito (`RELATORIO-arena-lote2.md:52`).

[F] **As bandeiras de uso são artefato do bot, e mesmo assim bloqueiam a promoção.**
- O bot joga primeiro todo golpe barato, por `dano_base` (`sim.py:183-191`), e nunca declara reação/passiva (`sim.py:146`).
- `em_branco` (uso < 5 %) e `dominante` por uso > 60 % (`sim.py:362-365`) entram em `bandeiras`, e o `main` sai com código 1 por elas (`sim.py:457`).
- `promote.py` recusa a Carta por qualquer bandeira fora de `amostra_insuficiente`/`uso_nao_medido` (`scripts/cards/promote.py:76-82`).
- Três relatórios seguidos registram que essas bandeiras são artefato e que não se mexeu no poder por causa delas (`RELATORIO-arena-lote3.md:48`, `RELATORIO-arena-lote5.md:61`, `RELATORIO-arena-lote6.md:61`).

**Objetivo.** Criar o protocolo **`lote-v2`** ao lado do `lote`, com duas mudanças:
1. a bandeira de delta passa a usar o **delta por substituição**: a Carta contra uma **referência sintética de mesmo custo, tier e faixa de orçamento**, no mesmo baralho base;
2. o uso pelo bot vira **aviso**, não bandeira.

O protocolo `lote` (v1) continua byte-a-byte o mesmo. Os relatórios da 335 são reprocessados **só como documento novo**. Nenhuma Carta, número, limiar, baseline ou golden muda.

Princípio: integridade de eval (`docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`). Quem muda o avaliador não otimiza produto na mesma tarefa. É o mesmo princípio do "avaliador congelado" da SPEC-341 (`specs/SPEC-341-balanco-sangromante.md:60-65`), agora no sentido inverso.

## 2. Requisitos

### Integridade (valem para todas as etapas)

- **R1 — Nada de produto muda.**
  - Saem desta spec byte-idênticos: `data/cards/**`, `services/**`, `tests/fixtures/spec330_legacy_golden.json`, `evals/**`, `docs/spec335/**`, `docs/spec339/**`, `docs/spec341/**` e `docs/spec335/arena_posturas.py`.
  - Prova no pouso: `git diff --exit-code main -- data/cards services tests/fixtures/spec330_legacy_golden.json evals docs/spec335 docs/spec339 docs/spec341`.
- **R2 — Limiares e preset v1 congelados.**
  - `LIMIAR_BRANCA`, `LIMIAR_DOMINANTE_USO`, `LIMIAR_DOMINANTE_DELTA_PP`, `AMOSTRA_MINIMA_MAO`, `MIN_LUTAS_DELTA`, `MAX_ROUNDS`, `SEM_BANDEIRA` e `PROTOCOLO_LOTE` mantêm os valores (`sim.py:48-54`, `:391`).
  - `tests/test_card_sim.py:344-348` não é editado.
  - O v2 **reusa** essas constantes. Não há limiar novo.
- **R3 — Equivalência do v1 com prova.** Com `--protocolo lote` ou sem `--protocolo`, `simulate_batch`, `simulate_protocolo_lote` e `main` devolvem **exatamente** o mesmo dict, a mesma saída de texto e o mesmo código de saída de antes. Isso vale também para o `--json` e o `--out`: as chaves não mudam, e o v1 não ganha campo novo. A prova tem duas camadas:
  - **(a) golden fixo,** gerado com o `sim.py` da `main` **antes** de qualquer edição dele (R12);
  - **(b) comparação completa no pouso:** o `sim.py` da `main` (via `git show`) contra o novo, sobre todos os arquivos de Postura (R13).
- **R4 — Reprocessamento é documento novo.** Os resultados v2 vão só para `docs/spec358/`. Nenhum `docs/spec335/RELATORIO-*.md` nem `sim-*.json` é reescrito.
- **R5 — Sementes.** O v2 usa as mesmas sementes 0–19 do protocolo. As 20–99 (held-out da SPEC-341, `specs/SPEC-341-balanco-sangromante.md:67`) rodam **uma vez**, só para as Cartas do R14, e não alteram nada.

### Protocolo `lote-v2`

- **R6 — Seleção de protocolo.**
  - `sim.py --protocolo` aceita `lote` (v1, inalterado) e `lote-v2`.
  - `simulate_batch` ganha o parâmetro de palavra-chave `protocolo: str = "v1"`.
  - `simulate_protocolo_lote` ganha `protocolo: str = "v1"`.
  - Com `"v1"`, o caminho de código produz o mesmo resultado de antes (R3).
  - Constante nova `PROTOCOLO_LOTE_V2 = {**PROTOCOLO_LOTE, "versao": 2, "delta": "substituicao", "uso": "aviso"}`. Categorias, criaturas e sementes são as mesmas.
- **R7 — Referência sintética equivalente.** `referencia(card) -> dict | None` monta, sem tocar no catálogo, uma Carta com:
  - os mesmos `classe`, `subclasse`, `patamar`, `raridade`, `tier`, `level_req`, `frequencia` e `custo_entropia` da Carta;
  - `custo_folego` **explícito** igual a `fx.custo_folego(card)`;
  - `tipo: "ativa"`, `apex: False`, `onda: 0`, `versao: 1`;
  - `id = f"{card['id']}~ref"` (ver R9);
  - **um** efeito, conforme a família do bot (`sim._kind(card_id)`; `sim.py:175-191`):

    | família da Carta | efeito da referência |
    |---|---|
    | ataque (`_kind ∈ ct._ATTACK_EFFECTS`) | `{"kind": "dano", "dano_base": X}` + `categoria_arma` do efeito principal da Carta, se houver |
    | cura (`_kind == "cura"`) | `{"kind": "cura", "valor": X}` |
    | defesa (`_kind ∈ {"protecao", "vigilia", "buff_defesa"}`) | `{"kind": "protecao", "valor": X}` |
    | outro suporte (`_kind ∈ ct._SUPPORT_EFFECTS`) | `{"kind": "protecao", "valor": X}` (limitação registrada, D3) |

  - `X` é o inteiro em `1..40` cujo `fx.power_score(ref)` fica mais perto do **ponto médio** de `fx.budget_band(ref)`; no empate, vale o menor `X`.
  - Devolve `None`, e a Carta fica **sem referência**, quando:
    - o `tipo` da Carta é `reacao`, `passiva`, `virtude` ou `utilitaria`;
    - `budget_band(ref)` é `None`;
    - nenhum `X` cai dentro da faixa;
    - ou a família não é nenhuma das quatro.
- **R8 — Três braços pareados.** Para cada Carta do v2:
  - `base` = o braço "sem" de hoje (`build_arms`, com a Carta fora do catálogo e `reserve=copies`);
  - `com` = `base + [cid]*copies`;
  - `ref` = `base + [ref_id]*copies`, com a referência injetada no catálogo só durante as lutas desse braço e restaurada no `finally`.
  - Os três braços usam a mesma tag de semente (`"par"`), os mesmos encontros e as mesmas sementes.
  - `seen` (uso) é medido só no braço `com`, como hoje.
- **R9 — A referência ocupa a posição da Carta.**
  - O baralho entra ordenado nas pilhas (`sim.py:223`), e o bot desempata golpes por id (`sim.py:183-186`).
  - Por isso `ref_id` precisa ocupar no `sorted(ref)` o **mesmo índice** que `cid` ocupa no `sorted(com)`. O sufixo `~` (0x7E) é maior que qualquer caractere de id.
  - Se algum id do baralho cair entre `cid` e `ref_id`, a referência é descartada (`None`) com o aviso `referencia_fora_de_posicao`.
  - Consequência testável: uma Carta **idêntica** à referência dá braços `com` e `ref` idênticos luta a luta, e `delta_pp == 0.0`.
- **R10 — Relatório v2 por Carta.** Os campos do v1 continuam com o mesmo significado. Os campos novos estão em §3.3:
  - `delta_pp` = `round((vit_com − vit_ref) * 100, 1)` quando há referência; sem referência, é o delta por remoção do v1;
  - `delta_base` ∈ {`"substituicao"`, `"remocao"`};
  - `delta_pp_remocao` = o delta do v1 (com − base), só para informação;
  - `vitoria_ref`; `referencia` (id, efeito, `power_score`, faixa) ou `null`;
  - `protocolo: "lote-v2"`;
  - `avisos: list[str]`.
- **R11 — Uso vira aviso.** No v2, `bandeiras` só pode conter `dominante`, **pelo delta**: `lutas_por_braco >= MIN_LUTAS_DELTA` e `delta_pp > LIMIAR_DOMINANTE_DELTA_PP`. Todo o resto vai para `avisos`:
  - `uso_baixo` (uso < `LIMIAR_BRANCA`, com amostra ≥ `AMOSTRA_MINIMA_MAO`);
  - `uso_alto` (uso > `LIMIAR_DOMINANTE_USO`, idem);
  - `uso_nao_medido`, `amostra_insuficiente` (as mesmas regras de `sim.py:354-360`);
  - `sem_referencia` (R7) e `referencia_fora_de_posicao` (R9).

  O `main` com v2 sai com código 1 se e só se alguma Carta tiver `bandeiras` não vazias. Na saída de texto, cada linha mostra `ref` e `avisos`.

### Provas e reprocessamento

- **R12 — Golden do v1 (antes de tocar no `sim.py`).**
  - Um commit **anterior** a qualquer edição do `sim.py` grava `tests/fixtures/spec358_sim_v1_golden.json`, com `_meta.gerado_de` = SHA da `main`.
  - Ele é gerado por `docs/spec358/gerar_golden_v1.py`, importando o `sim.py` intocado.
  - O golden contém:
    - `simulate_batch` do lote sintético `_synthetic_batch()` de `tests/test_card_sim.py:56-61`, níveis `[1, 3]`, `padrao`, 2 criaturas, sementes `[0, 1]`;
    - `simulate_protocolo_lote` de 2 Cartas sintéticas (uma de ataque, uma de defesa);
    - o stdout e o código de saída de `main(["--lote", <tmp>, "--protocolo", "lote"])` para o mesmo lote.
  - **Pool congelado:** o gerador e o teste fazem `monkeypatch` de `cards.cards_for_class` para devolver uma lista fixa de Cartas sintéticas gravada no próprio golden. Assim o golden não quebra quando a esteira 336 promove Cartas novas; ele depende só das básicas (legadas, já protegidas pelo golden da 330) e do motor.
  - A revisão confere no `git log` que o commit do golden precede o primeiro commit que edita o `sim.py`.
- **R13 — Equivalência completa (uma vez, no pouso).**
  - `docs/spec358/equivalencia_v1.py` extrai `git show main:scripts/cards/sim.py` para o scratch e importa os dois módulos.
  - Roda `simulate_protocolo_lote(batch)` (v1) nos dois, para cada um dos 15 arquivos `data/cards/posturas/<postura>_<subclasse>.json`, com as sementes 0–19.
  - Afirma igualdade **exata** dos dicts.
  - Grava `docs/spec358/equivalencia-v1.json` (`{arquivo: {"cartas": n, "iguais": true}}`) e a linha de resumo no relatório.
  - Qualquer diferença bloqueia o pouso.
- **R14 — Reprocessamento v1 × v2** (`docs/spec358/arena_v2.py`, sementes 0–19):
  - **Cartas de onda** (`onda >= 1`) dos 15 arquivos de subclasse: `simulate_protocolo_lote(batch, protocolo="v2")` por arquivo.
  - **Tronco** (`*_tronco.json`): uma variante por subclasse, como em `docs/spec335/confirmar_tronco_lote6.py`.
  - **Neutras** (`data/cards/valoria_neutras.json`): variantes com os `BARALHOS` e a `variante()` **importados** de `docs/spec335/arena_neutras_lote6.py:30-41`, sem modificá-lo.
  - Saídas: `docs/spec358/arena-v2.json` e `docs/spec358/RELATORIO-arena-v2.md`. O relatório traz:
    1. uma tabela por arquivo: Carta | uso | delta v1 (remoção) | delta v2 (substituição) | `vitoria_base` | `vitoria_ref` | bandeiras v1 → v2 | avisos v2;
    2. a contagem de bandeiras v1 × v2 (total e por motivo: uso × delta);
    3. a lista de **divergências** de veredito;
    4. os casos de controle: `dev1_con_bencao_do_aco`, `san1_sil_corte_sem_aviso`, `cor1_alm_culpa_antiga`, `med1_bot_agulha_envenenada`, `med1_fer_cotovelo_de_aco`, `med1_fer_pinca_de_aco`, `arc1_tro_centelha_ressoante`;
    5. a seção "Limitações" (D3, reações sem referência).
  - Cartas com `dominante` no v2, ou com veredito v1 ≠ v2, são conferidas **uma vez** com as sementes 20–99, nos dois protocolos. O resultado vai para `docs/spec358/arena-v2-confirmacao-sementes20-99.json` e para uma tabela do relatório.
  - Nenhuma Carta é alterada. As candidatas a revisão viram uma lista para uma spec de balanço futura.
- **R15 — Validação do próprio v2 com o controle da 335** (prova de que o v2 mede o que promete). O controle sintético `ctl_ferro_dano4_marcial` (`docs/spec335/confirmar_lote5.py:40-61`, `:88`), rodado no v2 com as sementes 20–99, é relatado com `delta_pp_remocao` e `delta_pp`. [H] Espera-se `|delta_pp|` < `|delta_pp_remocao|`. **Não é critério de aceite**: se não se confirmar, o relatório diz isso, e o dono decide (D6).
- **R16 — Documentação.** `docs/guias/CARTAS.md:23-33` ganha um parágrafo "Protocolo `lote-v2`": o que muda, que os limiares são os mesmos, avisos × bandeiras e que o default da esteira segue `lote` até a D5. O `docstring` do `sim.py:1-14` também ganha o v2.
- **R17 — Esteira aceita relatório v2 sem mudar o default.**
  - `promote.py --sim-report <v2.json>` funciona: só `bandeiras` recusa, e `avisos` não recusam.
  - `promote.py` sem `--sim-report` continua chamando o v1 (`promote.py:188`).
  - A flag `--protocolo {lote,lote-v2}` é aceita, com default `lote`.

### Fora de escopo

- Mudar qualquer Carta, número, `versao`, orçamento (`data/cards/_orcamento.json`), limiar, `PROTOCOLO_LOTE`, golden da 330, baseline da 339/341 ou relatório antigo.
- Trocar o protocolo default da esteira (`promote.py` sem `--sim-report`, `docs/guias/CARTAS.md`, `rodar-protocolo-lote*.sh`) para o v2 (D5; spec própria depois do relatório).
- Montar o braço base **com as irmãs do lote**, a outra opção do follow-up de `RELATORIO-arena-lote3.md:76` (D2).
- Bandeira nova de Carta **fraca** (delta muito negativo no v2). Ela aparece só como dado no relatório.
- Mudar o bot (`full_deck_decl`), a ordem do `full_deck`, o motor ou a mistura de subclasses no tronco (`RELATORIO-arena-lote6.md:77`; o reprocessamento só usa variantes por subclasse, como a 335 já fazia).
- `docs/spec335/arena_posturas.py` (taxa de vitória por Postura: não usa remoção nem uso, `arena_posturas.py:38-58`) fica byte-idêntico (D4).
- Referência para reação/passiva (o bot não as declara, `sim.py:146`). Essas Cartas ficam com `sem_referencia` e delta por remoção.
- Rodar long-runs, `pytest -m llm_playtest` ou qualquer LLM.

## 3. Design técnico

### 3.1 Arquivos novos

- `tests/fixtures/spec358_sim_v1_golden.json`: golden do v1 (R12), com `_meta` (`gerado_de`, `comando`, `pool_congelado`).
- `tests/test_card_sim_v2.py`: testes do v2 e da equivalência (§4).
- `docs/spec358/gerar_golden_v1.py`: gera o golden (R12). Roda **antes** de editar o `sim.py`.
- `docs/spec358/equivalencia_v1.py`: `main` × worktree, completo (R13).
- `docs/spec358/arena_v2.py`: reprocessamento (R14/R15). Importa `sim`, `arena_neutras_lote6.BARALHOS/variante` e o `controle` de `confirmar_lote5`.
- `docs/spec358/RELATORIO-arena-v2.md`, `docs/spec358/arena-v2.json`, `docs/spec358/arena-v2-confirmacao-sementes20-99.json`, `docs/spec358/equivalencia-v1.json`.
- `docs/spec358/rodar.sh`: os comandos exatos, versionados (como `docs/spec335/rodar-protocolo-lote*.sh`).

### 3.2 Arquivos alterados

- `scripts/cards/sim.py`:
  - `PROTOCOLO_LOTE_V2`;
  - `referencia()`;
  - `build_arms_v2()`;
  - o parâmetro `protocolo` em `simulate_batch`/`simulate_protocolo_lote`;
  - o ramo v2 de bandeiras e avisos;
  - `--protocolo lote-v2` no `main`;
  - o docstring.

  O ramo v1 **não** é reescrito: o código novo entra em funções novas ou atrás de `if protocolo == "v2"`. Reestruturar o v1 "para reaproveitar" só vale se o golden (R12) e a equivalência (R13) continuarem idênticos.
- `scripts/cards/promote.py`: aceita `--protocolo` (default `lote`) e repassa ao `simulate_protocolo_lote`. `evaluate` não muda: já ignora o que não está em `bandeiras` (`promote.py:76-82`).
- `docs/guias/CARTAS.md`: o parágrafo do R16.

### 3.3 Formato do relatório v2 (ids reais; números ilustrativos)

```json
"dev1_con_bencao_do_aco": {
 "protocolo": "lote-v2",
 "classe": "Devoto do Abismo",
 "vezes_na_mao": 120, "vezes_jogada": 65, "taxa_uso": 0.542,
 "vitoria_sem": 0.375, "vitoria_ref": 0.45, "vitoria_com": 0.488,
 "delta_pp": 3.8, "delta_base": "substituicao", "delta_pp_remocao": 11.2,
 "lutas_por_braco": 80,
 "referencia": {"id": "dev1_con_bencao_do_aco~ref", "efeito": {"kind": "dano", "dano_base": 4},
                "power_score": 5.0, "faixa": [3.5, 6.5]},
 "dano_por_folego": 4.0, "protecao_por_folego": 2.0,
 "bandeiras": [],
 "avisos": []
}
```

Uma reação no v2 fica com `"referencia": null`, `"delta_base": "remocao"` e `"avisos": ["uso_nao_medido", "sem_referencia"]`.

### 3.4 Assinaturas

```python
PROTOCOLO_LOTE_V2: dict  # {**PROTOCOLO_LOTE, "versao": 2, "delta": "substituicao", "uso": "aviso"}


def referencia(card: dict) -> dict | None: ...
def build_arms_v2(
    card: dict, level: int, subclass: str
) -> tuple[list[str], list[str], list[str] | None, dict | None]:
    """(base, com, ref_deck|None, ref_card|None)"""


def simulate_batch(batch, levels, categories, per_cat, seeds, *, protocolo: str = "v1") -> dict: ...
def simulate_protocolo_lote(batch: list[dict], *, protocolo: str = "v1") -> dict: ...
```

`protocolo` fora de {`"v1"`, `"v2"`} levanta `ValueError`.

## 4. Plano passo a passo

Execução no worktree `rpg-spec-358`. Python via `bash scripts/dev/py.sh`. Testes só do escopo, no máximo `-n 2`. Comandos > 2 min em background com timeout (`CLAUDE.md`).

### Etapa 0 — Golden do v1 (antes de qualquer edição do `sim.py`)

1. Escrever `docs/spec358/gerar_golden_v1.py` e gerar `tests/fixtures/spec358_sim_v1_golden.json` (R12) com o `sim.py` intocado.
2. **Teste** (`tests/test_card_sim_v2.py`): `test_v1_reproduz_golden` asserta, com o pool congelado, igualdade exata de:
   - `simulate_batch`;
   - `simulate_protocolo_lote`;
   - o stdout e o código de saída do `main` com `--protocolo lote`.

   Ele passa já nesta etapa, contra o código da `main`.
3. Commit só com o fixture, o gerador e o teste (`test: freeze sim v1 golden for SPEC-358`).

### Etapa 1 — Testes do v2 (vermelhos)

Em `tests/test_card_sim_v2.py`:
- `test_referencia_mesmo_custo_tier_e_dentro_do_orcamento`: para uma Carta sintética de ataque e uma de defesa, a referência tem o mesmo `custo_folego` efetivo, `tier`, `patamar`, `level_req`, `classe`, `subclasse` e `frequencia`, e `fx.budget_error(ref) is None`.
- `test_referencia_familia_segue_o_bot`: ataque → `dano`; cura → `cura`; protecao/vigilia → `protecao`.
- `test_referencia_none_para_reacao_passiva_e_isentas`: `tipo` reacao, passiva ou utilitaria → `None`.
- `test_referencia_ocupa_a_mesma_posicao_no_baralho_ordenado` (R9).
- `test_carta_identica_a_referencia_da_delta_zero`: a Carta = a referência com outro id → `vitoria_com == vitoria_ref` e `delta_pp == 0.0`.
- `test_v2_bracos_diferem_so_na_carta_ou_referencia`: `Counter(com) − Counter(base)` = cópias da Carta; `Counter(ref) − Counter(base)` = cópias da referência; nada mais.
- `test_v2_uso_vira_aviso`: a Carta do `test_sim_flags_blank_card` (`tests/test_card_sim.py:80-88`) tem, no v2, `uso_baixo` ou `amostra_insuficiente` em `avisos`, e `bandeiras == []`.
- `test_v2_dominante_so_por_delta`: Carta sintética de dano 40 (`_synthetic_batch()[0]`), parâmetros de `test_sim_flags_dominant_card` → `"dominante" in bandeiras` e `set(bandeiras) == {"dominante"}`.
- `test_v2_reacao_sem_referencia_usa_remocao`: `delta_base == "remocao"`, com `sem_referencia` e `uso_nao_medido` em `avisos`.
- `test_v2_restaura_catalogo`: nenhum `~ref` nem Carta do lote fica no catálogo depois da execução.
- `test_v2_deterministico`.
- `test_main_v2_codigo_de_saida`: só avisos → 0; `dominante` → 1.
- `test_promote_aceita_relatorio_v2_com_avisos`: relatório v2 com `avisos: ["uso_alto"]` e `bandeiras: []` → a Carta não é recusada pela simulação.
- `test_protocolo_invalido_levanta`.
- `test_v1_reproduz_golden`: segue verde.

### Etapa 2 — Implementação no `sim.py` e no `promote.py`

1. Implementar R6–R11 e R17 conforme §3.2/§3.4, sem tocar no ramo v1.
2. **Verificação:**
   ```
   bash scripts/dev/py.sh -m pytest tests/test_card_sim.py tests/test_card_sim_v2.py -q -n 2
   ```
   Verde. `git diff main -- tests/test_card_sim.py` vazio.

### Etapa 3 — Equivalência completa (R13)

`docs/spec358/equivalencia_v1.py` em background (timeout explícito), com o resultado em `docs/spec358/equivalencia-v1.json`. Qualquer diferença: parar e devolver ao coordenador.

### Etapa 4 — Reprocessamento (R14/R15)

1. `docs/spec358/arena_v2.py` com as sementes 0–19, em background. Depois, uma única rodada 20–99 para as Cartas selecionadas pelo R14 e para o controle do R15.
2. Escrever `RELATORIO-arena-v2.md`. Na leitura, separar [F] de [H] e não propor números de Carta: só a lista de candidatas.

### Etapa 5 — Docs e revisão

1. R16 (`CARTAS.md`, docstring).
2. **Revisão Sol** (obrigatória) em `handoffs/SPEC-358-sol-review.md`, cobrindo:
   - o golden precede a edição do `sim.py` (`git log --follow`);
   - R1/R2 por `git diff`;
   - a equivalência completa;
   - a correção estatística dos três braços pareados;
   - a escolha da referência (midpoint) e a posição no baralho (R9).

   Sem Sol disponível: `MODEL_HANDOFF_REQUIRED` + o handoff preparado, sem autoaprovação.

## 5. Critérios de aceite

- [x] Golden v1 commitado antes da primeira edição do `sim.py`; `test_v1_reproduz_golden` verde.
- [x] `docs/spec358/equivalencia-v1.json`: 15/15 arquivos `iguais: true`.
- [x] `git diff --exit-code main -- data/cards services tests/fixtures/spec330_legacy_golden.json evals docs/spec335 docs/spec339 docs/spec341 tests/test_card_sim.py` vazio.
- [x] Constantes e `PROTOCOLO_LOTE` inalterados (`tests/test_card_sim.py:344-348` verde, sem edição).
- [x] Todos os testes da Etapa 1 verdes; `tests/test_card_sim.py` verde.
- [x] `sim.py --protocolo lote-v2` produz `bandeiras` só com `dominante` por delta, e uso só em `avisos`.
- [x] `promote.py` sem `--sim-report` continua no v1; com relatório v2, aviso não recusa.
- [x] `docs/spec358/RELATORIO-arena-v2.md` com tabelas v1 × v2, divergências, casos de controle, R15 e limitações; nenhum relatório antigo reescrito.
- [x] `docs/guias/CARTAS.md` documenta o v2 (R16).
- [x] Revisão Sol registrada (`handoffs/SPEC-358-sol-review.md`) sem P1 aberto.
- [x] `uv run pytest` verde (suíte completa offline, pelo coordenador no pouso).
- [x] Guard de FallbackLLM: não se aplica (nenhum `with_structured_output` novo).
- [x] Saves antigos: não se aplica (nada de estado de jogo muda).

## 6. Smoke test real

Não há LLM nem infraestrutura: a arena é offline (`RPG_FORCE_MOCK=1`, `sim.py:28`). O smoke "real" é a CLI de ponta a ponta sobre um arquivo real do catálogo:

1. `bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/posturas/devoto_consagrado.json --protocolo lote --out <scratch>/v1.json`, depois comparar com o v1 da `main` sobre o mesmo arquivo (é a linha do R13): idênticos.
2. Mesmo comando com `--protocolo lote-v2 --out <scratch>/v2.json`. Conferir no JSON:
   - `dev1_con_bencao_do_aco` com `referencia` não nula, `delta_base: "substituicao"` e `delta_pp_remocao` igual ao `delta_pp` do v1;
   - as reações com `sem_referencia`.
3. `bash scripts/dev/py.sh scripts/cards/promote.py <lote sintético em scratch> --onda 99 --sim-report <scratch>/v2.json --dry-run`: avisos não recusam, `dominante` recusa.
4. `git status` limpo em `data/`: nada gravado no catálogo.

## 7. Riscos & compatibilidade

- **Escolha da referência (risco principal).**
  - O ponto médio da faixa é uma convenção; uma Carta no topo da faixa terá delta positivo legítimo. É o que se quer: medir poder **acima do esperado para o custo**.
  - Uma referência mal escolhida (família errada) distorce o delta. Mitigações:
    - a tabela de família (R7) segue a decisão do bot;
    - o caso "outro suporte → `protecao`" é declarado como limitação (D3);
    - o v2 mantém `delta_pp_remocao` no relatório para comparação.
- **Custo de execução.** O v2 roda 3 braços em vez de 2 (≈ 1,5× o v1). O reprocessamento completo (~260 Cartas × 240 lutas + variantes) roda em background, um processo só (regra de RAM do `CLAUDE.md`).
- **Brittleness do golden.** Com o pool congelado (R12), o golden depende só das básicas e do motor. Se uma spec futura mudar o motor, o golden pode mudar **naquela** spec, que regenera com o `sim.py` intocado e registra no próprio commit. Esta spec não pode regenerá-lo depois de editar o `sim.py`.
- **Integridade de eval.** Esta spec otimiza o avaliador e não o produto, e nenhuma Carta muda. O risco inverso, usar o v2 para "absolver" Cartas, é bloqueado de duas formas:
  - o default da esteira segue v1 (D5);
  - o relatório só lista candidatas.
- **Compatibilidade.** Os chamadores de `simulate_batch` com posicionais (`docs/spec339/arena_spec339.py:71`, `docs/spec341/arena_spec341.py:125-154`, `docs/spec335/*.py`) seguem iguais (o parâmetro novo é só de palavra-chave, com default `"v1"`).
- **MockLLM/FallbackLLM/quota/latência:** sem efeito (não há LLM).

## 8. Decisões do dono

O dono disse "abre e executa" em 28/10. As recomendações abaixo estão **adotadas** e podem ser revertidas no hand-back.

- **D1 — Referência = Carta sintética no ponto médio da faixa de orçamento (mesmo custo/tier/patamar), não uma básica.** *Adotada.* A básica do mesmo custo (a sugestão de `RELATORIO-arena-lote3.md:76`) é mais fraca que uma comum de onda e manteria parte da inflação. O ponto médio da faixa é, por definição, "equivalente pelo custo". O controle da 335 já era sintético (`confirmar_lote5.py:40-61`).
- **D2 — Montar o braço base com as irmãs do lote:** *não nesta spec.* Isso muda o isolamento do protocolo (`sim.py:387-390`) e o significado de todos os deltas antigos. A substituição ataca a inflação sem mexer no isolamento.
- **D3 — Família da referência para "outro suporte"** (purga, ganhar Fôlego etc.): `protecao`. *Adotada como limitação declarada.* Alternativa: sem referência (`sem_referencia`) para essa família.
- **D4 — `docs/spec335/arena_posturas.py` não muda.** *Adotada.* Ele mede taxa por Postura, sem remoção nem uso (`arena_posturas.py:38-58`), e é o baseline das SPEC-339/341.
- **D5 — Default da esteira continua `lote` (v1).** *Adotada.* Trocar o `promote.py`/`CARTAS.md`/scripts para o v2 é uma decisão **depois** de ler `docs/spec358/RELATORIO-arena-v2.md`, em spec própria, para não mudar o gate e o avaliador na mesma tacada.
- **D6 — Se o R15 não confirmar** (substituição não reduz o delta do controle): o v2 fica disponível, mas não é recomendado como default. O relatório expõe isso, e o dono decide entre aceitar ou rever o desenho da referência numa spec nova. *Adotada.*
- **D7 — `uso_alto` também vira aviso** (não só o uso baixo). *Adotada.* A evidência de artefato cobre os dois (`RELATORIO-arena-lote3.md:48`, `RELATORIO-arena-lote5.md:61`). Uma Carta forte de verdade aparece no delta por substituição.
- **Recomendação do revisor (Sol), para a D5:** antes de qualquer troca do default da esteira para o v2, abrir **spec própria para recalibrar a referência**. O ponto médio da faixa de orçamento é forte demais para o bot (muitos deltas v2 saem negativos, e o controle R15 não confirmou), então um v2 sem bandeira não prova que a Carta é boa.

## 9. Registro de execução (desvios)

- **Golden regenerado (commit `1d41ae11`).** O motor (`services/`) avançou na `main` depois do 1º golden e o `test_v1_reproduz_golden` passou a falhar. O §7 proíbe regenerar o golden depois de editar o `sim.py`; por isso a regeneração usou o `sim.py` **da `main`, intocado** (`gerar_golden_v1.py --sim`), não o editado. O `sim.py` novo reproduz o golden regenerado, e a equivalência `main` × novo nos 15 arquivos (R13) foi refeita no motor atual. O commit seguinte só corrige a proveniência (`gerado_de` = SHA da `main`, `sim_fonte`).
- **Bandeiras v1 derivadas** no reprocessamento (R14) a partir do relatório v2, conferidas contra o v1 real em `sangromante_avaro`; evita rodar o v1 duas vezes.
- **Dados da arena v2 carimbados** com `motor_sha` (merge-base com a `main`) em `arena-v2*.json`; foram regerados no motor do pouso (revisão P2-1).
