# SPEC — Fase 8A: Âncoras visuais contextuais

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `onboarding-valoria`, `inicio-personalizado`,
> `mapa-sublocais-viagem-variavel`, `npcs-3-camadas-traits`,
> `streaming-turno-sse`, `hardening-persistencia-sse-idempotencia` (`done`)
> **Desbloqueia:** Fase 8B (arte de itens/monstros e geração sob demanda) e
> Fase 9 (transições audiovisuais)

---

## 1. Contexto & Objetivo

Valoria já possui um acervo de âncoras visuais aprovado fora do jogo, mas o
frontend ainda apresenta raça, classe, NPC e local apenas por texto. Esta spec
integra esse acervo ao produto sem transformar a LLM em autoridade de identidade:
**IDs canônicos, visibilidade, primeira aparição e fallback são resolvidos em
Python; React apenas apresenta o contrato recebido da API.**

A experiência-alvo tem três momentos: os cards de raça e classe recebem uma
imagem-base; o local atual ganha uma arte de cena que muda ao viajar; e a primeira
aparição válida de um NPC recebe um retrato junto ao turno narrado. Recarregar a
página não repete a revelação do NPC, e repetir uma ação com o mesmo `action_id`
devolve exatamente a mesma pista visual sem reaplicar o turno.

Esta é a fatia **8A, curada e estática**. Ela substitui a premissa antiga de gerar
arte em tempo de request por um catálogo versionado, rápido e auditável. Geração
de item/monstro/NPC em runtime fica para 8B depois que armazenamento, moderação,
custo e latência tiverem contrato próprio.

### Mapeamento do projeto atual

- `web/src/components/CreateScreen.tsx` renderiza os seis `races_full` e as cinco
  chaves de `gamedata.CLASSES`, hoje em cards somente textuais.
- `web/src/App.tsx` mantém o diário em memória; `finishStreamEntry()` consolida a
  mesma entrada criada pelos chunks SSE. A pista visual deve ser anexada a essa
  entrada final, não criada como um segundo turno.
- `web/src/components/StoryLog.tsx` não conhece mídia; `PlayScreen.tsx` já possui
  um `stage` adequado para a cena persistente do local.
- `api.py::format_response()` é a fronteira pública comum a criação, ação, SSE e
  retomada. `/data/options` já entrega os IDs canônicos das raças.
- `world.current_location_id` é a fonte da verdade para local; o mapa contém 35
  nós, dos quais cinco são interiores com `parent_id`.
- NPCs têm `known_by_player`/`in_scene`, mas a resolução por nome canônico está
  duplicada e limitada a `lower()` em `agents/npc.py` e `services/discovery.py`.
- Saves estão em schema v5 e já persistem um ledger de 64 `action_id`s. A pista
  de NPC precisa participar da mesma semântica de idempotência.
- A build Vite é servida por `StaticFiles`; arquivos em `web/public/art/` ficam
  disponíveis como `/art/...` tanto no Vite dev quanto em `web/dist`.

### Auditoria do pacote importado

Fonte auditada: `VALORIA_GAME_ART_HANDOFF` (68 PNGs; SHA do ZIP
`8f1574b336a9fe8db5fe128d50b0f66b7a5a84fb57063848aa9de014e0709bd1`).
A aprovação declarada no JSON não basta: o importador exige arquivo presente,
`approved`, `public` e SHA-256 aprovado.

| Família necessária | Estado encontrado | Decisão desta spec |
|---|---:|---|
| Raças jogáveis | 6 entidades / 14 imagens, todas verificadas | importar uma capa real por raça; Osshari usa a variante do Mar feminina sugerida no handoff |
| Classes-base | 5/5 apresentações recuperáveis com SHA aprovado | importar as cinco capas |
| Locais | 36 imagens aprovadas; 35 nós no mapa atual | 22 mappings exatos + 13 fallbacks regionais explícitos cobrem o mapa inteiro |
| NPCs | 13 aprovados públicos | importar 12 IDs canônicos; Vrethis fica como fonte não mapeada por ainda não existir no grafo |

