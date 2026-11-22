# SPEC-425 — arte-troca-modelo-imagem-gpt-image-2-6

> **Status:** `in-progress` (22/11: Etapa 0 entregue, sem card novo; Etapas 1–3 esperam o dono. Aprovada em 22/11, pelo coordenador, por delegação: vale para a **Etapa 0** e para D2, D4, D5, D6, D7 e D9 como recomendado. As Etapas 1–3 esperam o dono: D8 (chave e gasto de até US$ 2,00), D1 (variante, olhando a ficha de contato) e D3 se o teto passar de US$ 0,12. Veto do dono continua possível)
> **Criada:** 2026-11-22 · **Atualizada:** 2026-11-22
> **Depende de:** SPEC-125, SPEC-326 e SPEC-352 (`done`); SPEC-409 (`in-progress`: o card de imagem renovado em dezembro segue o runbook dela)
> **Desbloqueia:** arte dinâmica no staging depois de 10/02/2027 (o modelo atual desliga nessa data)
> **Risco:** `alto`. Mexe no caminho de pagamento: o card de imagem decide se a cotação abre (`services/image_pricing.py:22-26`) e se o custo é exato (`:29-70`); o `max_provider_usd` do profile vira o teto em Estilhas que o jogador paga (`services/image_quotes.py:84-86`). Também troca uma API externa paga e a estética canônica da Valoria. → `spec-reviewer` obrigatório.
> **EXECUTOR_MODEL:** `Terra` (`spec-executor`, Sonnet), uma etapa por vez · **REVIEW_MODEL:** `spec-reviewer` (Opus) nas Etapas 0 e 2; a rubrica de estilo (Etapa 1) é do Opus, e a escolha final é do dono.
> **EVAL_AUTHORING_REQUIRED:** `false`. Conferido em 22/11: `git grep "dynamic_art_profiles|image_pricing|openai_images|gpt-image" -- evals playtest` não acha nada, e nenhum caminho de `evals/protected-paths.txt` é tocado.
> **Requer:** dono: `OPENAI_API_KEY` com acesso a `gpt-image-2.6-*` (talvez exija a "API Organization Verification", `docs/spec425/fontes.md:83`) e gasto de até US$ 2,00 na Etapa 1 · staging: publicar os price profiles, `vercel_env.py` e deploy (Etapa 3) · web: reler a página de preço no dia em que o card for gerado (runbook `docs/spec197/runbooks/budget.md:64-66`)
> **Domínios de revisão:** api (parâmetros do provider externo), persistência (linhas imutáveis de `image_price_profiles` e `profile_version` na chave de dedupe)
> **Evidência:** (a) `require_image_prices("gpt-image-2.6-sunburst", …)` hoje levanta `PricingUnavailable` (`services/image_pricing.py:25`), e o teste novo exige que passe; (b) o adapter hoje não envia `complexity` (`infrastructure/openai_images.py:89-91`), e o teste novo exige o campo quando o brief o traz; (c) `docs/spec425/medicao.json` com `usage` real por formato; (d) smoke §6 no staging.

---

## 1. Contexto & Objetivo

O projeto fixa `gpt-image-2-2026-04-21` em `data/dynamic_art_profiles.json:4`, no card
`data/pricing/image_rate_card_2026-11-13.json:5` e nos profiles do staging (`docs/spec409/fontes.md:149-151`).
A OpenAI descontinuou esse modelo, que desliga em **10/02/2027**, e indicou como substitutos
`gpt-image-2.6-sunburst` e `gpt-image-2.6-flare` (`docs/spec425/fontes.md:11`). O preço por token é igual nos três
(`fontes.md:55-60`), mas o custo por imagem é desconhecido: não há tabela de tokens por tamanho, e o padrão novo é
`complexity: high` (`fontes.md:79`). O custo só aparece medindo `usage` numa chamada real (`fontes.md:68-70`).

Hoje o custo entra no produto por dois caminhos. O card por token prica o `usage` observado
(`services/image_pricing.py:29-70`) e aceita **um** modelo (`:25`, `:35`). O teto por imagem é o
`max_provider_usd` de `app.image_price_profiles`, uma linha imutável por modelo e tamanho
(`supabase/migrations/20261012160000_image_quotes.sql:2-12`). No staging ele vale US$ 0,08, medido em cerca de
US$ 0,05 com referências (`specs/SPEC-326-arte-dinamica-consistencia-valoria.md:322-328`). Não existe
`usd_per_image` no card; o número por imagem é esse teto, mais `IMAGE_COST_USD` em `scripts/finops_margin_sim.py:37`.

