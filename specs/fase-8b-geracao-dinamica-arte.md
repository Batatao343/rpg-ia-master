# SPEC — Fase 8B: geração dinâmica e rara de arte

> **Status:** `done` (2026-08-20 — pipeline/fake/local completos; geração paga opt-in)
> **Criada:** 2026-08-17 · **Atualizada:** 2026-08-19
> **Depende de:** `fase-8-ancoras-visuais-contextuais` (`done`) ·
> `fase-10b-fundacao-local-portas-adapters`,
> `fase-10b-turnos-duraveis-concorrencia-fila` e
> `fase-10b-storage-assets-portavel` (`done`)
> · hosted também depende de `fase-10b-auth-rls-isolamento`
> **Desbloqueia:** identidade visual personalizada, retratos persistentes de NPCs
> emergentes e ilustrações de momentos culminantes
> **Aceite local:** concluído com provider fake. O smoke pago de GPT Image da §6
> permanece opt-in e só roda com teto de gasto autorizado.

---

## 1. Contexto & Objetivo

A Fase 8A integrou 45 âncoras curadas e 90 derivados WebP para raças, classes,
locais e NPCs, com identidade canônica, primeira aparição, fallback e
idempotência resolvidos em Python. Ela deliberadamente não gera nada em runtime.
Esta fase acrescenta geração dinâmica somente onde a personalização ou a
singularidade narrativa justifica custo: retrato do personagem, NPC persistente
sem arte e uma cena épica por arco narrativo.

O jogador escolhe raça e classe, descreve a aparência e revisa um brief adaptado
às regras estéticas de Valoria. Python combina entrada, âncoras e contexto
canônico; o modelo de imagem cria os pixels, mas nunca decide identidade, gatilho,
orçamento, nome de arquivo ou fato do mundo. Geração é assíncrona, privada,
durável e idempotente: o turno nunca espera pela imagem e nenhum retry cria custo
duplicado silencioso.

O provider inicial é OpenAI, usando o snapshot mais recente do GPT Image 2
validado no início da implementação. Em 2026-08-17 a referência é
`gpt-image-2-2026-04-21`; upgrades são explícitos e versionam o perfil visual, em
vez de seguir um alias móvel sem revisão estética.

## 2. Requisitos

### Gatilhos e raridade

- **R1 — Gatilhos fechados:** apenas três eventos geram jobs:
  `player_portrait_confirmed`, `npc_first_appearance_without_art` e
  `arc_epic_moment`. Menção em prosa, viagem comum, combate normal, item, monstro,
  multidão, figurante, escolha de subclasse ou clique repetido não gera imagem.
- **R2 — Retrato do jogador:** existe no máximo um retrato aprovado por
  personagem, mais uma reformulação manual autorizada. Falha técnica pode repetir
  o mesmo job até três tentativas, sem consumir a reformulação e sem criar novo
  registro lógico.
- **R3 — NPC elegível:** só NPC nomeado, conhecido, `in_scene`, persistido no
  estado e sem arte curada/dinâmica pronta entra na fila. NPC citado somente pela
  LLM, figurante sem identidade ou entidade secreta ainda não revelada fica com
  silhueta/monograma da 8A.
- **R4 — Orçamento por arco, nunca por campanha:** cada instância de arco possui
  até **4 retratos de NPC**, com cooldown de 15 turnos entre enqueues, e **1 cena
  épica**. Não existe teto acumulado de campanha e saldo não transfere entre
  arcos. O retrato do jogador e sua única reformulação ficam fora do orçamento de
  arco.
- **R5 — Arco estável:** orçamento usa `arc_instance_id`/sequência criada por
  Python quando um arco abre; `arc_title` não é chave porque pode repetir ou ser
  reescrito pela LLM. Retry, restore e replan preservam ou restauram o ledger
  correspondente à linha do tempo.
- **R6 — Épico único:** o primeiro boss significativo do arco, identificado por
  categoria mecânica `boss` e nova instância de conflito, reserva a arte épica.
  Se nenhum boss a consumir, a conclusão aplicada do arco reserva a imagem. Boss
  e conclusão nunca geram duas artes no mesmo arco.
