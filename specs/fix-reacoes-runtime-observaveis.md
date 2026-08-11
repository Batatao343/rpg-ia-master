# SPEC — Cartas inimigas efetivas e reações observáveis no runtime

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `conflito-06-reacoes-movimento`, `conflito-08-perfil-tatico`
> e `hardening-playtest-observabilidade`
> **Desbloqueia:** aceite real verificável do `conflito-13`

---

## 1. Contexto & Objetivo

O relatório do smoke real exigia tornar reações observáveis. Depois de exportar
`combat.last_reactions`, o rerun offline formal `20260725-140705-420702`
registrou **67 turnos de conflito e zero reação**. A causa é de integração:
`_enemy_reaction_card` aceita somente um `dict` com `tipo="reacao"`, enquanto o
bestiário persiste IDs de Carta. A mesma auditoria mostrou que
`_enemy_offensive_card` tem o mesmo defeito: as 113 referências a Cartas ativas
curadas também são IDs e, portanto, todas as assinaturas especiais estavam
inacessíveis. Além disso, a materialização de cache miss não atribui reação e
os custos/frequências inimigos não têm um consumidor próprio. O motor puro e o
conteúdo existem, mas a vertical natural do jogo não consegue alcançá-los.

Esta spec liga catálogo, ficha e janela de reação sem introduzir LLM na
resolução. A reação defensiva deve durar somente o ataque que a disparou, ser
limitada pela frequência da Carta e aparecer no JSONL do playtest.

## 2. Requisitos

- **R1 — Catálogo por ID.** Cartas inimigas ativas e de reação persistidas como
  IDs são resolvidas
  pelo catálogo canônico. Dict legado só é aceito se tiver ID conhecido e
  contrato válido; payload mecânico livre não entra no resolver.
- **R2 — Reação materializada.** Toda ficha inimiga criada por cache miss recebe
  uma Carta de reação curada em Python/dados. Fichas curadas ou saves antigos
  sem reação recebem o mesmo default no adaptador, sem reescrever a fonte.
- **R3 — Efeito delimitado.** A reação defensiva concede o modificador fechado
  `protected` apenas ao ataque disparador; não ativa `guarding` sustentado.
- **R4 — Frequência e recursos.** Carta `frequencia="cena"` dispara no máximo
  uma vez por inimigo no conflito. Cartas ativas/reação debitam um pool inimigo
  fechado, derivado deterministicamente da ficha v4, e nunca usam
  `player.prepared_cards`; custo, frequência e casamento de gatilho são
  validados antes da resolução.
- **R4b — Assinatura ofensiva.** A primeira Carta ativa disponível vira
  `TurnStep(kind="card")`, resolve pelo catálogo, consome custo/frequência no
  ator inimigo e, quando esgotada, a IA retorna a ataque/tática válida em vez de
  repetir uma ação impossível.
- **R5 — Observabilidade.** Toda reação resolvida entra em
  `combat.last_reactions`, no JSONL e na cobertura agregada. O smoke de aceite
  deve registrar pelo menos uma reação natural.
- **R6 — Zero LLM.** Seleção, validação, custo, efeito e frequência permanecem
  totalmente determinísticos no Python.

### Fora de escopo

- UI para o jogador escolher reações (`conflito-16`).
- Rebalancear o efeito ou o texto de todas as Cartas ativas de inimigo.
- Implementar contra-ataques ou cadeias novas além da reação defensiva curada.

## 3. Design técnico

- `data/cards/bestiario.json`: Carta curada `bst_defesa_instintiva`, do tipo
  `reacao`, gatilho `ao_ser_atacado`, frequência `cena`, efeito fechado
  `buff_esquiva` e custo zero.
- `scripts/migrate_bestiary_v4.py`: mantém a Carta no catálogo gerado.
- `agents/bestiary.py`: `materialize_enemy_concept` atribui o ID curado.
- `services/conflict_orchestrator.py`:
  - resolve IDs ativos/de reação com `services.cards.get_card`;
  - garante o default no adaptador para fichas existentes;
  - materializa Entropia inimiga por uma fórmula fechada e registra uso bounded
    por turno/cena no próprio ator;
  - aplica `conflict_scene.grant_tactical_modifier("protected", ...)` antes do
    ataque e nunca `guard(..., spend=False)`.
- `services/cards.py`: helpers puros de disponibilidade/consumo de Carta inimiga
  validam catálogo, pertença à ficha, custo e frequência sem tocar no player.
- Nenhum campo novo obrigatório de save: a lista de usos é opcional, bounded e
  serializável; ausência significa “ainda não usada”.

## 4. Plano passo a passo

### Etapa 1 — Catálogo e materialização

1. **Testes:** cache miss e ficha curada/legada terminam com uma reação resolvível
   por ID; Carta ativa por ID é selecionada; ID/dict desconhecido é ignorado.
2. **Implementação:** Carta curada, materializador e adaptador.

### Etapa 2 — Resolução delimitada

1. **Testes:** ataque dispara uma reação, aplica Desvantagem somente nesse ataque
   e não deixa `guarding`; o segundo ataque na mesma cena não repete a Carta.
   Carta ativa debita recurso/frequência do inimigo sem consultar o acervo do
   jogador e depois cai para ação válida.
2. **Implementação:** resolução por catálogo, pool/frequência bounded e
   modificador `protected`.

### Etapa 3 — Vertical do harness

1. **Testes:** `run_round` real registra o link em `last_reactions`; serialização
   JSONL e cobertura agregada preservam a reação.
2. **Verificação:** rerun offline 13×30 tem `reactions > 0`, zero invariant
   `error` e manifesto completo.

## 5. Critérios de aceite

- [x] Cartas inimigas ativas e de reação por ID alcançam o resolver natural.
- [x] Cache miss, curadoria e saves antigos têm default determinístico.
- [x] Reação afeta só o ataque disparador e respeita frequência por cena.
- [x] Carta ofensiva consome recurso/frequência do inimigo e tem fallback válido.
- [x] `combat.last_reactions` e JSONL registram o resultado.
- [x] Rerun offline formal tem `reactions > 0` e zero erro.
- [x] Smoke real tem ao menos uma reação e zero LLM dentro da resolução.
- [x] `uv run pytest` e lint de conteúdo verdes.

## 6. Smoke test com LLM real

Rodar os 13 perfis por 30 turnos com o LLM real. Confirmar no JSONL:

1. pelo menos uma reação com `card_id=bst_defesa_instintiva`;
2. o turno contém `combat_agent`, sem invoke de LLM entre declaração e resolução;
3. nenhuma Carta reage duas vezes pelo mesmo inimigo na mesma cena;
4. zero `combat.no_progress`, `action.declaration_matches` ou erro de Vitalidade.

**Evidência (2026-08-02):** a matriz real registrou 4 reações e 28 ações
táticas, sem chamada LLM dentro do resolver e sem violação mecânica. A matriz
offline formal `20260802-154317-705789` também ficou verde.

## 7. Riscos & compatibilidade

- A primeira defesa de cada inimigo fica mais forte; frequência por cena contém
  o impacto de balanceamento.
- Saves antigos não exigem migração e recebem o default no adaptador.
- Mock e LLM real usam a mesma mecânica; só a descrição/conceito do encontro
  varia por provider.
