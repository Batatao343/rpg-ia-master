# SPEC-326 — Arte dinâmica consistente com Valoria (estética, lore e raça)

> **Status:** `in-progress` (aprovada 26/10, D1–D7 nos padrões recomendados; código + testes offline prontos; falta revisão independente e o §6 real)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** pipeline de arte dinâmica já na `main` (`services/art_brief.py`, `workers/dynamic_art_jobs.py`, `infrastructure/openai_images.py`, cotação de imagem)
> **Desbloqueia:** `RPG_DYNAMIC_ART_ENABLED=1` no staging (só depois do §6 aprovado)

---

## 1. Contexto & Objetivo

O dono pediu (25/10) que a arte dinâmica "fique bem parecida com a de Valoria, respeitando estética,
lore e racialidade". Testamos o caminho real de produção: brief → `render_image_prompt` → GPT Image 2
pinado. Foram 7 imagens mais 3 sondas, US$ 0,21 medidos (≤ US$ 0,24 com uma chamada que estourou o
timeout). O relatório com as notas por imagem ficou no scratchpad da sessão de 25/10 (`art_test/art_report.md`).

**Resultado de produção.** As imagens saem limpas (sem texto, marca d'água, gore nem semelhança com
The Witcher), mas genéricas:
- o estilo é render digital "pictórico", enquanto o pacote canônico (`web/public/art/v1/**`) é
  **gravura com hachura fina densa e paleta úmbar/ferrugem/ocre/violeta**;
- **Anão da Fuligem, Vrel, Osshari e o NPC Kahen (Cinzéu) saíram humanos** (nota 1/5 em raça);
- raças não humanas de pele escura no lore viraram **humanos negros reais**, um erro de lore e de representação;
- a cena épica não tem local nem chefe;
- a identidade do herói deriva entre gerações, porque a "referência do retrato" nunca é enviada.

**As sondas mostraram que a correção é barata e funciona.** Com estilo de gravura e traços do codex
no texto, o Vrel saiu correto, com raça 5/5. Somando a arte canônica da raça como referência, a
estética chegou a 5/5. Com o retrato aprovado como referência, a identidade chegou a 5/5.
O princípio do projeto se mantém: a IA só renderiza, e o brief continua determinístico e montado em Python.

### Causas-raiz (verificadas no source em 25/10)

| # | Causa | Onde |
|---|---|---|
| C1 | O estilo global pede "painterly realism" e "cinematic chiaroscuro", sem técnica, paleta nomeada nem composição de cena | `data/dynamic_art_profiles.json:9-14` |
| C2 | `race_anchors` só tem as chaves `Humano`/`Elfo`/`Anão`, mas o player guarda o **nome exibido** ("Anão da Fuligem", "Vrel", "Cinzéu", "Osshari"). Resultado: 4 de 6 raças sem âncora, e o `.get(race)` devolve `None` em silêncio | `data/dynamic_art_profiles.json:28-32`; `services/art_brief.py:50`; `web/src/components/CreateScreen.tsx:233` |
| C3 | O prompt nunca nomeia a raça nem a classe | `services/art_brief.py:45-58`, `:126-136` |
| C4 | `reference_asset_ids` só entra no `anchor_hash`, e o worker chama o provider com refs `()`. O ramo `/images/edits` nunca roda | `services/art_brief.py:76,121`; `services/dynamic_art.py:45`; `workers/dynamic_art_jobs.py:35`; `infrastructure/openai_images.py:80` |
| C5 | O brief de NPC usa só `role` e `persona`, e ignora `appearance` e `race_id` | `services/art_brief.py:96-105`; `agents/npc.py:137,139` |
| C6 | O épico recebe `conflict_summary or {"detail": ...}`, mas o resumo **não tem `detail`**. O assunto vira sempre "momento épico" ou "Confronto decisivo", e local e chefe são ignorados | `api.py:4330-4333`; `services/art_brief.py:119`; `services/conflict_summary.py` (`build_summary`) |
| C7 | A linha `region:` sai sempre vazia: o player tem `origin_region_id`, não `region` | `services/art_brief.py:52`; `api.py` (`_create_game`) |
| C8 | Sem negativos de época (sobrecasaca, tricórnio, arma de fogo), de máscara no rosto, de fotorrealismo nem de semelhança com franquias | `services/art_brief.py:72-75` |
| C9 | `quality` não é enviada (`auto`): a saída variou de 158 a 601 tokens no mesmo tamanho, e com isso o detalhe e o custo ficam imprevisíveis | `infrastructure/openai_images.py:88,96` |
| C10 | O timeout padrão é 120 s, mas uma chamada real passou de 300 s | `infrastructure/openai_images.py:34`; `workers/run_worker.py:87` |

