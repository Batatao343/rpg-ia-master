# SPEC — Fase 7.3 — Separação público/segredo nos NPCs do Codex

> **Status:** `done` (2026-07-05)
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** 7.1 (validadores) `done`; 7.2 (overrides/idempotência do migrate) `done`
> **Desbloqueia:** revelação controlada de segredos de NPC (usa canal da 3.2)

---

## 1. Contexto & Objetivo

Débito da Fase 2.5: os `.md` de NPC mesclam descrição pública com a verdade
oculta no MESMO documento `visibility: public`. Exemplo real — `npc_valerius.md`
traz "História real: ... Fez pacto com Daruun: cedeu a família ... em troca de
imortalidade" e "Motivação real: ...". Consequência: `codex_body("npc_valerius")`
(usado pelo context builder 2.8 e pelo `npc_actor`) e os chunks RAG `public`
entregam o segredo direto ao narrador — o LLM pode vazar o twist central do
mundo num diálogo casual de taverna.

Esta spec faz o `migrate_lore_nova.py` **dividir** cada NPC em dois documentos:
o público (papel, aparência, comportamento, motivação declarada) e um doc
paralelo `visibility: hidden` com os parágrafos secretos (história real,
motivação real, pactos, rumores confirmados). A divisão é determinística por
**rótulo de parágrafo** (os arquivos de NPC seguem o padrão `Rótulo: texto`),
com lista curada de rótulos secretos — zero LLM. A infra de visibilidade já
existe (RAG filtra `max_visibility="public"`; `codex_body` só devolve `public`);
o que falta é o conteúdo estar do lado certo da cerca.

## 2. Requisitos

- **R1 — Split determinístico:** parágrafos de NPC cujo rótulo (prefixo até `:`,
  normalizado sem acento/minúsculo) pertence à lista curada
  `_NPC_SECRET_LABELS` saem do doc público e vão para
  `data/codex/npcs/segredos/{npc_id}_segredo.md`.
- **R2 — Lista curada inicial:** `historia real`, `motivacao real`,
  `o que ele esconde`, `o que ela esconde`, `segredo`, `o pacto e seus efeitos`,
  `rumor verdadeiro`, `verdade`. Constante no migrate script, comentada,
  extensível por revisão manual da saída.
- **R3 — Doc de segredo:** frontmatter `id: {npc_id}_segredo`,
  `type: npc_secret`, `visibility: hidden`, `related_entities: [{npc_id}]`,
  mesmo `tags` do NPC. NÃO registra entidade em `entities.json` (mesmo padrão
  dos docs de `secrets/` e `timeline/`). `CODEX_TYPES` do lint 7.1 ganha
  `npc_secret`.
- **R4 — Público limpo:** o doc público resultante não contém nenhum parágrafo
  de rótulo secreto; NPC sem parágrafo secreto não gera arquivo de segredo.
- **R5 — Não-vazamento em runtime:** `codex_body(npc_id)` devolve só o público;
  `codex_body(f"{npc_id}_segredo")` devolve `""` (já garantido pela regra
  `visibility != public` existente); `query_rag(..., max_visibility="public")`
  não retorna chunks do doc de segredo.
- **R6 — Lint (7.1) estendido:** doc `public` de NPC contendo rótulo da lista
  secreta → ERRO (impede regressão quando lore_nova crescer); doc
  `type: npc_secret` com `visibility` ≠ `hidden`/`secret` → ERRO.
- **R7 — Auditoria da divisão:** saída do migrate imprime contagem
  (`N NPCs, M com doc de segredo`); revisão manual da lista de segredos gerados
  faz parte da entrega (rótulo esquecido = vazamento silencioso).

### Fora de escopo

- Mecânica de REVELAÇÃO do segredo ao jogador em gameplay (quest/descoberta
  promove `hidden` → visível) — candidata a spec futura; aqui só se fecha a cerca.
- Segredos de fação (`faction_perspectives` já é `hidden`) e de mundo
  (`secrets/` já é `secret`) — já resolvidos na 2.5.
- Reescrever prosa dos NPCs — split mecânico, texto intacto.

## 3. Design técnico

### Arquivos novos

- `data/codex/npcs/segredos/*.md` — gerados pelo migrate (não editar à mão).
- `tests/test_fase73.py`