Os 12 retratos ligados ao grafo são Aelwin, Arcante Gresh, Astrin, Grum, Kahen,
Khatarn, Lady Aerwen, Velha Magda, Onda-Profunda, Silas Vane, Valerius e Vehkr.
Thessavar/Víbora continuam excluídos por serem secretos. Arquivo “compatível”,
nome parecido ou candidato temporário nunca autoriza vinculação.

---

## 2. Requisitos

- **R1 — Catálogo canônico:** toda arte de conteúdo publicada pertence a
  exatamente um `subject_type` (`race | class | location | npc`) e `subject_id`
  existente nos dados canônicos. O único asset reutilizável é o placeholder de
  sistema `awaiting_art`; nome livre nunca é a chave primária do frontend.
- **R2 — Proveniência fail-closed:** o importador só aceita uma fonte declarada,
  `status=approved`, `visibility=public` e SHA-256 idêntico ao manifesto. Divergência
  encerra o comando com erro e não sobrescreve derivados válidos.
- **R3 — Cobertura do onboarding:** os seis IDs de `origins.json` e as cinco
  classes de `classes.json` recebem uma imagem. Havendo fonte aprovada e
  verificável, ela é obrigatória; sem fonte aprovada, usa-se o PNG compartilhado
  `AGUARDANDO ARTE`, nunca um candidato provisório. `/data/options` devolve essas
  referências sem quebrar os campos legados `races`, `races_full` e `classes`.
- **R3.1 — Placeholder curado:** o PNG `AGUARDANDO ARTE` segue o tom dark medieval
  das âncoras, sem simular uma raça/classe específica. O fundo é gerado com a
  ferramenta de imagem; um teste Python/Pillow valida texto, dimensões e formato
  antes da publicação (e o importador pode reaplicar a tipografia se uma revisão
  futura exigir). Ele recebe proveniência, hash e alt próprios e pode ser
  substituído só por edição de catálogo.
- **R4 — Local por estado:** `GameResponse.visual.scene` deriva exclusivamente de
  `world.current_location_id`. Ao mudar o ID, a UI troca a cena; ao retomar, mostra
  a cena atual sem fabricar um evento narrativo.
- **R5 — Fallback de local honesto:** a ordem é arte exata → fallback explícito
  de pai/região no catálogo → placeholder CSS. O DTO informa `scope=exact |
  regional | placeholder`; nunca legenda uma arte regional como se fosse um
  interior específico.
- **R6 — Primeira aparição de NPC:** no máximo um `visual.cue` de NPC é emitido por
  turno. Prioridade: NPC alvo da rota atual, depois NPC que acabou de se tornar
  conhecido e está em cena segundo `npc_layers.is_in_scene()` (campo legado
  ausente continua significando presente). Só o escolhido entra em
  `visual_seen_entity_ids`.
- **R7 — Identidade determinística:** NPC usa `npc["id"]` quando válido; como
  compatibilidade, um resolvedor Python normaliza Unicode, caixa, pontuação e
  aliases de `entities.json`. Não se procura nome dentro da prosa da LLM.
- **R8 — NPC sem arte:** NPC canônico ainda sem retrato e NPC gerado em runtime
  recebem uma silhueta/monograma determinístico com nome e papel, nunca a arte de
  outra pessoa. A primeira apresentação também ocorre uma só vez.
- **R9 — Persistência e retry:** save schema v6 guarda os IDs já apresentados e
  um ledger visual limitado de 64 ações. Retry SSE→POST com qualquer UUID ainda
  retido no ledger retorna a mesma pista; a ação seguinte sem apresentação tem
  registro `cue=null` e não repete a anterior.
- **R10 — Retomada sem replay:** `GET /game/state` retorna a cena atual e
  `cue=null`. Checkpoint restaura também a memória visual daquele ponto da linha
  do tempo.