Objetivo: medir as duas variantes com teto de gasto, escolher uma por critério objetivo (com a decisão final de
estilo do dono) e trocar o modelo sem quebrar cotação, débito, jobs em voo nem a consistência visual da SPEC-326.
A troca precisa ser reversível até 10/02/2027 e não pode atrapalhar a renovação dos cards. Os cards vencem em
13/12/2026, e `tests/test_rate_card_freshness.py` deixa a `main` vermelha a partir de 03/12 (`budget.md:57-60`).

## 2. Requisitos

**Card e cobrança**

- **R1** — O card de imagem ganha `extra_models: list[str]`, cobrados pelas mesmas taxas do card. Ele traz
  `gpt-image-2.6-sunburst` e `gpt-image-2.6-flare`, e o `derivation` cita as linhas literais da página de preço.
  `require_image_prices` e `price_image_event` aceitam `model ∈ {card["model"], *extra_models}`. Modelo fora do
  conjunto continua `PricingUnavailable` ou evento não exato.
- **R2** — Card com `observed_at ≥ 2027-02-10` não lista `gpt-image-2-2026-04-21`, nem em `model` nem em
  `extra_models` (gate em `tests/test_pricing_card_files.py`).
- **R3** — O card é um **arquivo novo** (`budget.md:47-48`). O antigo segue intacto, com sha256 conferido.

**Parâmetros do provider**

- **R4** — `ImageGenerationInput` (`infrastructure/ports.py:10-15`) ganha `complexity: str | None = None`. O adapter
  envia `complexity` nas duas rotas (generations em JSON, edits em form) só quando o valor não é `None`, e o inclui
  na `Idempotency-Key` (`infrastructure/openai_images.py:81`).
- **R5** — `complexity` vem **só do brief** (`complexity_for(brief)`, sem cair para o profile, ao contrário de
  `quality_for`, `services/art_brief.py:115-123`). Os builders gravam o valor no brief a partir de
  `formats.<fmt>.complexity`, como já fazem com `quality` (`art_brief.py:181`, `:237`), e o builder de criatura também
  (`:298`). Assim, um brief cotado antes da troca nunca manda `complexity` ao modelo antigo.
- **R6** — O profile só aceita `complexity ∈ {low, medium, high}`, e só quando `model` começa com `gpt-image-2.6-`.
  Com `gpt-image-2-2026-04-21`, nenhum formato tem `complexity` (teste de validação do JSON).
- **R7** — `quality` segue `medium` nos três formatos (`data/dynamic_art_profiles.json:6-8`). O adapter não manda
  `user`, `safety_identifier` nem `input_fidelity`, como hoje (`openai_images.py:89-91`; o `user` obsoleto,
  `fontes.md:82`, já não é enviado).

**Medição (Etapa 1, chamada real)**

- **R8** — `scripts/art/measure_image_model.py` roda o caminho de produção (builder de brief, referências canônicas,
  `OpenAIImageGenerator`, `safe_provider_usage`, `price_image_event`) sobre a matriz da §4 Etapa 1. Para cada
  chamada, grava em `docs/spec425/medicao.json`: `model`, `format`, `size`, `quality`, `complexity`,
  `refs` (quantidade), `endpoint`, `http_status`, `latency_ms`, o `usage` saneado, `cost_usd`, `cost_basis` e
  `canon_min_hamming` (`services/art_similarity.py`). Bytes de imagem vão só para um diretório fora do repo
  (`--out-dir`). Prompt não vai para o JSON; vai só `prompt_hash`.
- **R9** — Teto obrigatório `--max-usd` (≤ 2,00, que o script recusa ultrapassar). Antes de cada chamada, o script
  para se `gasto + 0,25 > max`. Ele também para na primeira imagem com `cost_usd > 0,25` e na primeira com
  `cost_basis != "rate_card"`, porque esse formato de `usage` não é cobrável com exatidão e a troca não pode seguir.
  Sem `--confirm-spend` o script só imprime o plano. A chave é lida pelo nome da variável e nunca impressa.
- **R10** — Regra do teto por formato: `max_provider_usd = max(cost_usd do modelo e complexity escolhidos naquele
  tamanho) × 1,5`, arredondado para cima em 0,01, com piso de 0,08. Se o resultado passar de 0,12, o jogador paga
  mais, e quem decide é o dono (D3). `IMAGE_COST_USD` = mediana do retrato do modelo escolhido.