- **R7 — Sem bloqueio:** criação, turno, SSE, restore e conclusão do arco
  prosseguem com placeholder e status `pending|generating`. Falha, recusa ou
  timeout mantém fallback honesto; jamais vira 500 do jogo.

### Criação e fidelidade estética

- **R8 — Entrada separada:** onboarding coleta `appearance` em campo livre e
  opcional `visual_exclusions`, além de nome, raça, classe, Virtudes e backstory.
  Aparência não é misturada à história e não altera mecânica. Como a subclasse é
  escolhida explicitamente apenas no nível 3, o primeiro retrato usa raça e
  classe-base e não antecipa ramo futuro.
- **R9 — Adaptação Python-first:** `build_player_art_brief()` combina descrição
  sanitizada com âncoras curadas da raça, classe, região e estilo global. Não há
  segunda chamada de LLM textual. O jogador revisa o brief final antes de
  confirmar qualquer gasto.
- **R10 — Autoridade do jogador:** características físicas explícitas do jogador
  são preservadas quando compatíveis com segurança; raça/classe adicionam
  materiais, silhueta, símbolos, clima e linguagem visual, mas não trocam gênero,
  tom de pele, idade adulta, cabelo, cicatrizes ou corpo declarados.
- **R11 — Referências visuais:** o provider recebe somente âncoras aprovadas e
  públicas: uma referência de raça, uma de classe e, para cenas épicas, o retrato
  aprovado do jogador mais no máximo uma âncora de local/boss. Assets secretos,
  candidatos rejeitados e prompts do handoff nunca entram.
- **R12 — Anatomia e pose naturais:** todo template de prompt inclui bloco
  obrigatório de composição anatomicamente plausível: centro de gravidade
  coerente, coluna/pescoço naturais, articulações possíveis, membros sem
  duplicação, mãos compatíveis com o enquadramento, pegada correta de armas e
  interação espacial consistente. Cenas evitam contorção extrema, perspectiva
  impossível, foreshortening agressivo e oclusões que façam membros parecerem
  desconectados.
- **R13 — Cenas com o herói:** ao retratar o personagem personalizado, a cena usa
  seu retrato aprovado como referência de identidade e uma pose escolhida de um
  catálogo curado (`defensive_stance`, `grounded_advance`, `ritual_focus`,
  `aftermath_stillness`). Se a subclasse já foi escolhida, seu vocabulário visual
  curado entra no brief como contexto estético textual, sem criar outra referência
  visual nem novo job. A LLM não inventa uma pose livre sem esse envelope.
- **R13A — Subclasse sem cobrança automática:** `subclass_chosen` nunca dispara
  regeneração do retrato. O retrato aprovado permanece válido. Se o jogador ainda
  possui sua única reformulação manual, pode solicitá-la depois do nível 3 e o
  novo brief incorpora a subclasse; isso consome a mesma reformulação já prevista
  em R2, não uma franquia adicional.
- **R14 — Revisão de qualidade:** checklist humano do smoke avalia identidade,
  mãos, membros, pegada, postura, silhueta e coerência com raça/classe. Não se faz
  regeneração automática por um classificador subjetivo; uma imagem com defeito
  fica `rejected_quality` e exige ação humana explícita, preservando auditoria e
  custo.

### Provider, persistência e segurança

- **R15 — Modelo pinado:** `OPENAI_IMAGE_MODEL` tem default no snapshot aprovado
  durante a implementação. Troca de modelo exige atualizar `generation_profile`
  e executar a matriz visual de regressão; alias `gpt-image-2` pode ser usado só
  em experimento explícito, nunca silenciosamente em produção.
- **R16 — Porta de domínio:** o núcleo depende de `ImageGenerator`, não do SDK da
  OpenAI. `OpenAIImageGenerator` é Python, usa cliente com timeout, valida MIME e
  devolve bytes/metadados; testes usam `FakeImageGenerator` sem rede/custo.