## 2. Requisitos

**Estilo**
- **R1** — `global_style` vira o estilo da casa, em gravura. Texto validado na sonda:
  - "intricate etched illustration, dense fine-line crosshatching and stippled ink texture under muted wash colour, like a hand-engraved plate";
  - "palette of umber, rust, ochre, soot black, bruised violet and tarnished teal; low warm lantern light; no glossy digital render, no photorealism";
  - "full figure embedded in a lived-in Valorian environment that tells a small story";
  - "dark medieval material culture: hand-forged iron, leather, wool, rope, brass and copper".

  O `profile_version` passa a `valoria-gpt-image2-v2`.
- **R2** — Ofertas pendentes (`state["art_offers"]`) com `brief.profile_version` diferente do atual
  são **reconstruídas** no `/art/quote` a partir do estado (D7). Nunca se cota um brief v1 com o profile v2.

**Raça e representação**
- **R3** — Os descritores de raça ficam em `race_descriptors`, **indexados por `race_id`**, e cobrem
  todos os ids de `services/reputation.VALID_RACES`. A resolução usa `resolve_race_id`, que aceita
  id ou nome exibido. Cada descritor tem `name`, `positive` (traços do codex) e `negative`. O texto
  é curado a partir de `data/codex/races/<id>.md` § aparência, e só entra traço `visibility: public`.
- **R4** — O prompt contém sempre `RACE: <nome> — <positive>` e `CLASS: <nome> — <class anchor>`.
  Raça não resolvida usa um descritor neutro **explícito** ("Valorian person, race unspecified")
  e emite o log `art.race_unresolved`. Nunca omitir em silêncio.
- **R5** — Representação respeitosa:
  - **Raças não humanas** (elfos, anões da fuligem, vrel, cinzéus, osshari) levam no `negative`
    "not a human". As de pele escura no lore (cinzéus; osshari e vrel quando escuros) levam também
    "skin is the non-human tone of this Valorian race, not a real-world human ethnicity".
    Os traços não humanos obrigatórios (íris branca, quitina, escamas etc.) precisam aparecer no `positive`.
  - **Humanos** mantêm a diversidade real: nenhuma etnia padrão; a aparência declarada governa; a
    região influencia vestuário e materiais, não a etnia.
  - Nada de caricatura nem traços étnicos exagerados (negativo global).
- **R6** — A aparência declarada pelo jogador complementa o descritor da raça e não o substitui.
  O descritor vem antes no prompt.

**NPC e cena**
- **R7** — O brief de NPC inclui `appearance` (sanitizada, ≤ 500 caracteres) e o descritor da raça
  por `race_id`. Se `appearance` vier vazia e houver `entity_id` canônico, usa-se o trecho público
  "Aparência:" do codex. Fica mantida a exclusão de traços secretos ou não revelados.
- **R8** — O brief épico tem:
  - como assunto, o nome e o tipo do chefe (inimigo `type` boss/chefe que disparou o gatilho);
  - o local, com `world.current_location` mais um descritor curto curado por região (os 12 ids de
    `origins.json.regions`);
  - a raça e a classe do herói.

  O fallback de `api.py:4332` deixa de depender de `detail` (corrige C6).
