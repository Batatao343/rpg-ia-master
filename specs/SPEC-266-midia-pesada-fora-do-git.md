# SPEC-266 — Tirar mídia pesada de marketing do git

> **Status:** `draft` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (só os 2 MP4 renderizados saem; insumos do Remotion e pacote `proximas-specs` ficam; ver §8)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** decisão do dono sobre onde guardar os vídeos (Release do GitHub, Drive, LFS)
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Cerca de **44 MB** de mídia de divulgação estão versionados (tamanho do blob em `HEAD`):

| Arquivo | Bytes |
|---|---|
| `docs/descricao_projeto/brag-output/brag-25s.mp4` | 17.847.765 |
| `docs/descricao_projeto/rpg-ia-master-linkedin-3min-narrado.mp4` | 17.554.897 |
| `docs/descricao_projeto/video/public/music/crossing_the_chasm.mp3` | 6.301.717 |
| `docs/descricao_projeto/video/public/brag/play.mp4` | 2.468.079 |

Também há prévias de 3,1 MB em `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/previas/*.png`
e a pasta `historico-nao-executar/` (10 arquivos), resíduos do pacote cujas specs já
viraram SPEC-199–236. Todo clone e todo checkout do CI baixam isso. Só `.gitignore`,
`.gitleaks.toml` e `docs/README.md` citam `docs/descricao_projeto/`; o deploy da Vercel
exclui `docs/**`.

## 2. Requisitos

- **R1** — *(revisado)* Só os dois **renderizados** saem: `brag-output/brag-25s.mp4` e
  `rpg-ia-master-linkedin-3min-narrado.mp4` (~35 MB). Subir para o local escolhido pelo dono e
  trocar, em `docs/descricao_projeto/README.md:7-8`, por links + SHA-256.
  **Ficam** `video/public/music/crossing_the_chasm.mp3` e `video/public/brag/play.mp4`: são
  **insumos** do projeto Remotion versionado (`video/src/brag/Brag.tsx:355`
  `staticFile('music/crossing_the_chasm.mp3')`; `video/package.json:11` script `timeline:linkedin`
  `--music music/crossing_the_chasm.mp3`; `play.mp4` está na sequência de cenas do Brag). Tirá-los
  quebra `remotion render`. Se o dono quiser tirá-los também, a spec precisa de um passo de
  restauração documentado (download + SHA) no README do vídeo, e a trilha CC BY 4.0 mantém a
  atribuição.
- **R2** — `git rm` dos 2 arquivos renderizados; ignorar **só esses caminhos** (ou
  `docs/descricao_projeto/*.mp4` e `docs/descricao_projeto/brag-output/*.mp4`). **Não** usar
  `docs/descricao_projeto/**/*.mp4`/`*.mp3`: o glob passaria a ignorar os insumos de `video/public/`.
- **R3** — *(revisado)* `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/` **fica inteiro**:
  `MANIFEST_SHA256.txt:6-21` lista `historico-nao-executar/*` e `previas/*.png` (apagar deixa o
  manifesto falso), o `README_COMECE_AQUI.md:25` descreve as pastas, e SPEC-202:19, SPEC-203:17 e
  SPEC-205:20 linkam `historico-nao-executar/`. Ganho de 3,1 MB não paga a quebra.
- **R4** — Sem reescrita de histórico neste passo (exige decisão separada e force push).

### Fora de escopo

Evidências de spec (`docs/spec*/evidence/*.webm/png`) linkadas pelos READMEs; a
imagem `assets/visual/system/aguardando-arte-source.png` (SHA fixado no ESTADO_ATUAL);
os índices FAISS; `project_index/repo_graph.json` (ver relatório, "não podar agora").

## 3–4. Design e plano

1. Upload + registro de SHA-256 (R1). 2. Remoção + `.gitignore` (R2). 3. Checagem de links (R3).

## 5. Critérios de aceite

- [ ] `git ls-files docs/descricao_projeto | xargs -I{} git cat-file -s HEAD:{}` sem arquivo > 1 MB
- [ ] `uv run python -m project_index check` verde após regenerar em checkout limpo
- [ ] `uv run pytest` verde (nenhum teste lê esses arquivos)
- [ ] Links novos abrem; `git grep -nE "brag-25s|linkedin-3min-narrado"` sem link para arquivo removido
- [ ] `cd docs/descricao_projeto/video && npx remotion compositions src/index.ts` (ou equivalente) ainda
      resolve os `staticFile` (insumos presentes)

## 6. Smoke

Nenhum smoke de runtime (só docs).

## 7. Riscos & compatibilidade

Risco **baixo**. O ganho de tamanho de clone só vem com reescrita de histórico, que fica
fora daqui. O ganho imediato: checkout menor e diffs sem binário. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

Achados:
1. `crossing_the_chasm.mp3` e `video/public/brag/play.mp4` **não são saída, são insumo** do projeto
   Remotion versionado em `docs/descricao_projeto/video/` (`src/brag/Brag.tsx:355`, `package.json:11`,
   `src/data/timeline_linkedin.json` `"music"`). Removê-los quebra o re-render dos vídeos. Agora só os dois
   MP4 renderizados saem (~35 MB dos 44 MB).
2. O glob proposto `docs/descricao_projeto/**/*.mp4` passaria a ignorar os insumos em `video/public/`.
3. O pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/` tem `MANIFEST_SHA256.txt` cobrindo
   `previas/` e `historico-nao-executar/`, e SPEC-202/203/205 linkam `historico-nao-executar/`. Fica inteiro.
- O deploy não é afetado (`.vercelignore` e `vercel.json` excluem `docs/**`).