- **R17 — Registro antes da chamada:** `generation_id` e row `pending` são
  persistidos antes de invocar o provider. O registro guarda owner/game/arco,
  sujeito, evento idempotente, modelo, perfil, hashes de prompt/âncoras, status,
  tentativas, uso/custo, timestamps e erro sanitizado.
- **R18 — Idempotência financeira:** chave única
  `(game_id, timeline_epoch, trigger_kind, trigger_instance_id, profile_version)`
  impede duplicata em retry SSE→POST, worker reiniciado, clique duplo, replan ou
  lease expirada. Apenas `failed_retryable` reutiliza a mesma geração lógica.
- **R19 — Storage privado:** original e derivados dinâmicos usam `BlobStore` e o
  namespace privado da 10b.6. API entrega URL curta/assinada escopada ao owner;
  service key nunca chega ao browser. Arte curada da 8A permanece pública e
  imutável.
- **R20 — Pipeline seguro:** bytes passam por decode real, limite de pixels/MIME,
  orientação, remoção de metadata, hash, WebP responsivo e promoção atômica
  `pending_upload→ready`. Base64/URL efêmera do provider nunca é a referência
  persistente do frontend.
- **R21 — Moderação e segredos:** brief é limitado, normalizado e tratado como
  descrição do sujeito, não instrução de sistema. Conteúdo recusado não é
  reformulado automaticamente para burlar política. Dark fantasy pode mostrar
  tensão, ferimentos não gráficos e horror atmosférico, nunca sexualização de
  menor, violência gráfica explícita ou segredo não revelado.
- **R22 — Proveniência exportável:** prompt adaptado, entrada original,
  exclusões, IDs das âncoras, hashes, modelo/snapshot, perfil, custo e decisões de
  aprovação/rejeição pertencem ao export da campanha; apagar campanha agenda
  lifecycle dos blobs e metadados conforme a 10b.6.
- **R23 — Observabilidade e custo:** métricas por tipo/arco registram enqueued,
  cache hit, sucesso, recusa, falha, latência, bytes e custo estimado/real. Prompt,
  aparência e URL assinada são redigidos dos logs. Um kill switch
  `RPG_DYNAMIC_ART_ENABLED=0` desliga novos jobs sem esconder arte pronta.
- **R24 — Resiliência:** indisponibilidade de chave/provider/worker/storage produz
  estado explícito e placeholder. Não há fallback para outro modelo de imagem
  nesta fase, geração determinística falsa nem uso do MockLLM de texto.
- **R25 — UX acessível:** UI mostra brief revisável, confirmação de custo,
  placeholder, progresso não bloqueante, erro/recusa compreensível, alt text
  derivado de metadata segura, dimensões reservadas e reduced motion. Polling só
  existe enquanto há job pendente e para após estado terminal.

### Fora de escopo

- Arte dinâmica de item, criatura comum, Carta ou local cotidiano; retrato próprio
  ou regeneração automática disparada exclusivamente pela subclasse.
- Vídeo, animação, áudio, sprites ou geração por turno.
- Marketplace/compartilhamento público de retratos entre usuários/campanhas.
- Treinar/fine-tunar modelo, LoRA ou classificador próprio de anatomia.
- Gerar imagem síncrona dentro de `/game/new` ou `/game/action`.
- Executar a Fase 10b nesta spec; fila, BlobStore e Auth são dependências.

## 3. Design técnico

### 3.1 Perfil visual e brief

**Novo `data/dynamic_art_profiles.json`:** fonte curada, sem segredos, contendo
`profile_version`, modelo pinado, formatos, estilo global, blocos por raça/classe,
poses e regras negativas. Exemplo resumido:

```json
{
  "schema_version": 1,
  "profile_version": "valoria-gpt-image2-v1",
  "model": "gpt-image-2-2026-04-21",
  "formats": {
    "portrait": {"size": "1024x1536"},
    "epic_scene": {"size": "1536x1024"}
  },
  "pose_constraints": [
    "anatomically plausible grounded pose",
    "natural spine, neck and joint alignment",
    "exactly two coherent arms and two coherent legs when visible",
    "hands and weapon grips consistent with the action",
    "no extreme foreshortening or disconnected limbs"
  ],
  "epic_pose_ids": [
    "defensive_stance", "grounded_advance",
    "ritual_focus", "aftermath_stillness"
  ],
  "subclass_style_anchors": {
    "<subclass_id>": ["curated public visual vocabulary"]
  }
}
```