- **R9** — A linha `region:` traz o nome resolvido de `origin_region_id` e é **omitida** quando vier vazia.

**Referências (worker)**
- **R10** — O worker resolve `reference_asset_ids` em bytes PNG (no máximo 2 por geração) e as passa em
  `ImageGenerationInput.reference_payloads`, ativando `/images/edits`. Os tipos são:
  - `race:<race_id>`: display canônico da raça (`data/visual_assets.json`), em retrato de player e de NPC (D1);
  - `location:<id>`: `visual_catalog.location_visual`, exata ou regional, no épico;
  - `player:approved_portrait`: variante `full` da última geração `player` com `status='ready'`
    (aprovada), lida do BlobStore, no épico e na reformulação.
- **R11** — O prompt leva um preâmbulo para cada tipo de referência:
  - para arte canônica: "match technique, palette and racial anatomy; create a NEW individual and a NEW scene";
  - para o retrato do herói: "SAME person: identical face, age, hair, scars, outfit; change only pose and background".
- **R12** — **Guard anti-cópia:** depois de gerar, calcula-se o dHash (Pillow, 64 bits) da saída contra
  cada referência **canônica**. Se a distância de Hamming ficar abaixo do limiar do profile (inicial 10,
  calibrado no §6), grava-se `similar_to_canon=true` no resultado e emite-se o log `art.canon_similarity`.
  A ação segue a D4. O retrato do próprio herói **não** entra nessa checagem.
- **R13** — Referência ausente ou ilegível não derruba o job: ele segue só com texto e emite
  `art.reference_missing`, com o tipo e sem o conteúdo.

**Negativos, provider e custo**
- **R14** — Exclusões globais:
  - "no firearms, tricorn hats, frock coats or modern tailoring";
  - "face not hidden by a mask in portraits";
  - "no photorealism";
  - "original character, no likeness to The Witcher, Warhammer, Lord of the Rings or Elden Ring characters";
  - "no caricature";
  - "no text, logo, watermark, graphic gore or sexualized presentation".
- **R15** — `quality` é fixada no profile (`formats.*.quality`, D3) e enviada pelo adapter nas duas rotas,
  generations e edits.
- **R16** — O timeout do provider no worker fica em **≥ 300 s**. A lease e o heartbeat do job cobrem
  a chamada inteira.
- **R17** — O `max_provider_usd` do price profile de imagem (por ambiente) precisa cobrir o pior caso
  com 2 referências mais a qualidade escolhida. O coordenador confere no staging antes do §6.

### Fora de escopo

- Descritores para raças só de NPC/lore (Hospedeiros de Xylos, Povo-recife, Lycans, Vampiros). Elas
  não estão em `VALID_RACES`, então NPCs dessas raças caem no descritor neutro.
- Gerar ou reimportar arte canônica; trocar de modelo ou provider; UI nova de revisão; LLM-judge automático.
- Alterar a cotação comercial, além de garantir que o teto cubra o novo custo (R17).

## 3. Design técnico

**Arquivos alterados**
- `data/dynamic_art_profiles.json`: `profile_version` v2; novo `global_style` (R1);
  `race_descriptors{race_id: {name, positive, negative}}` (R3/R5); `region_descriptors{region_id: str}`
  (R8/R9); `global_exclusions[]` (R14); `formats.portrait|epic_scene.quality` (R15);
  `reference_preambles{canon, identity}` (R11); `canon_similarity_min_hamming: 10` (R12).
  O bloco `race_anchors` antigo é removido.
- `services/art_brief.py`:
  - `ArtBrief` ganha `race_line: str`, `class_line: str` e `scene: str`;
  - `reference_asset_ids` usa ids canônicos (`race:race_vrel`, `location:brekmar`, `player:approved_portrait`);
  - `build_player_art_brief` resolve a raça e a região;
  - `build_npc_art_brief` usa `appearance` e `race_id`;
  - `build_epic_art_brief(state, trigger, *, pose_id)` lê o chefe e o local do estado;
  - `render_image_prompt` emite as linhas `RACE:`/`CLASS:`/`SCENE:`, os preâmbulos e as exclusões globais.