**Troca, reversão e deriva**

- **R11** — A troca é uma mudança de dados: `model`, `profile_version` = `valoria-gpt-image26-<variante>-v1` e
  `formats.*.complexity` em `data/dynamic_art_profiles.json`, mais os ids de `DYNAMIC_ART_PRICE_PROFILES`
  (`scripts/staging/vercel_env.py:120-123`). Nada no código de cobrança muda na Etapa 2.
- **R12** — `scripts/staging/publish_image_profiles.py` (novo) publica dois profiles com `model`, `size` e
  `max_provider_usd` **explícitos**, `--dry-run` e `--confirm-staging <ref>`. Depois confere o que ficou no banco,
  como `publish_rate_card.published_problems` (`scripts/staging/publish_rate_card.py:62-87`). O
  `publish_rate_card.py` continua copiando o modelo dos profiles anteriores (`:24-28`); o contrato dele não muda.
- **R13** — Reversão até 03/02/2027 (uma semana antes do desligamento) = reverter o commit de dados de R11 (modelo antigo, `profile_version`
  `valoria-gpt-image2-v2`, sem `complexity`), apontar `RPG_IMAGE_PRICE_PROFILE_*` para profiles do modelo antigo
  ainda válidos e fazer deploy. O card de R1 cobre os dois modelos, então a reversão não toca em código de cobrança.
  O runbook registra os ids desses profiles e o `expires_at` deles.
- **R14** — `routes/art.py:371-372` deixa de ter id de modelo e `profile_version` literais como fallback e passa a
  ler o profile, como as rotas vizinhas (`:239`, `:446`).
- **R15** — Contra deriva (não há snapshot datada, `fontes.md:105-107`): o `derivation` do card e o runbook dizem
  "sem snapshot datada". `profile_version` inclui a variante. A cada renovação mensal do card, o runbook roda
  `measure_image_model.py --canary`: 1 retrato do Elfo, teto de US$ 0,25. O canário compara `output_tokens` com a
  mediana de `medicao.json` (±30 %) e `canon_min_hamming` com o limiar do profile (`dynamic_art_profiles.json:16`).
  Se sair da faixa, o card não é renovado em silêncio: a divergência fica em `docs/spec425/` e vai ao coordenador.
  Em produção, o excesso sobre o teto já vira `financial_anomaly_milli` (`infrastructure/wallet.py:782-794`) e
  conta no FinOps (`infrastructure/finops_reader.py:213-216`). Não há infraestrutura nova.

### Fora de escopo

- Regenerar imagens já prontas, incluindo os retratos de criatura compartilhados, que são chaveados só por
  `portrait_key` (`supabase/migrations/20261028120000_creature_portraits.sql:12`). Arte antiga e nova convivem (D9).
- `safety_identifier`, `input_fidelity`, SVG/GIF, `quality` acima de `medium`, Batch API e Responses API.
- Classificar a recusa `moderation_blocked` (só no resumo, `fontes.md:92-93`). Hoje a recusa é detectada por
  `"safety"` no corpo (`openai_images.py:111`). Se a Etapa 1 ou o §6 mostrarem outro texto, abre-se uma spec própria.
- Produção (como na SPEC-409, só staging), preço comercial em Estilhas além do teto de R10, e prompt tuning do estilo.
- Mudar timeout ou lease (300 s, `openai_images.py:33`). Se a Etapa 1 medir mais que 240 s, a variante é eliminada (§4).

### Invariantes

- **I1** — Um brief sem `complexity` gera uma requisição sem o campo, byte a byte igual à de hoje
  (teste: `test_sem_complexity_nao_envia_campo`, nas duas rotas).
- **I2** — Uma cotação emitida com o modelo antigo antes da troca ainda é confirmada, despachada e cobrada exata
  depois dela: o worker usa `generation["model"]` (`workers/dynamic_art_jobs.py:216-222`), o card cobre os dois
  modelos e `IMAGE_PRICING_VERSION` não muda na Etapa 2 (teste: `test_quote_modelo_antigo_cobra_apos_troca`).
- **I3** — Oferta com `profile_version` velho é reconstruída e não cotada como está (`routes/art.py:117-124`;
  teste existente `tests/test_image_quotes.py:95-104`, com o literal velho atualizado para `valoria-gpt-image2-v2`).