As âncoras de subclasse são texto curado e público, nunca uma nova imagem de
referência. `build_player_art_brief()` as ignora enquanto `player.subclass` for
nulo e as inclui em reformulação posterior; `build_epic_art_brief()` as inclui
quando o ramo já estiver confirmado.

**Novos `services/art_brief.py` e `services/art_triggers.py`:**

```python
class ArtBrief(TypedDict):
    subject: str
    canon: list[str]
    player_description: str
    composition: list[str]
    exclusions: list[str]
    reference_asset_ids: list[str]
    profile_version: str

def build_player_art_brief(character: Mapping[str, Any]) -> ArtBrief: ...
def build_npc_art_brief(state: Mapping[str, Any], npc_id: str) -> ArtBrief: ...
def build_epic_art_brief(state: Mapping[str, Any], event: Mapping[str, Any]) -> ArtBrief: ...
def render_image_prompt(brief: ArtBrief) -> str: ...
def resolve_art_triggers(previous: Mapping[str, Any], current: Mapping[str, Any],
                         *, action_key: str) -> list[ArtGenerationRequest]: ...
```

O renderer usa seções fixas e nunca concatena entrada do jogador como comando de
nível superior. `appearance` tem até 1.000 caracteres; `visual_exclusions`, 500;
controle, NUL, markup de papel e whitespace excessivo são normalizados.

### 3.2 Porta do provider e job

**Nova porta em `infrastructure/ports.py`:**

```python
@dataclass(frozen=True)
class ImageGenerationInput:
    prompt: str
    model: str
    size: str
    reference_blobs: tuple[BlobRef, ...]

@dataclass(frozen=True)
class GeneratedImage:
    payload: bytes
    mime_type: str
    provider_request_id: str | None
    model: str
    usage: dict[str, Any]

class ImageGenerator(Protocol):
    def generate(self, request: ImageGenerationInput) -> GeneratedImage: ...
```

**Novos arquivos:**

- `infrastructure/openai_images.py` — adapter GPT Image 2, timeout, erros tipados,
  sem fallback de texto;
- `workers/dynamic_art_jobs.py` — handler `generate_dynamic_art`;
- `services/dynamic_art.py` — reserva de orçamento, idempotência, estados e
  promoção via `asset_pipeline` da 10b.6;
- `tests/fakes/fake_image_generator.py` — PNG fixture válido, uso/custo sintético.

Fluxo do worker:

```text
claim job → load generation pending → mark generating → load approved references
→ provider once → validate bytes → asset pipeline/BlobStore → ready
→ on retryable error: retry same generation_id
→ refusal/permanent error: terminal state + placeholder
```

### 3.3 Dados e orçamento

Extender `app.assets` da 10b.6 ou criar `app.art_generations` relacionado a ela:

```sql
create table app.art_generations (
  generation_id uuid primary key,
  owner_id uuid not null,
  game_id uuid not null,
  timeline_epoch integer not null,
  arc_instance_id text,
  trigger_kind text not null check (trigger_kind in
    ('player_portrait','npc_first_appearance','arc_epic_moment')),
  trigger_instance_id text not null,
  subject_type text not null check (subject_type in ('player','npc','scene')),
  subject_id text not null,
  status text not null check (status in
    ('pending','generating','ready','failed_retryable','failed','refused',
     'rejected_quality','superseded')),
  model text not null,
  profile_version text not null,
  prompt_hash text not null,
  anchor_hash text not null,
  asset_id uuid,
  attempt_count integer not null default 0,
  usage_json jsonb not null default '{}',
  cost_usd numeric,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (game_id, timeline_epoch, trigger_kind, trigger_instance_id, profile_version)
);
```

Prompt e aparência podem ficar em coluna/registro privado criptografável ou
payload de auditoria separado; nunca em log. RLS e grants seguem owner explícito.