- **R11 — SSE/paridade:** POST clássico e evento SSE `state` produzem o mesmo
  `GameResponse.visual`. Depois de resolver/persistir o estado, o stream emite um
  evento aditivo `visual` antes dos chunks `narrative`; o cliente anexa a pista à
  mesma entrada que receberá o texto. O evento `state` final repete o contrato
  canônico para paridade/recovery, sem duplicar texto nem imagem.
- **R12 — Arquivos web:** fontes PNG não são servidas. Um importador Python remove
  EXIF/text chunks, corrige orientação e gera WebP responsivo com nome contendo o
  hash. Apenas derivados públicos versionados são commitados.
- **R13 — Orçamento:** thumbnail ≤ 120 KiB, retrato de exibição ≤ 300 KiB e cena
  ≤ 400 KiB. Raças/classes usam `loading=lazy`; durante o jogo só a cena corrente
  e, quando houver, um retrato são requisitados.
- **R14 — Segurança:** URLs são caminhos relativos sob `/art/v1/` produzidos pelo
  catálogo; nenhuma entrada do cliente vira caminho de arquivo. Entidade
  `hidden/secret` e metadata sensível não podem aparecer no catálogo público.
- **R15 — UX/acessibilidade:** toda imagem tem `alt` curado, dimensões reservadas
  contra layout shift, `figure/figcaption` quando há pista narrativa, foco/teclado
  preservados nos cards e animação removida com `prefers-reduced-motion`.
- **R16 — Mobile e falha de rede:** em 390 px a arte não encobre texto/HUD/dock de
  combate. Erro de carregamento troca localmente para o placeholder e nunca
  bloqueia criação, ação ou retomada.
- **R17 — Zero custo narrativo:** seleção e disparo visual não fazem chamada LLM,
  RAG, embedding ou geração de imagem. O comportamento é igual em MockLLM,
  FallbackLLM e providers reais.
- **R18 — Lint de conteúdo:** o validador acusa como erro IDs órfãos, hash/path
  inválido, arte não pública, cobertura de raça/classe incompleta ou arquivo acima
  do teto; ausência de local/NPC não essencial é aviso com relatório de cobertura.

### Fora de escopo

- Gerar imagens durante uma request de jogo ou chamar provider de imagem.
- Arte de item, monstro, carta, subclasse, região no passo 3 ou avatar customizado.
- Escolha de gênero/variante de retrato na criação; cada raça recebe uma capa-base
  real ou o placeholder `AGUARDANDO ARTE`, e variantes ficam preparadas no
  catálogo para uma spec futura.
- Persistir o diário React completo; somente a memória visual mínima fica no save.
- Som, sprites, vídeo, parallax pesado ou alteração do motor narrativo.
- Importar todos os 808 MB do pacote, seus candidatos, prompts ou PNGs originais.

---

## 3. Design técnico

### 3.1 Fonte de verdade e pipeline de assets

**Novo `data/visual_assets.json`** — catálogo curado e versionado. Não contém
caminho absoluto da máquina. Exemplo com IDs reais:

```json
{
  "schema_version": 1,
  "system_assets": {
    "awaiting_art": {
      "url": "/art/v1/system/aguardando-arte.png",
      "alt": "Arte desta opção ainda em produção",
      "width": 768,
      "height": 1152,
      "bytes": 0,
      "sha256": "<sha256-do-placeholder>"
    }
  },
  "assets": [
    {
      "asset_id": "VAL-P4-CLS-DEVOTO_ABISMO-001",
      "subject_type": "class",
      "subject_id": "Devoto do Abismo",
      "title": "Devoto do Abismo",
      "alt": "Devoto do Abismo em armadura remendada e marcas rituais",
      "visibility": "public",
      "source": {
        "bundle": "valoria_codex_anchor_project_from_zero",
        "relative_path": "output/review/phase4_presentations/110_VAL-P4-CLS-DEVOTO_ABISMO-001.png",
        "sha256": "6c4803a964bd11512d632cb093ced29bbe0c55df3da27cd849454e24157d43a5"
      },
      "variants": {
        "thumbnail": {
          "url": "/art/v1/class/devoto-do-abismo.<sha12>.thumb.webp",
          "width": 384,
          "height": 576,
          "bytes": 0,
          "sha256": "<sha256-do-derivado>"
        },
        "display": {
          "url": "/art/v1/class/devoto-do-abismo.<sha12>.webp",
          "width": 768,
          "height": 1152,
          "bytes": 0,
          "sha256": "<sha256-do-derivado>"
        }
      },
      "placeholder_color": "#3a2c27"
    }
  ],
  "location_fallbacks": {
    "taverna_javali_dourado": "na_anel_lama"
  }
}
```