### Arquivos alterados

- `scripts/migrate_lore_nova.py` — no bloco de npcs.txt: função
  `split_npc_secrets(body) -> tuple[str, str]` (público, secreto); escreve o
  segundo arquivo quando a parte secreta é não-vazia.
- `services/content_validator.py` — R6 (validador `visibility` ganha os dois
  checks; `CODEX_TYPES` += `npc_secret`).
- `data/codex/**` regenerado (rodar o migrate) + `uv run python rag.py`
  (reindexar — chunks mudam de visibilidade).

### Assinaturas

```python
# scripts/migrate_lore_nova.py
_NPC_SECRET_LABELS: frozenset[str]  # R2, normalizado (sem acento, casefold)

def split_npc_secrets(body: str) -> Tuple[str, str]:
    """Divide o corpo de um NPC em (publico, secreto) por rótulo de parágrafo.

    Parágrafo = bloco separado por linha em branco. Rótulo = texto antes do
    primeiro ':' na primeira linha do bloco, normalizado via _strip_accents +
    casefold. Sem rótulo (linha sem ':') = público. Título '# ...' fica no público.
    """
```

Doc de segredo gerado (exemplo real):

```markdown
---
id: npc_valerius_segredo
type: npc_secret
name: Lorde Protetor Valerius — Segredos
aliases: []
tags: [Valerius, Governante, Imortal, Pacto]
visibility: hidden
related_entities: [npc_valerius]
---

# LORDE PROTETOR VALERIUS — O QUE NÃO É DITO

História real: Nobre mediano que lutou sob Elaryin ... pacto com Daruun ...

Motivação real: Não está completamente claro nem para ele. ...
```

Escolha `hidden` (não `secret`): segue a sugestão do ROADMAP e o precedente das
perspectivas de fação — `secret` fica reservado ao arquivo `secrets.txt`
(verdades de mundo); segredo de NPC é revelável em jogo.

`rumor verdadeiro`: o RUMOR circula publicamente (já existe em `rumors.txt`
público); o que o doc de NPC marca é a CONFIRMAÇÃO de que é verdadeiro — isso é
spoiler, vai para o hidden. Documentar no comentário da constante.

### Interação com 7.2

Split roda ANTES de `apply_overrides` no `main()` — override pode então curar o
doc público E o de segredo por id (`npc_x` / `npc_x_segredo`), inclusive mover
parágrafo mal classificado via curadoria sem tocar na lista de rótulos.

## 4. Plano passo a passo

### Etapa 1 — `split_npc_secrets`

1. **Testes** (`tests/test_fase73.py`): `test_split_move_historia_real`;
   `test_split_preserva_paragrafo_sem_rotulo`; `test_split_rotulo_com_acento`
   ("Motivação real:" casa `motivacao real`); `test_split_sem_segredo_devolve_vazio`;
   `test_split_titulo_fica_no_publico`.
2. **Implementação:** constante + função no migrate script.
3. **Verificação:** `/qa` verde.

### Etapa 2 — Migrate escreve o doc paralelo

1. **Testes:** `test_migrate_gera_doc_segredo_hidden` (fixture npcs.txt mínima
   em tmp → arquivo `segredos/npc_x_segredo.md` com frontmatter R3);
   `test_npc_sem_segredo_nao_gera_arquivo`;
   `test_segredo_nao_registra_entidade` (entities.json sem `npc_x_segredo`).
2. **Implementação:** integração no bloco npcs do `main()` + contagem R7.
3. **Verificação:** `/qa` verde.

### Etapa 3 — Lint anti-regressão

1. **Testes:** `test_lint_public_com_rotulo_secreto_erro`;
   `test_lint_npc_secret_public_erro`; `test_lint_npc_secret_hidden_ok`.
2. **Implementação:** checks no `content_validator` (a lista de rótulos vira
   import do migrate script ou constante compartilhada — evitar duplicação).
3. **Verificação:** `/qa` verde.

### Etapa 4 — Regeneração real + auditoria + reindex