Ledger por arco:

```python
class ArcArtBudget(TypedDict):
    arc_instance_id: str
    npc_generations_used: int       # 0..4
    epic_generation_used: bool
    last_npc_generation_turn: int | None
```

O banco/JobQueue é autoridade no perfil local/hosted; o estado expõe uma projeção
para UI/checkpoint. Reserva e enqueue ocorrem na mesma transação. Restore cria
novo `timeline_epoch`; artes de futuro divergente não reaparecem, mas blobs ficam
retidos/superseded conforme lifecycle até limpeza segura.

### 3.4 API e frontend

**Alterar criação:**

```python
class CharacterCreateRequest(BaseModel):
    # campos existentes
    appearance: str = Field("", max_length=1000)
    visual_exclusions: str = Field("", max_length=500)

class ArtBriefRequest(BaseModel):
    race: str
    class_name: str
    appearance: str = Field(max_length=1000)
    visual_exclusions: str = Field("", max_length=500)
```

Endpoints:

- `POST /game/art/brief` — zero provider; devolve brief seguro para revisão;
- `POST /game/{game_id}/art/player/confirm` — reserva geração/reformulação;
- `GET /game/{game_id}/art/{generation_id}` — status + asset privado quando ready;
- `POST /game/{game_id}/art/{generation_id}/quality` — aprovar ou rejeitar
  qualidade; reformulação só no retrato do jogador e uma vez.

`GameResponse.visual` ganha campos aditivos `player_portrait`, `cue.dynamic_art`
e `epic_scene`, cada um com `status`, `generation_id`, asset opcional e erro
apresentável. React nunca recebe prompt privado, object key ou custo bruto sem
confirmação. `CreateScreen` adiciona descrição/revisão; `StoryLog` liga retrato
pronto ao NPC; `SceneArtwork` aceita cena épica temporária sem sobrescrever a arte
canônica do local.

## 4. Plano passo a passo

### Etapa 1 — Perfil, brief e triggers puros

1. **Testes** (`tests/test_dynamic_art_brief.py`): preservação de aparência,
   âncoras corretas, secrets excluídos, limites, bloco anatômico obrigatório,
   poses apenas do catálogo, retrato inicial sem antecipar subclasse, reformulação
   e cena épica com âncora do ramo, e prompt determinístico por input.
2. **Implementação:** dados, builders, sanitização e triggers sem provider.
3. **Verificação:** testes focados e lint de conteúdo verdes.

### Etapa 2 — Orçamento por arco e idempotência

1. **Testes** (`tests/test_dynamic_art_triggers.py`): 4 NPC/arco, cooldown 15,
   novo arco zera orçamento, campanha não tem teto global, boss ganha da conclusão,
   retry/restore/action_id não duplica, figurante não enfileira e
   `subclass_chosen` gera zero jobs e zero custo.
2. **Implementação:** `arc_instance_id`, ledger, reserva transacional e projeção.
3. **Verificação:** testes unitários + integração local Postgres.

### Etapa 3 — Provider, worker e storage

1. **Testes** (`tests/test_dynamic_art_jobs.py`): record-before-call, bytes/MIME,
   timeout/retry, recusa terminal, promoção atômica, crash após provider, dedupe,
   custo e redaction. Contract usa fake; integração real fica marcada.
2. **Implementação:** adapter OpenAI, worker e pipeline BlobStore.
3. **Verificação:** contratos File/Supabase local e reconciliação sem órfão.

### Etapa 4 — Criação e UX assíncrona

1. **Testes:** brief→confirmação, uma reformulação, placeholder, polling terminal,
   falha sem bloquear, URL privada e acessibilidade/390 px.
2. **Implementação:** DTOs/endpoints/React.
3. **Verificação:** build e browser smoke local.

### Etapa 5 — NPC e cena épica end-to-end

1. **Testes:** primeira aparição liga job ao mesmo cue; imagem pronta não repete;
   boss/conclusão uma por arco; herói usa retrato aprovado; checkpoint/epoch.
2. **Implementação:** integração no pós-turno durável e apresentação.
3. **Verificação:** E2E com fake, caos de worker/storage e smoke real.