O arquivo final não usa placeholders `<...>` nem `bytes=0`. Para raça usa IDs
como `race_humanos`; para local, IDs como `pr_vaelorn`; para NPC, IDs como
`npc_grum`. Classes continuam usando a chave canônica atual porque
`classes.json` ainda não possui um ID próprio. A matriz de criação pode apontar
para `system_assets.awaiting_art` quando não há fonte aprovada; isso não transforma
o placeholder em arte canônica daquela entidade.

**Placeholder já autorizado e gerado nesta sessão:** fonte em
`assets/visual/system/aguardando-arte-source.png`, 1024×1536, SHA-256
`6e22252aa9b9610cee908358e6978028e84ff7401ecf79d55c79f1605132e51f`.
O importador produzirá a cópia web otimizada; o original não deve ser usado
diretamente na página (2,9 MB).

**Novo `scripts/import_visual_assets.py`** — CLI Python/Pillow:

```python
def import_assets(
    source_root: Path,
    catalog_path: Path,
    output_root: Path,
    *,
    check: bool = False,
    prune: bool = False,
) -> ImportReport: ...
```

- `--source-root` aponta para a raiz extraída, mas nunca é gravado como absoluto.
- valida arquivo e SHA antes de qualquer escrita;
- gera em diretório temporário e promove atomicamente só quando o lote é válido;
- aplica orientação, converte para RGB, remove metadata e emite WebP;
- produz thumbnails de 384 px e retratos de 768 px; cenas de 640 e 1280 px,
  sempre preservando proporção, sem crop destrutivo;
- calcula hash, bytes, dimensões e cor de placeholder em Python;
- `--check` não escreve; `--prune` é explícito e nunca é default.

Pillow entra no grupo `dev` e fica travado em `uv.lock`; o runtime da API não
depende dele. Somente `data/visual_assets.json`, derivados WebP e documentação de
proveniência entram no Git.

### 3.2 Catálogo e identidade em Python

**Novo `services/entity_identity.py`:**

```python
def normalize_entity_label(value: str) -> str: ...
def resolve_npc_entity_id(npc: Mapping[str, Any], fallback_name: str = "") -> str | None: ...
```

O índice inclui `id`, `name` e `aliases` apenas de entidades `type=npc`.
`agents/npc.py` e `services/discovery.py` passam a reutilizar esse resolvedor,
eliminando o match duplicado por nome sem mudar regras de quest/Codex.

**Novo `services/visual_catalog.py`:**

```python
SubjectType = Literal["race", "class", "location", "npc"]

def load_visual_catalog(path: Path | None = None) -> VisualCatalog: ...
def visual_for(subject_type: SubjectType, subject_id: str) -> dict | None: ...
def creation_visuals() -> dict[str, dict[str, dict]]: ...
def scene_visual(world: Mapping[str, Any]) -> dict: ...
def resolve_turn_visual_state(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    action_key: str,
) -> dict[str, Any]: ...
def visual_response(state: Mapping[str, Any], *, cue_action_key: str | None) -> dict: ...
```

`resolve_turn_visual_state` é puro: devolve o novo ledger e os IDs vistos, sem
I/O, LLM ou leitura da narrativa. O chamador incorpora o resultado ao estado
antes do save. Cada ação ganha um registro, inclusive quando `cue=null`.

### 3.3 Estado, persistência e idempotência

Adicionar a `GameState`:

```python
class VisualCue(TypedDict, total=False):
    kind: Literal["npc_first_appearance"]
    subject_id: str
    subject_name: str
    caption: str
    asset_id: str | None
    fallback: bool

class VisualCueRecord(TypedDict):
    action_key: str
    cue: Optional[VisualCue]

visual_seen_entity_ids: List[str]
visual_cue_ledger: List[VisualCueRecord]
```

O schema sobe de v5 para v6. `_migrate_v5_to_v6()` cria as duas listas vazias,
preserva saves arquivados e é idempotente. `_state_to_save_data()` e
`_raw_to_state()` persistem ambos os campos. Os ledgers são normalizados,
deduplicados por chave e limitados a 64 registros/IDs seguros; não guardam URLs
nem uma cópia do catálogo.

Chaves da transição:

- nova campanha: `new:<game_id>`;
- ação com UUID: o próprio `action_id`;
- cliente legado sem UUID: `turn:<turn_count>` calculado após o grafo.

Em `_run_turn` e no worker SSE, a ordem atômica é: estado anterior → grafo →
resolver visual → registrar `cue` (inclusive nula) → marcar `action_id` → podar
os dois ledgers para 64 → salvar → checkpoint → responder. O caminho “já
processado” não recalcula: apenas chama `format_response(state,
cue_action_key=req.action_id)`. Assim qualquer retry ainda no ledger recebe a
mesma pista. O worker coloca `(final_state, action_key)` na fila SSE; o gerador
não tenta inferir a chave depois do save.

Checkpoints usam a serialização comum e, portanto, incluem o ledger. Voltar no
tempo pode legitimamente tornar uma apresentação futura novamente inédita.

### 3.4 Contrato da API

Novos DTOs Pydantic em `api.py` (com `Field(default_factory=...)`, sem defaults
mutáveis compartilhados):

```python
class VisualVariantResponse(BaseModel):
    url: str
    width: int
    height: int
    bytes: int
    sha256: str

class VisualAssetResponse(BaseModel):
    asset_id: str
    subject_type: Literal["race", "class", "location", "npc"]
    subject_id: str
    title: str
    alt: str
    placeholder_color: str
    thumbnail: VisualVariantResponse
    display: VisualVariantResponse

class SceneVisualResponse(BaseModel):
    location_id: str
    location_name: str
    scope: Literal["exact", "regional", "placeholder"]
    asset: VisualAssetResponse | None

class VisualCueResponse(BaseModel):
    kind: Literal["npc_first_appearance"]
    subject_id: str
    subject_name: str
    caption: str
    asset: VisualAssetResponse | None
    fallback: bool

class VisualResponse(BaseModel):
    scene: SceneVisualResponse
    cue: VisualCueResponse | None = None
```

`GameResponse` ganha `visual: VisualResponse`. `format_response` passa a aceitar:

```python
def format_response(state: dict, *, cue_action_key: str | None = None) -> GameResponse: ...
```

Sem `cue_action_key` — inclusive em `GET /game/state`, equip, level-up e morte —
a pista é `null`, mas a cena sempre existe. `/game/new` usa a chave `new:*`.
POST e SSE passam a chave da ação. O SSE adiciona `event: visual` imediatamente
antes de `event: narrative`, com o mesmo `VisualResponse` que aparecerá depois
em `event: state`; clientes antigos ignoram o evento desconhecido.

`GET /data/options` ganha:

```json
{
  "visuals": {
    "races": { "race_humanos": { "...": "VisualAssetResponse" } },
    "classes": { "Devoto do Abismo": { "...": "VisualAssetResponse" } }
  }
}
```

O servidor nunca devolve `source.relative_path`, SHA da fonte, prompts, notas de
review ou qualquer entrada fora do catálogo público.

### 3.5 Regra de apresentação de NPC

São elegíveis apenas NPCs `known_by_player != false` e aprovados por
`npc_layers.is_in_scene()`; isso conserva a compatibilidade dos NPCs legados sem
campo `in_scene`.
A seleção determinística é:

1. `active_npc_name`/ID da rota NPC atual, se elegível e ainda não visto;
2. transição `ausente/desconhecido/fora de cena` → `conhecido e em cena`;
3. ordem por ID canônico para desempate.

O token persistido é `npc:<entity_id>` para canônico ou
`runtime_npc:<slug-estável>` para gerado. A existência de um retrato não decide
se o NPC é conhecido; ela só muda `asset` de `null` para uma referência pública.
Não se marca todos os candidatos: somente o que efetivamente ganhou a pista.

### 3.6 Frontend React

**Tipos:** espelhar os DTOs em `web/src/types.ts`; `CreateOptions.visuals` é
opcional durante compatibilidade. `LogEntry` ganha `visual?: VisualCueView`.

**Criação:** `CreateScreen.tsx` obtém arte pelo ID de raça e pela chave de classe.
Cada card renderiza thumbnail com largura/altura explícitas, placeholder e estado
selecionado legível. Se a API antiga não fornecer `visuals`, o card textual atual
continua funcionando.

**Jogo:**

- novo `web/src/components/SceneArtwork.tsx` renderiza `data.visual.scene` no topo
  do `stage`, com gradiente para manter contraste e crossfade só quando muda o
  `location_id`/`asset_id`;
- novo `web/src/components/VisualArtwork.tsx` concentra `<picture>`, fallback,
  alt, caption, dimensões e tratamento de erro;
- `onTurn()` grava `r.visual.cue` na nova entrada do narrador;
- `onVisual` guarda a pista do evento SSE e abre/enriquece uma única entrada do
  narrador; os chunks seguintes entram nela, já com a imagem visível;
- `finishStreamEntry()` reconcilia com `state.visual` sem inserir outra imagem;
- `StoryLog.tsx` mostra o retrato antes do corpo do mesmo turno;
- `handleContinue()` não recebe cue do servidor e, portanto, não repete retrato.

CSS em `web/src/styles.css` mantém retrato vertical, cena horizontal e layout de
390 px. `motion` pode fazer crossfade curto, respeitando reduced motion.

### 3.7 Arquivos

**Novos:**

- `specs/SPEC-094-fase-8-ancoras-visuais-contextuais.md` — esta spec.
- `data/visual_assets.json` — catálogo público e mapeamentos explícitos.
- `services/entity_identity.py` — identidade/aliases de NPC.
- `services/visual_catalog.py` — carga, lookup, cena e primeira apresentação.
- `scripts/import_visual_assets.py` — verificação/otimização Python.
- `web/public/art/v1/{race,class,location,npc}/` — derivados WebP.
- `web/public/art/v1/system/aguardando-arte.png` — placeholder compartilhado,
  com composição visual gerada e tipografia final aplicada por Pillow.
- `web/src/components/VisualArtwork.tsx` e `SceneArtwork.tsx`.
- `tests/test_visual_assets.py` e `docs/ARTE_VISUAL.md`.

**Alterados:**

- `pyproject.toml`/`uv.lock` — Pillow no grupo dev.
- `state.py`, `persistence.py`, `api.py`, `game_engine.py` — schema v6, defaults
  dos construtores de estado e contrato visual.
- `agents/npc.py`, `services/discovery.py` — resolvedor canônico compartilhado.
- `services/content_validator.py`, `scripts/validate_content.py` — lint/cobertura.
- `web/src/types.ts`, `App.tsx`, `CreateScreen.tsx`, `StoryLog.tsx`,
  `PlayScreen.tsx`, `styles.css` — apresentação responsiva.
- `tests/test_api.py`/suítes equivalentes de API, persistência e frontend.
- `ESTADO_ATUAL.md`, `ROADMAP.md`, `docs/AUTORIA.md` — operação e autoria.

---

## 4. Plano passo a passo

### Etapa 0 — Fechar a matriz importável e o placeholder

1. **Testes primeiro** (`tests/test_visual_assets.py`): criar fixtures de manifesto
   que rejeitam SHA divergente, status não aprovado, visibilidade não pública,
   duplicidade de `(subject_type, subject_id)` e path fora da raiz.
