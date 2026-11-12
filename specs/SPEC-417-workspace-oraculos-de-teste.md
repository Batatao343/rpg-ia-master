# SPEC-417 — workspace-oraculos-de-teste

> **Status:** `in-progress`
> **Criada:** 2026-11-12 · **Atualizada:** 2026-11-12
> **Depende de:** SPEC-338 `done` (perfil Hypothesis R16), SPEC-379 `done` (`tests/factories.py`), SPEC-407 `done` (desenho de catraca). **Ordem com a SPEC-415** (`approved`, cria `land_check`): independente; ver D2 e §7.
> **Desbloqueia:** check `weak-tests` dentro do `land_check` (uma linha na SPEC-415 ou follow-up, D2).
> **Risco:** `médio`. Não toca código de produto, mas (1) cria um gate que pode recusar pouso (falso positivo trava a onda), (2) põe testes de propriedade na suíte default (tempo e flake da camada 2) e (3) mexe em `pyproject.toml`/`uv.lock`. Revisor Sonnet; não é `alto` porque nada de combate, persistência, API ou eval muda de comportamento.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet) · **EVAL_AUTHORING_REQUIRED:** `false`
> **Evidência:** catraca: `tests/test_weak_tests.py` com diff sintético (repo git em `tmp_path`: `main` limpa, branch com `@pytest.mark.skip` sem `reason` num teste já existente e um `test_` novo sem assert) vermelho antes do script e verde depois, e a mesma branch sintética corrigida saindo rc 0. Propriedades: cada uma tem uma mutação manual (§4.4) que o revisor aplica no worktree e vê a propriedade falhar; desfeita a mutação, verde.

---

## 1. Contexto & Objetivo

O código deste repo é escrito por agentes. Na onda de 11/11 a revisão independente achou todos os bugs graves (`ESTADO_ATUAL.md`, "Notas da onda": 412 com 3 bugs de cancelamento, 411, 413, 410), e os testes do próprio executor não pegaram nenhum. O executor escolhe o exemplo, o valor esperado e quando pular; ele consegue, sem má-fé, escrever um teste que só confirma o que o código já faz. Faltam oráculos que ele não consiga tautologizar.

Esta spec cobre dois desses oráculos (itens A4 e A6 da proposta de qualidade de 12/11, revisados por revisor independente e delegados ao coordenador):

1. **Catraca de teste enfraquecido** no pouso: sobre `git diff main...HEAD` em `tests/`, recusa `skip`/`skipif`/`xfail` novo sem motivo e teste novo sem asserção, e relata (sem bloquear) assert removido. O desenho de catraca é o da SPEC-407 (`scripts/dev/size_budget.py:80-114`: só o que muda conta, saída curta, rc 1), mas a referência é o diff, não um JSON de baseline. Hoje 77 arquivos de `tests/` já usam skip/xfail; com o diff, eles são a baseline implícita e só o novo conta.
2. **Testes de propriedade com Hypothesis**, escopo estreito: cinco invariantes de mecânica determinística, lidas no código, e um round-trip de `persistence.py` sobre `GameState` vindo de `tests/factories.py`. O gerador escolhe os exemplos, não o executor. A regra do projeto já pede isso ("Mecânica é Python, não LLM", e "antes de criar um writer persistente... confirme round-trip save/load", `AGENTS.md`), mas só existem exemplos fixos (ex.: `tests/test_factories.py:103-115`, um único estado).

Hypothesis já está no `uv.lock` (`uv.lock:1040-1041`, 6.170.12), mas só entra de forma transitiva pelo grupo `fuzz` (`pyproject.toml:56-58`, via `schemathesis`), que a suíte default não instala. O perfil determinístico já existe para o fuzz (`tests/fakes/api_fuzz.py:194-211`, SPEC-338 R16: `derandomize=True`, `database=None`, `deadline=None`).

## 2. Requisitos

Linhas citadas = `main` em `29dba5d5`.

### Bloco A — catraca de teste enfraquecido (`scripts/dev/weak_tests.py`)

- **R1 — Comando.** `bash scripts/dev/py.sh scripts/dev/weak_tests.py [--base main] [--head HEAD] [--spec NNN] [--worktree]`. Lê o conjunto `git diff --name-status -M --diff-filter=AMRD <base>...<head> -- tests/` (renomes rastreados: o lado antigo do `R` é a versão anterior do mesmo arquivo). Versão antiga = `git show <merge-base>:<caminho antigo>`; nova = `git show <head>:<caminho>`, ou o arquivo em disco com `--worktree` (uso do executor antes de commitar). `--spec` ausente: deduz `NNN` do nome da branch `spec-NNN`; sem branch nesse formato e sem `--spec`, a justificativa por spec (R3) fica indisponível e isso sai numa linha `INFO`. Só arquivos `tests/**/test_*.py` e `tests/**/conftest.py` entram; o resto de `tests/` (fakes, JSON, fixtures) é ignorado.
- **R2 — Detecção por AST, nunca regex.** `ast.parse` das duas versões. Marca de pulo = qualquer um destes nós, atribuído ao `qualname` da função/classe que o contém (`<module>` no topo):
  - decorador `pytest.mark.skip`, `pytest.mark.skipif`, `pytest.mark.xfail` (atributo puro ou chamada), também via `from pytest import mark` (`mark.skip`);
  - chamada `pytest.skip(...)`, `pytest.xfail(...)`, `pytest.importorskip(...)` no corpo;
  - `pytestmark = ...` de módulo ou de classe contendo essas marcas (lista ou marca única);
  - `marks=` dentro de `pytest.param(...)`, atribuído à função decorada pelo `parametrize`.
  Texto dentro de string (inclusive código de teste sintético, como o de `tests/test_weak_tests.py`) não conta, e é por isso que é AST.