- `api.py` (~4320–4333): `_enqueue_turn_art` passa o estado ao novo épico, sem `conflict_summary`.
  O `create_image_quote` reconstrói o brief de ofertas com outra versão (R2).
- `workers/dynamic_art_jobs.py`: novo `resolve_reference_payloads(brief, *, blob_store, generation, catalog) -> tuple[bytes, ...]`
  (R10/R13); dHash pós-geração (R12) gravado em `result["canon_similarity"]`.
- `infrastructure/openai_images.py`: aceita `quality` via `ImageGenerationInput` (novo campo
  `quality: str | None = None` em `infrastructure/ports.py`) e o envia em generations e edits.
- `workers/run_worker.py:87`: `OpenAIImageGenerator(..., timeout=300.0)` (R16).

**Arquivos novos**
- `services/art_similarity.py`: `dhash64(png: bytes) -> int` e `hamming(a: int, b: int) -> int` (só Pillow).

**Exemplo** (`race_descriptors`, curado do codex):
```json
"race_cinzeus": {
  "name": "Cinzéu",
  "positive": "ash-grey to near-black hairless skin with no warm undertones, WHITE irises, three fingers per hand, hairless bony-tipped tail, black-and-white tattoos, piercings and decorative chains set into the back",
  "negative": "not a human; skin is the non-human tone of this Valorian race, not a real-world human ethnicity"
}
```

## 4. Plano passo a passo

Os testes são todos offline: `FakeImageGenerator` registra o `ImageGenerationInput`. Nenhuma chamada paga.

### Etapa 1 — Profile e brief do player (R1, R3–R6, R9, R14)
1. **Testes** (`tests/test_dynamic_art_brief.py`, novos casos):
   - `test_toda_raca_jogavel_tem_descritor`: todo `VALID_RACES` tem `race_descriptors`.
   - `test_raca_por_nome_exibido_resolve` (parametrizado nas 6 raças): o nome exibido produz o
     `positive` da raça no prompt e a linha `RACE: <nome>`.
   - `test_nao_humanos_tem_not_a_human` e `test_cinzeu_tem_guarda_etnia`.
   - `test_humano_sem_etnia_padrao`: o descritor de `race_humanos` não contém termos de etnia ou tom de pele.
   - `test_raca_desconhecida_neutro_e_log`.
   - `test_estilo_gravura_e_versao_v2`.
   - `test_linha_regiao_resolvida_ou_omitida`.
   - `test_exclusoes_globais_presentes`.
   - `test_aparencia_vem_depois_do_descritor`.
2. **Implementação:** profile e `art_brief.py`.

### Etapa 2 — NPC e épico (R7, R8, R2)
1. **Testes:**
   - `test_npc_brief_usa_aparencia_e_raca` (Kahen, `race_cinzeus`);
   - `test_npc_sem_aparencia_usa_codex_publico`;
   - `test_npc_nao_vaza_traco_secreto`;
   - `test_epico_tem_chefe_local_e_raca_do_heroi` (Brekmar, boss);
   - `test_epico_sem_detail_nao_vira_generico`;
   - `test_oferta_v1_e_reconstruida_no_quote` (`tests/test_image_quotes.py`).
2. **Implementação:** `art_brief.py` e `api.py`.