2. **Placeholder:** usar a composição neutra já gerada no mesmo tom dark medieval
   das âncoras; validar `AGUARDANDO ARTE`/dimensões/formato em Pillow e registrar
   prompt/proveniência e hash em `docs/ARTE_VISUAL.md`.
3. **Curadoria:** preencher a matriz pacote → ID do jogo. O pacote final trouxe
   arte exata aprovada para todas as raças; `awaiting_art` permanece reserva de
   sistema e não foi publicado para elas.
4. **Gate:** relatório confirma imagem 6/6 para raça (real ou `awaiting_art`),
   classe-base 5/5, lista de locais exatos/regionais e NPCs com retrato/fallback.

### Etapa 1 — Pipeline Python e catálogo

1. **Testes:** `test_import_is_deterministic`, `test_import_strips_metadata`,
   `test_import_preserves_aspect_ratio`, `test_import_respects_byte_budget`,
   `test_check_does_not_write`, `test_prune_is_opt_in`.
2. **Implementação:** adicionar Pillow dev, CLI transacional e derivados WebP com
   hashes no nome; documentar o comando em `docs/ARTE_VISUAL.md`.
3. **Verificação:** rodar import duas vezes (`--check` na segunda), lint de
   conteúdo e `git diff --check`.

### Etapa 2 — Catálogo, identidade e regras puras

1. **Testes:** validar os 6 IDs de raça, 5 classes, todos os location IDs mapeados,
   aliases/acentos de NPC e rejeição de ID/URL/visibilidade inválidos.
2. **Testes de cena:** exata, interior com fallback explícito, regional e
   placeholder; a legenda nunca confunde fallback com local exato.
3. **Testes de NPC:** alvo ativo vence, primeira transição aparece uma vez,
   múltiplos geram no máximo uma pista, só o escolhido vira visto, runtime usa
   fallback e prosa contendo um nome não dispara nada.
4. **Implementação:** `entity_identity.py` e `visual_catalog.py`; substituir os
   dois matches duplicados existentes.

### Etapa 3 — Save v6 e fronteira API/SSE

1. **Testes de persistência:** v5→v6, roundtrip, idempotência, ledger deduplicado,
   checkpoint/restore e save arquivado.
2. **Testes de API:** `/data/options` expõe apenas arte pública; nova campanha
   tem cena; viagem altera cena; GET state não repete cue; retry do mesmo UUID
   repete a mesma cue; UUID seguinte sem NPC retorna `null`.
3. **Teste de paridade:** resposta POST, evento SSE `visual` e `state.visual` são
   iguais para a mesma transição; `visual` precede `narrative`; desconexão+
   fallback preserva a pista já salva.
4. **Implementação:** schema v6, DTOs, ordem atômica no POST/worker SSE e
   `format_response(..., cue_action_key=...)`.

### Etapa 4 — Onboarding e narrativa React

1. **Testes/contratos:** ampliar a suíte frontend para afirmar lookup por ID,
   cue visível antes do primeiro chunk e anexada à única entrada SSE, fallback da API antiga e ausência de
   `dangerouslySetInnerHTML` em campos de catálogo/caption.
2. **Implementação:** componentes, tipos e estilos; thumbnails nos passos 1/2,
   cena em `PlayScreen`, retrato no mesmo artigo narrativo.
3. **Build:** `cd web && npm run build` verde; verificar que `web/dist/art/v1`
   contém exatamente os derivados catalogados.

### Etapa 5 — Gate integrado e documentação

1. `uv run python scripts/validate_content.py` = 0 erros; warnings de cobertura
   remanescente documentados.
2. `uv run ruff check .`, `uv run pytest` e `npm run build` verdes.
3. Smoke API clássico + SSE e smoke browser desktop/mobile conforme seção 6.
4. Atualizar esta spec para `done`, `ROADMAP.md`, `ESTADO_ATUAL.md`,
   `docs/AUTORIA.md` e contagem real de testes.

---

## 5. Critérios de aceite