1. **Implementação:** rodar `uv run python scripts/migrate_lore_nova.py`;
   **ler a lista dos docs de segredo gerados** (R7) e caçar vazamento restante
   (`grep -il "pacto\|na verdade\|segredo" data/codex/npcs/*.md` nos públicos);
   rótulo novo achado → adicionar à constante e rodar de novo; rodar
   `uv run python rag.py` (reindex com gate 7.2).
2. **Testes:** `test_valerius_publico_sem_pacto` (dado real: doc público de
   `npc_valerius` não contém "pacto com Daruun"); `test_valerius_segredo_hidden`.
3. **Verificação:** `uv run pytest` completo verde; lint do repo (gate R8 da
   7.1) verde.

## 5. Critérios de aceite

- [x] `npc_valerius.md` público sem "História real"/"Motivação real"; conteúdo
      em `npcs/segredos/npc_valerius_segredo.md` com `visibility: hidden`
- [x] `codex_body("npc_valerius")` sem segredo; `codex_body("npc_valerius_segredo") == ""`
- [x] Lint acusa ERRO se rótulo secreto voltar a doc público de NPC
- [x] Auditoria manual dos docs gerados feita — lista cresceu de 8 para 15
      rótulos (7 achados na auditoria, comentados na constante); 141 NPCs,
      14 com doc de segredo
- [x] Reindex rodado — FAISS reflete a nova visibilidade (2×: pós-split e
      pós-correção do Daruun)
- [x] `uv run pytest` verde (suíte completa offline — 581 testes)
- [x] Guard de FallbackLLM — N/A (zero LLM nesta spec)
- [x] Saves antigos continuam carregando (Codex não é estado de save)

**Desvios / achados da auditoria:**
- `NPC_SECRET_LABELS` mora em `services/content_validator.py` e o migrate
  importa de lá (spec deixava as duas opções em aberto).
- **Vazamento inline achado no smoke:** o doc público do DEMÔNIO Daruun contava
  o pacto com Valerius dentro do parágrafo "Natureza:" (sem rótulo secreto).
  Corrigido na FONTE (`lore_nova/npcs.txt`): frase movida para parágrafo
  "Segredo:" → split manda pro hidden. `query_rag` public confirmado limpo.
- Smoke narrativo real (1 request FAST): narrador descreveu Valerius só pela
  persona pública (Código de Ferro, Legião, execuções) — zero Daruun/pacto.
- Pendência de curadoria (registrada no ROADMAP): NPCs públicos do norte citam
  a Rede Carmesim como ameaça conhecida enquanto a timeline era-7 é `hidden`.
- `tests/test_fase25.py::test_codex_frontmatter_valido` atualizado: docs
  `npc_secret` não registram entidade (mesmo padrão story_/secret_/timeline_).

## 6. Smoke test com LLM real

(3–4 requests, valida não-vazamento fim a fim)

1. Novo jogo em Nova Arcádia; perguntar ao narrador/NPC sobre Valerius
   ("o que se sabe sobre o Lorde Protetor?") → resposta usa persona pública
   (ordem, Código de Ferro), **sem** pacto/Daruun/imortalidade.
2. Conferir no log do context builder que nenhum chunk `hidden` entrou no
   contexto do storyteller.
3. (Opcional, 1 request) `query_rag("pacto de Valerius", "lore",
   max_visibility="public")` → nenhum chunk do doc de segredo.

## 7. Riscos & compatibilidade

- **Rótulo fora da lista = vazamento silencioso** — maior risco. Mitigação
  tripla: auditoria manual (Etapa 4), lint anti-regressão (R6) e curadoria via
  override 7.2 para casos pontuais.
- **NPCs "mistério ambulante"** (A Senhora Sem Rosto etc.) podem ficar com doc
  público magro — aceitável: mistério É a face pública; ajustar via override se
  a persona pública precisar de mais texto.
- **Qualidade de contexto do npc_actor cai?** O agente perde a motivação real —
  intencional (não-onisciência); se um NPC precisar ATUAR sobre o próprio
  segredo, isso é a spec futura de revelação, não regressão desta.
- **Saves antigos:** Codex é dado autoral, não save — zero impacto.
- **MockLLM/FallbackLLM:** split e lint 100% offline; smoke real só valida o
  não-vazamento narrativo.
- **Quota:** smoke usa 3–4 requests FAST — dentro do bucket diário.