### Etapa 3 — Referências, anti-cópia, quality e timeout (R10–R13, R15, R16)
1. **Testes** (`tests/test_dynamic_art_jobs.py`):
   - `test_worker_envia_ref_da_raca_no_retrato`;
   - `test_epico_envia_retrato_aprovado_e_local`, que ignora gerações `rejected_quality`;
   - `test_max_duas_refs`;
   - `test_ref_ausente_segue_texto_e_loga`;
   - `test_preambulo_por_tipo_de_ref`;
   - `test_similaridade_canonica_sinaliza` (imagem idêntica → `similar_to_canon=true`; diferente → false);
   - `test_retrato_proprio_fora_do_guard`.

   Em `tests/test_openai_images.py` (arquivo novo, httpx mockado): `test_quality_enviada_generations_e_edits`;
   `test_timeout_worker_300`.
2. **Implementação:** worker, adapter, `art_similarity.py`, `run_worker.py`.
3. **Verificação:** testes do escopo (`-n 2`), e a suíte completa 1× no pouso.

## 5. Critérios de aceite

- [x] R1–R16 cobertos pelos testes acima (R17 = conferência do coordenador no staging antes do §6).
- [x] Prompt renderizado das raças anexado em `handoffs/SPEC-326-prompts.md` (sem chamada paga).
- [ ] §6 executado, com todas as notas acima da barra e a ficha de contato revisada pelo dono (D2).
- [ ] `uv run pytest` verde (suíte completa offline).
- [x] Ofertas v1 são reconstruídas sem erro (R2, `test_oferta_v1_e_reconstruida_no_quote`); briefs v1 já gravados renderizam com descritor neutro.
- [x] Nenhum `with_structured_output` novo (a spec não usa LLM de texto).

## 6. Smoke test real (obrigatório antes de `RPG_DYNAMIC_ART_ENABLED=1` no staging)

**Teto: US$ 0,60.** Ledger por chamada a partir de `usage` com o rate card do repo; parar ao atingir
o teto. A execução é local, pelo **mesmo** caminho de produção (brief → worker com refs → adapter).
As saídas vão para o scratchpad, nunca para o repo nem para upload.

**Matriz** (8 imagens, ≈ US$ 0,05 cada com refs):
1. Retratos de herói: Elfo (com aparência declarada), Anão da Fuligem, Vrel, Osshari e Humano (sem aparência).
2. NPC Kahen (Cinzéu, formato `NPCSchema`).
3. Épico em Brekmar com chefe, usando o retrato aprovado do Elfo.
4. Reformulação ou repetição do Elfo com o retrato aprovado (identidade).

**Rubrica** (1–5, comparando com `web/public/art/v1/**` e o codex):

| eixo | 5 | 3 | 1 |
|---|---|---|---|
| Estética | gravura e hachura com a paleta canônica, indistinguível do pacote | dark fantasy coerente, render liso | estilo alheio |
| Lore | material, época, local e classe corretos | genérico mas plausível | anacronismo ou local errado |
| Raça | todos os traços obrigatórios do codex visíveis | parte dos traços | humano ou raça ilegível |
| Identidade (só na repetição) | mesmo rosto, idade, cicatriz e roupa | mesmo arquétipo | outra pessoa |

**Barra de aprovação:**
- todas as imagens **≥ 4** em estética, lore e raça, e a repetição **≥ 4** em identidade;
- **zero** texto ou marca d'água, zero anacronismo, zero semelhança com franquia;
- **zero** raça não humana retratada como humano ou etnia humana real;
- o guard R12 sem falso positivo na matriz, com o limiar ajustado se preciso e registrado no profile.

Ficha de contato e notas no handoff `handoffs/SPEC-326-smoke.md`; o dono vê a ficha (D2).

## 7. Riscos & compatibilidade

- **Cópia da arte canônica:** usar a ilustração da raça como referência pode clonar o indivíduo
  canônico. Mitigação: preâmbulo "NEW individual", guard dHash (R12) e revisão das primeiras gerações (D2).
- **Custo:** com refs e `quality` fixa, a imagem passa de ≈ US$ 0,01–0,02 para ≈ US$ 0,05–0,06.
  A cotação precisa cobrir isso (R17); o dono decide o tier (D3).
- **Latência:** `/images/edits` ficou em dezenas de segundos a mais de 300 s. O job é assíncrono e a
  UI já mostra placeholder; o timeout e a lease ficam alinhados (R16).