- **R3 — Pulo novo sem motivo bloqueia.** Cada marca vira a chave `(arquivo, qualname, tipo, tem_motivo)`; marcas novas = multiconjunto novo menos antigo. `tem_motivo` = `reason=` com string não vazia (constante ou f-string) ou, onde o pytest aceita, 1º argumento posicional string (`mark.skip("…")`, `pytest.skip("…")`, `pytest.xfail("…")`). Marca nova com `tem_motivo = False` **e** sem justificativa na spec → `FAIL`. Justificativa na spec = uma linha de `specs/SPEC-NNN-*.md` que contenha o nome da função (ou o nome do arquivo, para `<module>`) e uma das palavras `skip`, `skipif`, `xfail`, `importorskip`. Consequências desejadas: pôr `@pytest.mark.skip` num teste que já existia conta como novo; apagar o `reason=` de uma marca antiga também (a chave muda para `tem_motivo = False`). Leitura literal do item A4 ("sem `reason=` e sem linha na spec"); a variante estrita é D1.
- **R4 — `xfail` novo sem `strict=True` vira `INFO`**, não `FAIL` (um `xfail` não estrito passa em silêncio quando o bug some, e esconde quando o teste para de testar).
- **R5 — Teste novo sem asserção bloqueia.** Teste = `def test_*`/`async def test_*` de módulo ou de classe `Test*`, sem `@pytest.fixture`. Novo = `qualname` ausente da versão antiga (arquivo novo: todos). Tem asserção se, em `ast.walk` do corpo, houver ao menos um de:
  - `ast.Assert` cujo teste não é constante verdadeira (`assert True`, `assert 1`, `assert "x"` não contam);
  - `with pytest.raises(...)`, `pytest.warns(...)`, `pytest.deprecated_call(...)`, ou chamada `pytest.raises(...)`/`pytest.fail(...)`;
  - chamada cujo nome (`Name.id` ou `Attribute.attr`, sem `_` iniciais) começa por `assert`, `check_`, `expect_` ou `verify_` (cobre `assert_called_once_with`, `self.assertEqual`, `check_response` de `tests/fakes/api_fuzz.py:62`, `assert_security_headers`);
  - chamada a função de módulo do **mesmo arquivo** que, ela própria, tem asserção pelas regras acima (um nível só);
  - chamada a nome da constante `ASSERT_HELPERS` do script (helpers que levantam `AssertionError` sem prefixo; semente: `fuzz_operation`, de `tests/fakes/api_fuzz.py:214`). Crescer essa lista aparece no diff do script, para o revisor.
  Sem nenhum → `FAIL <arquivo>::<qualname> sem assert/pytest.raises/helper de asserção`.
- **R6 — Remoção de assert não bloqueia: relatório.** Para cada arquivo de teste existente nos dois lados, contagem de asserções (as mesmas regras de R5, somadas no arquivo) antes e depois, e testes removidos (`qualname` que sumiu). Só delta negativo aparece: `INFO weak-tests: assert-delta tests/x.py 42 -> 38 (-4), 1 teste removido`, ordenado do mais negativo, no máximo 10 linhas e uma linha `(+N arquivos)`. Arquivo de teste apagado inteiro entra com `-> 0`.
- **R7 — Saída e rc.** Uma linha por achado, no formato do `land_check` (SPEC-415 R1): `FAIL weak-tests: …`, `INFO weak-tests: …`; sem `FAIL`, termina com `OK weak-tests: <A> arquivos, <T> testes novos, <M> marcas novas`. rc 0 sem `FAIL`, 1 com, 2 para uso errado (ref inexistente, git falhou). Arquivo que não parseia em qualquer lado → `INFO … não parseia, pulado` (o ruff do hook já reprova). Tempo: meta < 3 s sobre um diff típico; valor real 5,2 s reais com o arranque do `py.sh` (36 arquivos, 63 testes novos); acima da meta, ver `docs/spec417/medicoes.md`.
- **R8 — Ponto de integração para a SPEC-415, sem editar `land_check.*`.** O script expõe `check(repo: Path, base: str, head: str, spec_text: str | None, *, worktree: bool = False) -> list[Finding]` (`Finding = NamedTuple(level: Literal["FAIL","INFO","OK"], text: str)`) e `main(argv) -> int`, para o `land_check.py` importar ou chamar via subprocess. Até essa ligação existir, o coordenador roda o comando no `/spec-land` (D2). Esta spec não edita `scripts/dev/land_check.sh`, `land_check.py`, `wt.sh` nem skills.
- **R9 — Calibração em histórico real.** Antes de pousar, o executor roda o script sobre os diffs das specs pousadas em 11/11 (405–413, com `--base <pai do 1º commit> --head <último commit>` de cada) e registra em §9 quantos `FAIL` saíram e quantos são falso positivo. Falso positivo > 0 → ajuste de R5 (helper legítimo não reconhecido) antes do pouso, nunca afrouxar R3. 9 specs, 0 `FAIL`, 0 falso positivo (tabela em `docs/spec417/medicoes.md`).