- **I4** — O profile e o price profile referem o mesmo modelo; senão a cotação dá 503, nunca cobra errado
  (`image_quotes.py:73-79`; teste de profile cujo modelo difere).
- **I5** — Os cards antigos seguem com o sha256 inalterado (`tests/test_pricing_card_files.py:22`).

## 3. Design técnico

- **Alterados:** `infrastructure/ports.py` (campo `complexity`); `infrastructure/openai_images.py` (R4);
  `services/art_brief.py` (`complexity_for`, builders, R5); `services/image_pricing.py` (`priced_models()`, R1);
  `data/pricing/image_rate_card_<AAAA-MM-DD>.json` (novo, R1/R3) e o caminho em `image_pricing.py:16`;
  `data/dynamic_art_profiles.json` (Etapa 2); `routes/art.py:371-372` (R14); `scripts/staging/vercel_env.py:120-123`;
  `scripts/finops_margin_sim.py:37`; `docs/spec197/runbooks/budget.md` § Renovação (canário de R15 e reversão de R13).
- **Novos:** `scripts/art/__init__.py`, `scripts/art/measure_image_model.py`, `scripts/staging/publish_image_profiles.py`,
  `tests/test_image_model_measure.py`, `tests/test_publish_image_profiles.py`.
- **Assinaturas:** `priced_models() -> frozenset[str]`; `complexity_for(brief: Mapping[str, Any]) -> str | None`;
  `measure(plan: list[Case], generator: ImageGenerator, *, max_usd: Decimal, out_dir: Path) -> list[dict]`
  (gerador injetável, fake nos testes).
- **Card** (só o trecho novo; taxas iguais às de `image_rate_card_2026-11-13.json:8-10`):
  ```json
  "model": "gpt-image-2-2026-04-21",
  "extra_models": ["gpt-image-2.6-sunburst", "gpt-image-2.6-flare"],
  "derivation": "... same Standard image/text rates for gpt-image-2.6-sunburst, gpt-image-2.6-flare and gpt-image-2 ... no dated snapshot for 2.6 ... gpt-image-2 shutdown 2027-02-10"
  ```
- **Profile depois da Etapa 2** (exemplo com Sunburst):
  `"profile_version": "valoria-gpt-image26-sunburst-v1"`, `"model": "gpt-image-2.6-sunburst"`,
  `"portrait": {"size": "1024x1536", "quality": "medium", "complexity": "high"}` (idem `epic_scene` e `creature_portrait`).
- **`medicao.json`:** `{"spent_usd": "…", "max_usd": "2.00", "stopped": null|"motivo", "calls": [{…R8…}]}`.

### Concorrência

N/A: sem thread, async, cancelamento, retry ou lock novos. Timeout e lease seguem iguais (R16 da SPEC-326).

## 4. Plano passo a passo

### Etapa 0 — Suporte inerte, card e script (offline; pode pousar com a renovação de dezembro)

1. **Testes primeiro:**
   - `tests/test_openai_images.py`: `test_envia_complexity_quando_brief_tem` (JSON e form);
     `test_sem_complexity_nao_envia_campo` (I1); `test_idempotency_key_muda_com_complexity`.
   - `tests/test_dynamic_art_brief.py`: `test_builders_gravam_complexity_do_formato`;
     `test_complexity_for_ignora_profile` (R5); `test_profile_complexity_so_em_2_6` (R6).
   - `tests/test_image_pricing.py`: `test_card_prices_extra_models` (falha hoje); `test_modelo_desconhecido_segue_indisponivel`.
   - `tests/test_pricing_card_files.py`: o card novo tem as mesmas taxas, `extra_models` exato e `derivation` com as
     datas; gate R2.
   - `tests/test_image_model_measure.py` (gerador fake): para antes de passar do teto; para com
     `cost_basis != rate_card`; para com custo > 0,25; recusa `--max-usd > 2`; sem `--confirm-spend`, nenhuma chamada;
     o JSON não tem bytes nem prompt.
2. **Implementação:** R1, R3–R9. O card novo só existe na renovação (`observed_at` = dia da leitura da página, que o
   coordenador relê). Se a Etapa 0 não estiver pronta antes de 03/12, a renovação de dezembro sai sozinha, com o
   mesmo modelo, e `extra_models` entra no card seguinte. A Etapa 0 nunca segura a renovação (D7).