- [x] Catálogo público liga cada asset a ID canônico e passa no gate de SHA.
- [x] Seis raças e cinco classes exibem imagem: arte real quando aprovada e
  `AGUARDANDO ARTE` somente quando não há fonte aprovada verificável.
- [x] A cena inicial aparece e troca ao mudar `current_location_id`.
- [x] Local sem arte exata usa fallback explicitamente rotulado, nunca arte falsa.
- [x] NPC elegível aparece com retrato/fallback no primeiro turno e não novamente.
- [x] Retry com o mesmo `action_id` devolve a mesma cue sem duplicar o turno.
- [x] `GET /game/state` restaura cena sem reapresentar cue antiga.
- [x] POST e SSE têm paridade; streaming não cria segunda entrada no diário.
- [x] Nenhum segredo, path de fonte, prompt ou metadata de review chega ao cliente.
- [x] Imagens atendem orçamento, alt text, dimensões, reduced motion e 390 px.
- [x] Falha de imagem degrada visualmente e nunca bloqueia gameplay.
- [x] `uv run python scripts/validate_content.py` sem erros.
- [x] `uv run ruff check .` e `cd web && npm run build` verdes.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Saves v5 continuam carregando via migração v6; checkpoint mantém semântica.
- [x] Guard de FallbackLLM não se aplica: nenhum structured output/LLM novo.

---

## 6. Smoke test com LLM real e browser

Mesmo sem decisão visual pela LLM, o smoke real permanece obrigatório para provar
que uma narração real não interfere no detector estruturado.

1. Com provider real, criar personagem e confirmar as seis capas de raça, cinco
   de classe e a cena inicial; `simulated=false`.
2. Em save controlado numa localização mapeada, entrar em outro local e confirmar
   que a cena troca pelo ID, sem analisar o texto narrado.
3. Colocar Grum conhecido/em cena, falar com ele e confirmar um único retrato no
   mesmo bloco narrativo. Repetir a request com o mesmo `action_id`: mesmo estado,
   mesma cue e um único turno aplicado.
4. Enviar nova ação e recarregar `/game/state`: Grum não reaparece; a cena atual
   permanece.
5. Repetir no browser em desktop e 390×844: sem overflow, texto/HUD/dock legíveis,
   console limpo e axe WCAG A/AA sem nova violação.

Registrar game ID, provider/modelo, screenshots, contagem de requests e resultado
no handoff. O smoke não autoriza geração de imagem nem aumenta chamadas por turno.

---

## 7. Riscos & compatibilidade

- **Pacote incompleto:** o maior risco é confiar no `status=approved` sem o binário
  correspondente. SHA fail-closed e o placeholder explícito impedem importação
  enganosa sem bloquear a entrega.
- **Peso do Git/build:** somente WebP derivados entram no repositório; originais,
  candidatos e o ZIP ficam fora. Hash no nome permite cache e atualização segura.
- **IDs de classe:** hoje são nomes. O catálogo aceita isso como dívida explícita;
  uma futura migração para `class_id` deve ter aliases, não renomear silenciosamente.
- **NPCs gerados:** não possuem arte individual. O fallback é deliberado para não
  representar uma pessoa com o rosto de outra.
- **Interiores/lacunas:** fallback regional preserva atmosfera, mas o DTO expõe o
  escopo real. A cobertura pode crescer por edição de dados sem tocar na regra.
- **Compatibilidade de cliente:** campos novos são aditivos; `visuals` opcional no
  TypeScript mantém frontend novo funcional contra API antiga durante dev.
- **Compatibilidade de save:** v5 ganha defaults vazios; v6 não guarda URLs, então
  trocar um derivado no catálogo atualiza a apresentação sem migrar saves.
- **Idempotência:** `visual_cue_ledger` acompanha a janela de 64 ações e precisa
  ser salvo antes da resposta. Qualquer atalho que calcule cue só no React reabre
  duplicação em reconnect/retry.
- **Quota/latência:** zero request externa adicional; lookup é local e cacheável.
  A latência percebida depende apenas do download do asset e respeita os tetos.