### Bloco B — testes de propriedade (Hypothesis)

- **R10 — Dependência.** `hypothesis>=6.170,<7` entra em `[dependency-groups].dev` (`pyproject.toml:49-55`). `uv lock` não muda a versão resolvida (segue 6.170.12) e só altera metadados do grupo; `requirements.txt` fica idêntico (é exportado com `--no-dev`, `requirements.txt:2`). O grupo `fuzz` não muda. CI: os jobs que rodam `uv sync` sem `--no-dev` (`.github/workflows/validate.yml:42`, `:61`) já instalam o grupo `dev`.
- **R11 — Perfil determinístico igual ao da SPEC-338.** Novo `tests/fakes/property_settings.py` com `deterministic_settings(*, max_examples: int) -> hypothesis.settings`: `derandomize=True`, `database=None`, `deadline=None`, `suppress_health_check=[function_scoped_fixture, too_slow, filter_too_much]` (os mesmos de `tests/fakes/api_fuzz.py:201-211`). `deadline=None` também aqui: com `-n 4`/`-n 6` na camada 2 e o OneDrive, prazo por exemplo é flake garantido; o teto real é o tempo por arquivo (R14). `fuzz_settings` não muda (unificar é D3). Nenhum perfil global: nada de `settings.register_profile` em `conftest.py` (SPEC-414).
- **R12 — Mecânica: `tests/test_mechanics_properties.py`, cinco propriedades.** Toda aleatoriedade do produto vem de um `random.Random(seed)` com `seed` sorteado pelo Hypothesis (passado como `rng=` onde a função aceita; senão `unittest.mock.patch.object(<módulo>, "random", random.Random(seed))`). Dados do catálogo vêm dos dicionários reais (`gamedata`, `ARTIFACTS_DB`, `MERCHANTS`), por `st.sampled_from`.
  - **P1 — Dados dentro da faixa.** `combat_mechanics.roll_dice_numeric` (`combat_mechanics.py:100-114`): para fórmula `f"{n}d{m}{s}{k}"` com `n ∈ [1,6]`, `m ∈ {2,4,6,8,10,12,20}`, `s ∈ {"", "+", "-"}`, `k ∈ [0,20]`: `max(0, n + K) <= total <= max(0, n*m + K)`, com `K = ±k` (0 sem sinal), e `total >= 0` sempre.
  - **P2 — Dano dentro dos limites.** `services.conflict_damage.resolve_damage_and_wounds` (`services/conflict_damage.py:383`, núcleo `:200-380`), alvo = `make_player()` com `vitalidade ∈ [0, max_vitalidade]` e, opcionalmente, `armor = {protecao ∈ [0,6], integridade_max ∈ [0,10], integridade_atual ∈ [0, integridade_max], reducoes_max ∈ [0,3]}`; `damage_base ∈ [0,60]`, `crit_mult ∈ {1,2}`, `damage_type ∈ DANO_FISICO + DANO_SOBRENATURAL` (`gamedata.py:276-277`), `bypass_armor` booleano, `rng=random.Random(seed)`. Afirma: `dano_final >= 0`; `0 <= vit_depois <= vit_antes`; `vit_depois == max(0, vit_antes - dano_final)` quando não `imune`; `0 <= armor.integridade_atual <= integridade_max`; com `bypass_armor=True`, `integridade_atual` inalterada. Domínio `damage_base >= 0` por decisão: os chamadores entregam dano de `roll_dice_numeric`, que tem piso 0 (`:114`).
  - **P3 — Descanso nunca passa do máximo nem fere.** `world_utils.apply_rest` (`world_utils.py:248-335`, ramo v4 `:276-281`), jogador de `make_player(level ∈ [1,5])` com `vitalidade ∈ [0, max_vitalidade]`, mundo de `make_world()`: sem `rest_block` → `vit_antes <= vit_depois <= max_vitalidade` (do jogador devolvido); com `rest_block` (`:255-262`) → `vit_depois == vit_antes`. Os dois ramos são sorteados se o clima for controlável por `world`; senão, só o ramo aberto e isso fica escrito na docstring.
  - **P4 — Troca conserva ouro e estoque.** `services.economy.execute_trade` (`services/economy.py:781-881`), estado de `make_state()` com `world.current_location_id` sorteado entre os `location_id` de `MERCHANTS`, `gold ∈ [0, 5000]`, `mode ∈ {"buy","sell"}`, item do estoque/inventário. Afirma: (a) `ok` → `player["gold"] == gold_antes + gold_delta` e `>= 0`; compra: `gold_delta == -price(iid, mode="buy", …) * qty` e a quantidade do item no inventário sobe `qty`; venda: desce `qty`; (b) todo valor de `world["merchant_stocks"][*][*]` devolvido é `>= 0`; (c) `execute_trade` não muta o `state` de entrada (`copy.deepcopy` antes == depois), que é o que promete o comentário de `services/economy.py:571-572`.
  - **P5 — Sem arbitragem.** `services.economy.price` (`services/economy.py:293-299`): para o mesmo `state`, `merchant` e `item_id`, `price(…, mode="sell") <= price(…, mode="buy")`: comprar e revender na hora nunca dá lucro. Gerador: item de `ARTIFACTS_DB`, mercador de `MERCHANTS` ou `None`, e, se o estado de keeper/patente for montável com a fábrica em ≤ 30 linhas, faixa de relação do keeper (`services/reputation.py:983-989`) e patente com desconto (`services/faction_membership.py:1088-1100`); se não for, o executor limita o gerador e escreve o limite na docstring e em §9.
  - **Iniciativa: fora.** Não há função que ordene iniciativa no motor (`initiative` só aparece como modificador, `combat_mechanics.py:224`, `:396`, e em `services/initiative_cards.py:14-21`); sem função, sem propriedade.