## 5. Critérios de aceite

- [x] Apenas jogador, NPC elegível e épico do arco podem gerar arte.
- [x] Limites são 4 NPC + 1 épica por arco, sem teto de campanha.
- [x] Criação adapta descrição com raça/classe/Valoria e exige revisão antes do custo.
- [x] Retrato inicial não antecipa subclasse; escolhê-la no nível 3 não gera arte
      nem custo automaticamente.
- [x] Reformulação ainda disponível e futuras cenas épicas incorporam a âncora
      estética curada da subclasse sem exceder seus orçamentos existentes.
- [x] Todo prompt possui constraints explícitas de anatomia/pose natural.
- [x] Retrato aprovado mantém identidade nas cenas épicas.
- [x] GPT Image 2 está pinado em snapshot/perfil versionado e substituível por porta.
- [x] Job é durável/idempotente e nunca bloqueia turno ou criação.
- [x] Assets dinâmicos são privados, exportáveis e removíveis por lifecycle seguro.
- [x] Retry, restore, clique duplo e SSE→POST não duplicam geração/custo.
- [x] Falha/recusa/kill switch mantém jogo completo com placeholder.
- [x] Telemetria mede custo/latência/status sem registrar prompt ou aparência.
- [x] `cd web && npm run build` verde; fluxos desktop e 390 px aprovados.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de resiliência em qualquer structured output novo; adapter de imagem
  nunca é tratado como retorno Pydantic de LLM de texto.
- [x] Saves/checkpoints antigos continuam carregando.

## 6. Smoke test com provider real

1. Em ambiente local isolado e com teto de gasto explícito, gerar um retrato de
   personagem a partir de raça, classe e aparência; verificar snapshot, hashes,
   storage privado, derivados e custo registrado.
2. Alcançar o nível 3 e escolher a subclasse; confirmar zero job/cobrança. Se a
   reformulação estiver disponível, solicitá-la manualmente e verificar que o
   brief inclui o ramo e consome exatamente a franquia existente.
3. Revisar identidade e rubric de anatomia: mãos, quantidade/alinhamento de
   membros, pegada, coluna, centro de gravidade e pose natural. Reprovar
   manualmente qualquer arte defeituosa; não regenerar automaticamente.
4. Apresentar um NPC persistente sem arte; confirmar placeholder imediato e
   retrato assíncrono ligado ao mesmo NPC, sem segunda chamada ao recarregar.
5. Disparar boss e depois concluir o mesmo arco; confirmar exatamente uma cena
   épica, identidade do herói baseada no retrato aprovado e linguagem visual da
   subclasse já confirmada.
6. Derrubar worker/reiniciar durante um job; confirmar convergência sem blob,
   registro ou cobrança lógica duplicada.

## 7. Riscos & compatibilidade

- **Custo sem teto de campanha:** o controle por arco impede rajada local, mas uma
  campanha com muitos arcos continuará gerando. Telemetria, kill switch e
  confirmação do retrato são essenciais; nenhum saldo acumula.
- **Anatomia não é formalmente demonstrável:** prompt/poses reduzem risco, mas não
  garantem mãos perfeitas. A aprovação humana é a barreira final; auto-judge não
  pode criar ciclos caros.
- **Mudança estética do modelo:** snapshot pinado e matriz visual evitam drift
  silencioso. Upgrade é decisão de produto registrada.
- **Latência:** polling/placeholder tornam a imagem eventual; a primeira aparição
  do NPC pode mostrar silhueta antes do retrato terminar, comportamento esperado.
- **Privacidade:** aparência e retratos são dados do usuário; RLS, URL assinada,
  redaction, export e exclusão são requisitos, não polish posterior.
- **Dependência 10b:** implementar geração antes de fila/storage duráveis criaria
  perda e duplicação de custo. A ordem de dependência é deliberada.

## 8. Referências do provider

- GPT Image 2: https://developers.openai.com/api/docs/models/gpt-image-2
- Guia de geração de imagens: https://developers.openai.com/api/docs/guides/image-generation