**Desvio registrado (22/11, coordenador):** a Etapa 0 entrega só o **suporte de código** a `extra_models`
   (R1: `priced_models()`, `require_image_prices`, `price_image_event`), provado com card de teste por monkeypatch;
   o card atual segue sem `extra_models` (ausente = lista vazia). **Não** há arquivo de card novo nem mudança do
   caminho em `image_pricing.py:16`: o card com `extra_models` nasce na renovação de dezembro (D7). Fica para a
   renovação: R3 e o teste "card novo tem as mesmas taxas, `extra_models` exato e `derivation` com as datas". O gate
   de R2 já vale (`tests/test_pricing_card_files.py`) para qualquer card presente. `--canary` (R15) entrou no
   script; a comparação com `medicao.json` só roda de fato depois da Etapa 1.
3. **Verificação:** os arquivos de teste acima, mais `tests/test_rate_card_freshness.py` e
   `tests/test_bug_finops_wallet_jobs.py`, todos com `-n 2`.

### Etapa 1 — Medição real (dono ou coordenador com a chave; teto US$ 2,00)

Matriz em ordem de prioridade: se o teto cortar, os itens do fim ficam de fora. `quality: medium` em tudo.

1. Para cada variante (Sunburst, depois Flare), com `complexity: high`:
   retrato Elfo e retrato Vrel (com refs canônicas), NPC Kahen Cinzéu, épico em Brekmar (1536x1024) com o retrato
   aprovado do Elfo, e repetição do Elfo como identidade. São 10 imagens.
2. Com `complexity: medium`: retrato Elfo e épico, nas duas variantes. São 4 imagens.
3. Base com `gpt-image-2-2026-04-21`, sem `complexity`: retrato Elfo e épico. São 2 imagens (comparam tokens).
4. **Critério de escolha** (D1):
   - Uma variante é elegível se passa na barra da SPEC-326 §6 (≥ 4 em estética, lore e raça; identidade ≥ 4; zero
     texto, anacronismo e franquia; o guard dHash sem falso positivo). Precisa ainda de latência máxima ≤ 240 s e
     de todos os `cost_basis` iguais a `rate_card`.
   - Entre as elegíveis, ganha a maior média de estética.
   - Empate (diferença ≤ 0,25): ganha o menor custo mediano. Novo empate: a menor latência mediana.
   - `complexity: medium` só substitui `high` se passa na barra e custa ≥ 15 % menos (D2).
   - O Opus pontua a ficha de contato, que fica no diretório de saída e não vai para o repo; o dono escolhe.
5. **Saída:** `docs/spec425/medicao.json`, `docs/spec425/escolha.md` (rubrica, recomendação, teto por R10) e a
   decisão do dono registrada no §8.

### Etapa 2 — Troca de dados (depois da escolha; meta: pousar até 15/01/2027)

1. **Testes primeiro:** `test_quote_modelo_antigo_cobra_apos_troca` (I2); `test_profile_e_price_profile_mesmo_modelo`
   (I4); o teste de `routes/art.py` sem literal (R14); os literais de `profile_version` em
   `tests/test_dynamic_art_brief.py:110,113` e `tests/test_image_quotes.py:95,102` atualizados;
   `tests/test_publish_image_profiles.py` (plano, `--dry-run` sem conexão, problemas detectados).
2. **Implementação:** R10–R14 e R15 no runbook; `IMAGE_COST_USD` medido.
3. **Verificação:** os arquivos de teste da arte e do pricing com `-n 2`. A suíte completa fica para o coordenador, no pouso.

### Etapa 3 — Staging (coordenador ou dono; escrita no staging)

1. `publish_image_profiles.py --dry-run`, depois `--confirm-staging <ref>`, com o teto de R10.
2. `vercel_env.py` com os ids novos. A env só vale no deploy seguinte, então os passos 2 e 3 trocam juntos.
3. Pré-condição do `budget.md:78-82`: conferir reservas e jobs abertos. Pela I2 eles sobrevivem, mas o número fica
   registrado. Depois, deploy.
4. Smoke §6.

## 5. Critérios de aceite

- [ ] R1–R15 cobertos pelos testes citados; I1–I5 verdes.
- [ ] `docs/spec425/medicao.json` com o gasto total ≤ US$ 2,00 e todos os `cost_basis` iguais a `rate_card`.
- [ ] A escolha da variante e da complexity registrada pelo dono (§8) e o teto por R10 (ou aprovado no D3).
- [ ] Runbook com o canário (R15) e a reversão (R13), incluindo os ids dos profiles do modelo antigo e o `expires_at`.
- [ ] `ruff check` limpo; `tests/test_size_budget.py` verde; suíte completa verde no pouso.
- [ ] Sem `with_structured_output` novo (não há LLM de texto).