- **R13 — Round-trip: `tests/test_persistence_properties.py`.** Estado = `make_state(game_id=str(uuid.uuid5(NAMESPACE_URL, f"prop/{n}")), class_name, race, region, level)` com classe/raça/região de listas pequenas do catálogo (o `_sheet` tem cache de 64, `tests/factories.py:34`), depois mutado pelo gerador em: `player.gold`, `player.vitalidade` (0..max), `player.inventory` (ids de `ARTIFACTS_DB`, `qty ∈ [1,99]`), `world.turn_count`, `processed_action_ids` (0 a 100 strings), `archivist_last_run`, `conflict_summary` (`None` ou dict sem `conflict_id`), `messages` (`HumanMessage`/`AIMessage` com texto Unicode sem surrogates, `st.characters(blacklist_categories=("Cs",))`, D4). Save no perfil `legacy` (o `conftest.py` já isola `saves/`); `save_game_state` deve devolver `True`.
  - **RT1 — Preserva.** `s1 = load_game_state(save_path(id))` depois de `save_game_state(s0)`: cada campo mutado é igual em `s1` e `s0`, com as normalizações documentadas e só elas: `processed_action_ids` = os últimos 64 (`persistence.py:674`, `:1024`); no `player`, a chave extra `vitalidade_base_bonus` (`tests/test_factories.py:107-110`); no `world`, `shelter: None` (`:111-115`).
  - **RT2 — Ponto fixo.** `s2 = load(save(s1))` é igual a `s1` como dict inteiro (save/load é idempotente depois da 1ª normalização).
  - **RT3 — Save não muta a entrada.** `copy.deepcopy(s0)` antes do `save_game_state(s0)` é igual a `s0` depois.
- **R14 — Teto de tempo.** `max_examples` de partida: P1 e P2 = 100, P3/P4/P5 = 30, RT1–RT3 = 20 (cada uma). Meta na suíte default, medida com `--durations=0` em `-n 2`: `tests/test_mechanics_properties.py` ≤ 8 s e `tests/test_persistence_properties.py` ≤ 10 s no total do arquivo. Passou da meta → reduzir `max_examples` (nunca o domínio do gerador) e registrar o valor final em §9. mecânica ~0,7 s, persistência ~1,9 s em `-n 2` (meta 8 s / 10 s).
- **R15 — Bug achado não se conserta aqui.** Propriedade que falhar no código atual: o executor decide primeiro se a propriedade está errada (ex.: ignora uma regra de jogo escrita em spec) ou se é bug. Propriedade errada → corrige o teste e escreve o porquê em §9 (o revisor confere). Bug → **não** mexe no produto: marca o teste `@pytest.mark.xfail(strict=True, reason="SPEC-417 achado N: <resumo>; exemplo mínimo: <exemplo do Hypothesis>")` (com `@example(...)` fixando o exemplo mínimo), registra em §9 e devolve no hand-back para virar spec própria. `strict=True` faz o teste falhar quando a spec de correção pousar, obrigando a retirar a marca. Cada `xfail` desses é citado em §9 com o nome do teste e a palavra `xfail`, o que também satisfaz R3.
- **R16 — Sem lixo no repo.** Depois de rodar os dois arquivos, `git status --porcelain` não mostra `.hypothesis/`. Se a versão instalada criar o diretório mesmo com `database=None`, entra `.hypothesis/` no `.gitignore` (uma linha) e isso fica em §9. vazio (`.hypothesis/` existe mas traz `.gitignore` próprio).

### Bloco C — guia

- **R17 — Uma linha em `docs/guias/TESTES.md`**, na seção "Onde mora um teste novo" (`docs/guias/TESTES.md:55-67`): "Propriedade (Hypothesis, `tests/fakes/property_settings.py`) em vez de exemplo quando o código é writer persistente (round-trip save/load) ou mecânica numérica com faixa ou conservação (dano, ouro, estoque, dados); exemplo fixo continua para regra de negócio pontual. Pouso: `scripts/dev/weak_tests.py` recusa skip/xfail novo sem motivo e teste sem assert."