- **Assets em runtime:** os webp canônicos vivem em `web/public/art/v1`. Se o pacote do worker não os
  incluir, R13 cai para só texto, e o §6 deve rodar no mesmo empacotamento do worker de staging.
- **Saves:** o bump de `profile_version` não quebra o dedupe (a chave inclui a versão); ofertas v1 são reconstruídas (R2).
- **MockLLM/FallbackLLM:** não se aplicam, pois não há LLM de texto. Os testes usam o gerador fake.

## 8. Decisões do dono (defaults recomendados em negrito)

- **D1 — Arte canônica como referência de estilo:** **ligada para retrato de herói e de NPC (ref da
  raça) e para o épico (ref do local), com o guard anti-cópia.** Alternativa: desligada, só texto.
  É mais barato (≈ US$ 0,02) e chegou a raça 5 e estética 4 na sonda, mas fica abaixo da barra.
- **D2 — Revisão humana:** **o dono vê a ficha do §6, e o coordenador revisa as 10 primeiras gerações
  reais no staging antes de considerar a feature estável.** Alternativa: sem revisão.
- **D3 — Qualidade vs custo:** **`medium`** (≈ US$ 0,05–0,06 com refs). Alternativas: `low` (mais
  barato, perde a hachura fina), `high` (≈ 4× o custo) ou `auto` (imprevisível, e é o estado atual).
- **D4 — Gatilho do guard anti-cópia:** **sinalizar e logar, sem rejeitar automaticamente** (a
  geração já foi paga; o jogador pode reprovar pela UI existente). Alternativa: rejeitar e reembolsar automaticamente.
- **D5 — Humanos:** **sem etnia padrão; etnia só pela aparência declarada; região define vestuário e
  materiais.** Alternativa: descritor étnico por região. Não recomendado, porque reforça estereótipo.
- **D6 — Raças só de NPC (Hospedeiros, Povo-recife, Lycans, Vampiros):** **fora desta spec, com descritor neutro.**
  Alternativa: incluir já, curando mais 4 descritores.
- **D7 — Ofertas antigas (v1) após o bump:** **reconstruir o brief no `/art/quote`.** Alternativa: expirar as ofertas.

## Histórico de mudanças

- **26/10 — implementação.** Desvios da spec, todos de forma:
  - **Assets em runtime (R10/R13):** `web/public/**` é excluído do bundle da Vercel, então o worker lê um conjunto
    curado em `data/art_refs/{race,location}/<id>.webp` (6 raças + 12 locais de região, ~5 MB), sem fallback para
    `web/public`. Local interior sem arte própria cai no fallback regional do catálogo e, por fim, na região
    (`region_id_of`). `test_ref_de_raca_vive_no_pacote_do_worker` trava o layout contra o `vercel.json`.
  - `resolve_reference_payloads` devolve `(ids carregados, bytes PNG)` e recebe `approved_portrait_key`
    (callback do repositório: `DynamicArtRepository.approved_portrait_key`, último retrato `status='ready'`).
  - O preâmbulo só aparece para referências efetivamente anexadas: `render_image_prompt(brief, used)`.
  - Preâmbulo extra `canon_location` (R11) para arte de local, porque "NEW individual" contradiria o
    retrato do herói no épico.
  - `build_epic_art_brief(state, event=None, ...)`: o chefe é relido de `state["enemies"]` (mesmo critério do gatilho).
  - Resultado do worker ganha `similar_to_canon` e `canon_min_hamming` (D4: só sinaliza e loga).
  - `_offer_brief_for_quote` em `api.py` isola a reconstrução da oferta v1 (R2) para teste offline.
  - Chave de idempotência do adapter agora inclui `quality` e o hash das referências.
  - Logs novos: `art.race_unresolved`, `art.reference_missing`, `art.canon_similarity`, `art.canon_similarity_failed`.