## 6. Smoke test real (staging, depois do deploy; teto US$ 0,50)

1. `scripts/staging/art_preflight.py` com `ok: true`.
2. `POST /game/{id}/art/quote` de retrato: 200, com `credits_milli` coerente com o teto novo.
3. Confirmar e gerar 1 retrato: `ready`, `usage` com `cost_basis = rate_card`, custo ≤ `max_provider_usd`,
   `financial_anomaly_milli = 0`, `model` = a variante escolhida.
4. Gerar 1 épico com o retrato aprovado como identidade. Mesma checagem, mais a rubrica ≥ 4.
5. `POST /internal/cron/finops` com 200 e sem `stale_rate_card`.

## Não rodou e por quê

- Ainda nada: a spec está em `draft`. Previsto: a Etapa 1 e o §6 dependem da chave e do gasto do dono e da escrita no
  staging, que hoje também bloqueia a SPEC-409. Os testes `*_local.py` precisam de Postgres, que não existe nesta
  máquina (D-36); o executor diz no hand-back se o CI os cobre.

## 7. Riscos & compatibilidade

- **Desligamento com job em voo:** depois de 10/02, o modelo antigo responde erro (qual, a fonte não diz,
  `fontes.md:17`). Um job já despachado vira `uncertain` e precisa de reconciliação manual
  (`services/image_quotes.py:425-432`). Por isso a meta é 15/01, e a reversão só vale até 03/02/2027.
- **Deriva:** o mesmo id pode mudar de comportamento sem aviso. O canário mensal e o contador de anomalia (R15)
  detectam isso; sem snapshot datada, não há como pinar.
- **Limite por minuto desconhecido** para os 2.6 (`fontes.md:104`): a Etapa 1 registra os 429. O uso no staging é baixo.
- **Formato do `usage`:** se o 2.6 devolver um formato que `safe_provider_usage` ou `price_image_event` não aceitam
  (`services/usage_metering.py:126-140`), o custo deixa de ser exato. R9 para a medição antes da troca.
- **Saves:** não mudam. O ledger de arte e as cotações antigas ficam intactos (as tabelas são imutáveis); a chave de
  dedupe inclui `profile_version` (`supabase/migrations/20260819002404_blob_assets_chronicle.sql:83`), então um gatilho
  novo gera com o modelo novo sem colidir.
- **MockLLM/FallbackLLM:** não se aplicam. Os testes usam o gerador fake e o `httpx` monkeypatchado.

## 8. Decisões do dono

| # | Decisão | Recomendação |
|---|---|---|
| D1 | Sunburst ou Flare | Aplicar o critério da Etapa 1 e escolher olhando a ficha de contato; a aposta inicial é Sunburst ("detailed visual work"), salvo se não for elegível |
| D2 | `complexity` explícita | Enviar sempre. `high` (o padrão da API, deixado explícito contra deriva), salvo se `medium` passar na barra custando ≥ 15 % menos |
| D3 | Teto por imagem | Regra R10 (×1,5, piso 0,08). Acima de 0,12 a imagem fica mais cara para o jogador: aprovar o valor medido ou rever a qualidade |
| D4 | Card com `extra_models` até 10/02 | Sim: cotações antigas sobrevivem à troca (I2) e a reversão fica só nos dados |
| D5 | Reversão | Commit de dados, env e deploy (R13). Sem uma flag `RPG_*` nova de override de modelo, porque a env da Vercel também exige deploy |
| D6 | `safety_identifier` | Fora desta spec. Hoje nada é enviado; avaliar numa spec de privacidade (o id precisa ser hash do owner) |
| D7 | Ordem com o rate card | A renovação de dezembro sai antes de 03/12, com ou sem a Etapa 0, e nunca espera por ela. A troca (Etapas 1–3) vem depois, até 15/01/2027 |
| D8 | Gasto e quem roda a Etapa 1 | Até US$ 2,00, com a chave do dono (a mesma do smoke da SPEC-326). Se a OpenAI exigir a Organization Verification, isso é ação do dono |
| D9 | Imagens antigas e retratos de criatura já gerados | Não regenerar; arte antiga e nova convivem. Se o dono vir diferença incômoda, abre-se uma spec de regeneração |