### Fora de escopo

- **Afrouxar tolerância não é detectável** e fica fora: trocar `==` por `>=`, aumentar `rel=`/`abs=` de `pytest.approx`, encolher o conjunto esperado, trocar o valor esperado pelo que o código devolve. Nenhuma regra de AST separa isso de uma correção legítima; quem pega é o revisor, com o relatório de R6 e o diff.
- Outros jeitos de enfraquecer que o script não vê: `deselect`/`-m` em `addopts` (`pyproject.toml:122`), `pytest_collection_modifyitems` que pula itens, assert em função aninhada que nunca é chamada, `assert x is not None` fraco. O diff de `pyproject.toml`/`conftest.py` é do revisor.
- Mutation testing (adiado: suporte a Windows incerto e relatório sem gate não fecha); cobertura de diff; gate de tipos (SPEC-418).
- `specs/TEMPLATE.md`, `.claude/agents/*`, `scripts/dev/land_check.*`, `scripts/dev/wt.sh`, skills, `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` (SPEC-415); `full.sh`, `guard_tools.py`, `tests/conftest.py`/basetemp (SPEC-414); catraca de relógio e baseline do ruff (SPEC-416).
- Qualquer correção de produto achada pelas propriedades (R15).
- Propriedades além das cinco + três (initiative, facções, clima, cartas): spec própria se o modelo funcionar.
- `evals/` protegido (`evals/protected-paths.txt`): nada.

## 3. Design técnico

### 3.1 Arquivos

- **Novos**
  - `scripts/dev/weak_tests.py` — R1–R9. Toda função ≤ 60 linhas; subprocess com lista de argumentos.
  - `tests/test_weak_tests.py` — §4 Etapa 1.
  - `tests/fakes/property_settings.py` — R11 (sem testes dentro; importa `hypothesis` no topo, pois o grupo `dev` passa a tê-lo).
  - `tests/test_mechanics_properties.py` — P1–P5 (docstring `SPEC-417 R12`).
  - `tests/test_persistence_properties.py` — RT1–RT3 (docstring `SPEC-417 R13`).
- **Alterados**
  - `pyproject.toml` — `hypothesis>=6.170,<7` no grupo `dev` (R10).
  - `uv.lock` — regravado por `uv lock` (só metadados do grupo).
  - `docs/guias/TESTES.md` — uma linha (R17).
  - `.gitignore` — só se R16 exigir.
  - `specs/SPEC-417-workspace-oraculos-de-teste.md` — §9 (execução, achados, medições).
- **Não tocados:** nenhum arquivo de produto (`combat_mechanics.py`, `world_utils.py`, `services/*`, `persistence.py`), `tests/fakes/api_fuzz.py`, `tests/conftest.py`, `tests/factories.py`, `scripts/dev/land_check.*`, `evals/`.

### 3.2 Assinaturas (`weak_tests.py`, funções puras testáveis sem git)

```text
Mark = NamedTuple(qualname: str, kind: str, has_reason: bool, strict: bool, lineno: int)
Finding = NamedTuple(level: str, text: str)               # "FAIL" | "INFO" | "OK"
marks(src: str) -> list[Mark]                             # R2
new_marks(old_src: str | None, new_src: str) -> list[Mark]   # R3: multiconjunto (qualname, kind, has_reason)
justified(mark: Mark, path: str, spec_text: str | None) -> bool
test_functions(src: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]   # R5
assertion_count(node: ast.AST, local_helpers: set[str]) -> int
local_assert_helpers(tree: ast.Module) -> set[str]        # funções do módulo com asserção (1 nível)
weak_new_tests(old_src: str | None, new_src: str) -> list[str]   # qualnames sem asserção
assert_delta(old_src: str, new_src: str) -> tuple[int, int, int]  # antes, depois, testes removidos
changed_test_files(repo: Path, base: str, head: str) -> list[tuple[str | None, str | None]]  # (antigo, novo)
check(repo: Path, base: str, head: str, spec_text: str | None, *, worktree: bool = False) -> list[Finding]
main(argv: list[str] | None = None) -> int
```

`changed_test_files` e a leitura de blobs são as únicas funções com git; o resto recebe texto.

### 3.3 Exemplo de saída

```text
FAIL weak-tests: tests/test_economy.py::test_compra_sem_ouro skip sem reason (l. 88) e sem justificativa na SPEC-999
FAIL weak-tests: tests/test_economy.py::test_venda_nova sem assert/pytest.raises/helper de asserção
INFO weak-tests: xfail novo sem strict=True: tests/test_rest.py::test_insonia (l. 40)
INFO weak-tests: assert-delta tests/test_rest.py 31 -> 27 (-4), 1 teste removido
```

### 3.4 Perfil Hypothesis (`tests/fakes/property_settings.py`)

```text
deterministic_settings(*, max_examples: int) -> hypothesis.settings
# derandomize=True, database=None, deadline=None,
# suppress_health_check=[function_scoped_fixture, too_slow, filter_too_much]
```

## 4. Plano passo a passo

