# SPEC-212 — follow-up da Etapa 0 (defeito de autoria em `vertical-journey.spec.ts`)

Escrito pelo executor de produto. Os arquivos da Etapa 0 (jornada, oráculos, evaluator, registry, lock) **não foram
editados**; este é o único item que impede V01–V09 de ficarem verdes de forma estável. Precisa de uma nova
tarefa de autoria de eval (relock + `eval-governance`).

## Item: nenhum passo pós-reload resolve o modal de nível (V07 e V08; flaky ~50% das execuções)

- Sintoma (stack real + MockLLM, 10 execuções completas de J-V1): V07 falha em ~50% dos runs, em qualquer viewport, com
  `TimeoutError: locator.click` na aba Codex (linha ~173, `snapshotTabs`) — ou, em outra amostra, com
  `expected "nova arcádia"` vs `"mapa do mundo · consultando o mapa da jornada…"`. V08/V09 ficam `did not run`.
- Causa 1 (principal): ao fim de V05 a jornada faz `page.reload()` + `openSaveByName(HERO)`. Se a vitória subiu o herói
  de nível (XP do abate varia com o dado sem seed), o `pending_choices` da campanha reabre o `LevelUpModal` (aria-modal)
  no reload — comportamento intencional do produto (Fase 4.1: escolha pendente reabre o modal). O modal cobre a faixa de
  abas e o clique em `#ws-tab-codex` nunca é acionável. O screenshot de falha mostra "Nível 2 alcançado — Expanda seu Acervo".
  `settleLevelUp()` é chamado em `submit()`, mas **não** antes de `snapshotTabs()` em V07.
- Causa 2: o poll de `snapshotTabs` espera só sair de `consultando os registros` (abas de dossiê). A aba Mapa mostra
  `Consultando o mapa da jornada…` até o `GET /game/map` voltar; a leitura imediata pega o placeholder.
- Correção sugerida (só na jornada, sem afrouxar nenhum oráculo): chamar `await settleLevelUp()` ao fim de `openSaveByName`
  (cobre V05→V07 e os três reloads de V08; é no-op sem modal) e estender o poll de `snapshotTabs` para também aguardar
  `consultando o mapa`.
- Verificado: uma cópia temporária da jornada com exatamente essas duas mudanças (não commitada) ficou verde nas execuções
  descritas no relatório do executor; sem `settleLevelUp` em `openSaveByName`, V07 passa mas V08 falha pelo mesmo motivo
  (`locator.click` coberto pelo modal após `page.reload()`).
- Por que não foi corrigido no produto: o modal reabrir com escolha pendente é o contrato da Fase 4.1 e da SPEC-204 R16;
  suprimir isso para a jornada passar seria relaxar o produto para a régua.

## Itens que o executor de produto resolveu (sem tocar a régua)

R13 stream nulo (corrigido no servidor), modal de nível cobrindo "Continuar" do desfecho (sequência desfecho → nível),
aliado fora do manifesto (documentado: contrato SPEC-203 é de `enemies`), dado sem seed (documentado: spec §3.1 proíbe tocar
a mecânica), beacon `ERR_ABORTED` (documentado: o cliente não usa `keepalive`; allowlist mantida). Ver
`docs/spec212/known-issues.md`.
