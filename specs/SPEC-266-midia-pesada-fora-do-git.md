# SPEC-266 — Tirar mídia pesada de marketing do git

> **Status:** `draft`
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

- **R1** — Subir os 4 arquivos de mídia para um local escolhido pelo dono e trocá-los, em
  `docs/descricao_projeto/README` (ou `docs/README.md`), por links + SHA-256.
- **R2** — `git rm` dos 4 arquivos; adicionar `docs/descricao_projeto/**/*.mp4` e `*.mp3` ao `.gitignore`.
- **R3** — `proximas-specs/.../previas/` e `historico-nao-executar/`: antes de remover, rodar
  `git grep -n "previas/\|historico-nao-executar"` e manter tudo o que alguma spec ou doc linka.
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
- [ ] Links novos abrem; checagem de links markdown (`scripts/normalize_specs.py --check`) sem link quebrado

## 6. Smoke

Nenhum smoke de runtime (só docs).

## 7. Riscos & compatibilidade

Risco **baixo**. O ganho de tamanho de clone só vem com reescrita de histórico, que fica
fora daqui. O ganho imediato: checkout menor e diffs sem binário. Rollback: `git revert`.