Executor roda só os arquivos do escopo, `bash scripts/dev/pt.sh <arquivos>` (`-n 2` no máximo); nunca a suíte completa.

### Etapa 0 — Medições (sem código)

1. Quantas marcas de pulo sem motivo já existem (informativo, mostra o custo de mover teste de arquivo): 175 marcas, 55 sem motivo.
2. `bash scripts/dev/py.sh -c "import hypothesis; print(hypothesis.__version__)"` com e sem o grupo (`uv sync` sem `--group fuzz`) para provar que hoje a suíte default não tem Hypothesis. 6.170.12 só no grupo `fuzz` antes; agora também em `dev`.

### Etapa 1 — Testes da catraca primeiro (vermelhos: o módulo não existe)

`tests/test_weak_tests.py` (docstring `SPEC-417 R1–R8`):
1. `test_skip_novo_sem_reason_falha`: `old` com `def test_a(): assert 1 == 1`, `new` com o mesmo teste decorado `@pytest.mark.skip` ⇒ `new_marks` devolve 1 marca `has_reason=False`; com `reason="x"` ⇒ 1 marca `has_reason=True`.
2. `test_marca_antiga_nao_conta`: mesma marca nos dois lados ⇒ `new_marks == []`.
3. `test_tirar_reason_de_marca_antiga_conta`: `skipif(c, reason="x")` → `skipif(c)` ⇒ 1 marca nova sem motivo.
4. `test_formas_de_pulo`: `pytest.skip("m")`, `pytest.xfail()`, `pytest.importorskip("x")`, `mark.skip` via `from pytest import mark`, `pytestmark = [pytest.mark.skip]`, `pytest.param(1, marks=pytest.mark.xfail)` ⇒ cada uma detectada com o `qualname` certo.
5. `test_string_com_marca_nao_conta`: `src = 'X = "@pytest.mark.skip"'` ⇒ `marks == []`.
6. `test_justificativa_na_spec`: marca sem motivo em `test_a`; spec com a linha "`test_a` fica em skip até a SPEC-999" ⇒ `justified` True; spec sem a linha ⇒ False.
7. `test_xfail_nao_estrito_vira_info`.
8. `test_teste_novo_sem_assert_falha`: `def test_b(): foo()` ⇒ `["test_b"]`; `assert True` sozinho também falha; com `assert foo() == 1`, `with pytest.raises(ValueError)`, `mock.assert_called_once_with()`, `check_response(r, "/")`, chamada a helper local que tem `assert` ⇒ nenhum.
9. `test_fixture_test_nao_conta` e `test_metodo_em_classe_Test`.
10. `test_assert_delta_relata_remocao`: 3 asserts → 1, e um teste removido ⇒ `(3, 1, 1)`.
11. `test_cli_em_repo_sintetico` (pula se `shutil.which("git")` for `None`): `git init -b main` em `tmp_path`, commit com `tests/test_x.py` (um teste com assert); branch `spec-999` que põe `@pytest.mark.skip` nesse teste e acrescenta `def test_novo(): pass` ⇒ `main(["--base","main","--head","HEAD"])` rc 1 com 2 linhas `FAIL`; commit que corrige os dois (`reason=` e assert) ⇒ rc 0 e linha `OK`. Esta é a evidência "falha antes / passa depois" do campo Evidência.

### Etapa 2 — Implementação da catraca

1. `scripts/dev/weak_tests.py` (R1–R8). Etapa 1 verde.
2. R9: rodar sobre as specs 405–413 e preencher §9. Ajustar R5 se houver falso positivo.

### Etapa 3 — Dependência e perfil

1. `pyproject.toml` (R10) + `uv lock`; conferir `git diff uv.lock` (sem troca de versão) e `git diff --exit-code requirements.txt`; `tests/test_spec192_vercel_packaging.py` verde.
2. `tests/fakes/property_settings.py` (R11).

### Etapa 4 — Propriedades de mecânica e round-trip

1. Escrever `tests/test_mechanics_properties.py` (P1–P5) e `tests/test_persistence_properties.py` (RT1–RT3), com `@deterministic_settings(max_examples=…)`.
2. Rodar. Falhou → R15 (propriedade errada ou bug; bug = `xfail(strict=True)` + `@example` + §9).
3. **Mutação manual por propriedade** (o revisor reproduz; o executor registra em §9 que viu cada uma falhar e voltou ao verde ao desfazer). Cada mutação é aplicada sozinha, no worktree, sem commit:

| Prop. | Mutação | Falha esperada |
|---|---|---|
| P1 | trocar `random.randint(1, sides)` por `random.randint(0, sides)` em `combat_mechanics.py:106` | limite inferior `n + K` |
| P1 | trocar `return max(0, total), " ".join(details)` por `return total, " ".join(details)` em `combat_mechanics.py:114` | `total >= 0` (ex.: `1d4-10`) |
| P2 | trocar `target["vitalidade"] = max(0, vit - dano)` por `target["vitalidade"] = vit - dano` em `services/conflict_damage.py:332` | `vit_depois >= 0` |
| P2 | trocar `absorbed = min(dano, protecao)` por `absorbed = protecao` em `services/conflict_damage.py:283` | `vit_depois <= vit_antes` (dano negativo cura) |
| P3 | trocar `min(ceiling, int(player.get("vitalidade", 0) or 0) + recover)` por `int(player.get("vitalidade", 0) or 0) + recover` em `world_utils.py:281` | `vit_depois <= max_vitalidade` |
| P4 | apagar o guarda `if int(player.get("gold", 0)) < total: return {…}` em `services/economy.py:808-809` | `gold == gold_antes + gold_delta` (o `clamp_gold` zera, o delta não) |
| P4 | trocar `int(player.get("gold", 0)) + total` por `int(player.get("gold", 0)) - total` em `services/economy.py:856` | conservação na venda |
| P5 | trocar `SELL_FACTOR = 0.5` por `SELL_FACTOR = 1.2` em `services/economy.py:75` | `sell <= buy` |
| RT1 | trocar `[-64:]` por `[:64]` em `persistence.py:674` (`processed_action_ids`) | RT1 com mais de 64 ids |
| RT2 | trocar `raw_data.get("archivist_last_run", 0)` por `raw_data.get("archivist_last_run", 0) + 1` em `persistence.py:1029` | ponto fixo `s2 == s1` |
| RT3 | trocar `deepcopy(state.get("conflict_summary"))` por `state.get("conflict_summary")` em `persistence.py:656` | `s0` mutado (ganha `conflict_id`) |

   Se a propriedade **não** falhar com a mutação, ela está fraca: reforçar o gerador (ex.: P4 precisa sortear ouro abaixo do preço) até falhar. Propriedade marcada `xfail` por R15 não tem como provar a mutação; vale o exemplo mínimo.
4. R14 (tempo) e R16 (`.hypothesis/`).

### Etapa 5 — Guia e autoaplicação

1. R17 em `docs/guias/TESTES.md`.
2. `bash scripts/dev/py.sh scripts/dev/weak_tests.py --spec 417` na própria branch: esperado `OK` (os `xfail` de R15, se houver, citados em §9). `ruff format --check` + `ruff check` nos `.py` tocados; `bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD`.

## 5. Critérios de aceite

- [ ] `tests/test_weak_tests.py` verde; `test_cli_em_repo_sintetico` visto vermelho antes do script (hand-back).
- [ ] R9: tabela 405–413 em §9, falso positivo = 0 (ou justificado um a um).
- [ ] `weak_tests.py --spec 417` na branch desta spec: rc 0, linha `OK`.
- [ ] `hypothesis` no grupo `dev`; `git diff --exit-code requirements.txt` limpo; versão do lock inalterada; `tests/test_spec192_vercel_packaging.py` verde.
- [ ] As 11 mutações de §4.4 vistas falhando e voltando ao verde (registro em §9), salvo propriedades em `xfail` por R15.
- [ ] Tempos de R14 dentro da meta (valores em §9); nenhum `.hypothesis/` no `git status`.
- [ ] Todo achado de bug listado em §9 com teste `xfail(strict=True)` + `@example`, e nenhum arquivo de produto no diff (`git diff --name-only main...HEAD` sem `*.py` fora de `tests/` e `scripts/dev/weak_tests.py`).
- [ ] `docs/guias/TESTES.md` com a linha de R17.
- [ ] `ruff format --check`/`ruff check` limpos; `dup_helpers.py --diff` sem helper duplicado (D2).
- [ ] `uv run pytest` verde (suíte completa, 1× pelo coordenador no pouso).

## 6. Smoke test com LLM real

Não se aplica: tooling e testes offline, sem LLM, prompt, rota ou staging. O smoke real é (1) o script sobre o histórico verdadeiro (R9) e sobre a própria branch (Etapa 5), e (2) a camada 2 do pouso com os dois arquivos de propriedade dentro do tempo de R14 sob `-n auto`. o valor do pouso fica com o coordenador (medido aqui: ~2,6 s somando os dois arquivos em `-n 2`).

## 7. Riscos & compatibilidade

- **Falso positivo trava pouso.** Teste legítimo que delega a um helper importado sem prefixo reprova R5. Mitigação: resolução de helper local (um nível), prefixos, `ASSERT_HELPERS` e a calibração de R9 antes de ligar. Mover teste com `skip` sem motivo de um arquivo para outro conta como novo: desejado (o motivo é barato de escrever).
- **Duplicação com a SPEC-415.** `red_green.py` (SPEC-415 §3.2) terá `added_tests(old_src, new_src)`, que é o mesmo cálculo de `test_functions` + diferença de nomes. Quem pousar depois importa do outro (D2); o `dup_helpers.py --diff` do revisor confere.
- **Flake da camada 2.** `derandomize=True` torna a geração função do nome do teste; `database=None` evita reaproveitar exemplo de outra máquina; `deadline=None` evita falha por CPU disputada. Uma falha intermitente é bug do teste (estado compartilhado do autouse entre exemplos, como em SPEC-338 §7), nunca retry.
- **Suspeitas que as propriedades devem confirmar ou descartar** (hipóteses da leitura, nada provado; R15 decide):
  - P4(c): `execute_trade` copia `world` raso (`services/economy.py:786`) e `_ensure_stock` devolve o dict de estoque compartilhado (`:490-497`); a compra decrementa esse dict (`:812`), o que mutaria o estado de entrada, contra o comentário de `:571-572`.
  - P4(b): itens do intendente (`:575-577`) e o `rare_stock` de keeper leal (`:580-582`) entram no estoque efetivo sem existir em `merchant_stocks[mid]`; a compra grava `get(iid, 0) - qty` (`:812`), possivelmente negativo.
  - P5: a venda usa o inverso da relação com clamp até 1,50 (`services/reputation.py:1078-1079`) e a compra no QG soma o desconto de patente (piso 0,1 no código, 0,8 nos dados, `services/faction_membership.py:1097`); com o traço `comercio` no extremo, `sell` pode passar `buy`. Depende do intervalo de `trait_dc_modifier`, não lido.
  - D4: texto com surrogate isolado (que um JSON `"\ud800"` produz) faria `save_game_state` devolver `False` em silêncio (`persistence.py:609-610`, `:827-836`). Fora do gerador por padrão.
- **Tempo da suíte default.** +2 arquivos; teto em R14. Se a camada 2 subir mais que ~15 s, cortar `max_examples` primeiro.
- **Lock.** Mudar o grupo `dev` regrava `uv.lock`; conflito com outra branch que mexa no lock é resolvido por `uv lock` de novo.
- Saves, MockLLM, quota: nenhum impacto (nada de produto muda).

## 8. Decisões do dono

Delegadas ao coordenador; proposta entre parênteses.

- **D1** — R3 literal (pulo novo passa se tiver `reason=` **ou** linha na spec) ou estrito (exige **as duas**)? (Literal, como no item A4. O estrito é mais forte contra `reason="flaky"`, mas a linha na spec já é o que o revisor lê; reavaliar depois de R9.)
- **D2** — Ligação ao pouso: (a) emendar a SPEC-415, ainda `approved`, para o `land_check` incluir o check `weak-tests` chamando R8, ou (b) follow-up depois que as duas pousarem; até lá o coordenador roda o comando no `/spec-land`. (a, se a 415 ainda não estiver em execução; senão b.) E quem é dono de `added_tests`/`test_functions`: quem pousar primeiro, o segundo importa.
- **D3** — Unificar `tests/fakes/api_fuzz.py::fuzz_settings` com `deterministic_settings`? (Não nesta spec: a 338 está `done` e o ganho é 6 linhas.)
- **D4** — Incluir surrogates isolados no gerador de RT1–RT3? (Não por padrão; se o coordenador quiser testar a suspeita do §7, um `@example` único com `"\ud800"`, que provavelmente vira `xfail` por R15.)

## 9. Execução

(Preenchido pelo executor: R9, R14, R16, mutações de §4.4, achados de R15.)
- **Aprovação (2026-11-12):** aprovada pelo coordenador por delegação do dono ("executa as mudanças", 12/11). D1: basta `reason=` OU linha na spec. D2: esta spec executa depois da SPEC-415 pousar; o executor então liga `weak_tests.check()` ao `land_check` e reusa a detecção de teste novo do `red_green.py` em vez de duplicar (a restrição "não edite `land_check.sh`" cai nesse ponto). D3 e D4 aceitas. Bug de produto achado por propriedade: `xfail(strict=True)` + hand-back, sem conserto aqui (R15).
- **Execução (2026-11-12, Terra):**
  - Bloco A: `scripts/dev/weak_tests.py` + `tests/test_weak_tests.py` (22 testes); `weak_tests.py --spec 417 --worktree` dá `OK`. Reuso de `red_green.added_tests` (sem duplicar a detecção de teste novo). Ligado ao `land_check` como check `weak-tests` (depois de `growth`, script irmão do `land_check.py`), com teste em `tests/test_land_check.py` e cópia dos scripts no fixture de `tests/test_wt_sh.py`.
  - Bloco B: `hypothesis>=6.170,<7` no grupo `dev` (`uv.lock` +2 linhas); `tests/fakes/property_settings.py`; `tests/test_mechanics_properties.py` (P1-P5) e `tests/test_persistence_properties.py` (RT1-RT3). R17 em `docs/guias/TESTES.md`. Medições e mutações: `docs/spec417/medicoes.md`.
  - Limites escritos: P5 não monta estado de keeper/patente (varre item x mercador no estado base); P3 controla o clima trocando `world_utils.weather_effects` (os dois ramos); RT1 aceita como normalização de save/load que `conflict_summary` ganhe `conflict_id`/`conflict_turn`.
  - **Achado 1 (R15, bug de produto, não consertado):** `economy.execute_trade` muta o `state` de entrada quando a loja já foi visitada, pois `world = dict(state["world"])` é cópia rasa e `world["merchant_stocks"][mid][iid] -= qty` (`services/economy.py:812`) escreve no dicionário compartilhado (a venda de item único também, `:876`). Teste `test_p4_trade_does_not_mutate_input`: `xfail` estrito com `@example(location="brekmar", gold=5000, mode="buy", pick=0, qty=1)`.
  - D4: sem surrogates no gerador (default aceito).
