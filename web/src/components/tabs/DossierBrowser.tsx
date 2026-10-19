import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import type { DossierBase } from "../../types";
import { safeStorage } from "../../safeStorage";
import { loadSeen, markerFor, MARKER_LABEL, openKey, saveSeen, withSeen, type SeenMap } from "../../dossiers";
import { ArrivalLi, useArrivals } from "../../design/primitives";
import { CertaintyBadge } from "./CertaintyBadge";
import { DossierDetail } from "./DossierDetail";
import "./tabs.css";

/** SPEC-211 R12: lista + detalhe numa ÚNICA região rolável. Setas movem o foco na lista,
 *  Enter abre (botão nativo), Esc volta. O dossiê aberto e o "visto" sobrevivem a reload
 *  (`safeStorage`, por game_id + aba; nunca fonte de verdade). */
export interface DossierBrowserProps<T extends DossierBase> {
  gameId: string;
  tabId: string;
  items: T[];
  empty: string;
  subtitle?: (item: T) => string;
  lead?: (item: T) => ReactNode;
  behind?: boolean;
}

/** `key` por jogo+aba: seções diferentes na mesma posição da árvore NÃO compartilham
 *  dossiê aberto nem mapa de "visto" (R12), e troca de save nunca herda estado. */
export function DossierBrowser<T extends DossierBase>(props: DossierBrowserProps<T>) {
  return <DossierBrowserInner<T> key={`${props.gameId}:${props.tabId}`} {...props} />;
}

function DossierBrowserInner<T extends DossierBase>({ gameId, tabId, items, empty, subtitle, lead, behind }: DossierBrowserProps<T>) {
  const [openId, setOpenId] = useState<string | null>(() => {
    try { return safeStorage.get(openKey(gameId, tabId)); } catch { return null; }
  });
  const [seen, setSeen] = useState<SeenMap>(() => loadSeen(safeStorage, gameId, tabId));
  const rows = useRef(new Map<string, HTMLButtonElement>());
  const lastOpened = useRef<string | null>(null);
  const arrivals = useArrivals();
  const backRef = useRef<HTMLButtonElement>(null);

  const current = openId ? items.find((item) => item.id === openId) ?? null : null;

  // Marca como visto a versão atual do dossiê aberto (nunca altera a versão do servidor).
  useEffect(() => {
    if (!current) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setSeen((prev) => {
      const next = withSeen(prev, current);
      if (next !== prev) saveSeen(safeStorage, gameId, tabId, next);
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- deps deliberadas: o efeito deve reexecutar só nestas chaves (callbacks/valores recriados a cada render não podem disparar de novo)
  }, [current?.id, current?.version, gameId, tabId]);

  function open(id: string | null) {
    if (id) lastOpened.current = id;
    setOpenId(id);
    try { if (id) safeStorage.set(openKey(gameId, tabId), id); else safeStorage.remove(openKey(gameId, tabId)); } catch { /* conveniência */ }
  }

  // Ao abrir o dossiê o foco vai para "Voltar" (a linha clicada desmonta): Esc/teclado seguem funcionando.
  useEffect(() => {
    if (current) backRef.current?.focus();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- deps deliberadas: o efeito deve reexecutar só nestas chaves (callbacks/valores recriados a cada render não podem disparar de novo)
  }, [current?.id]);

  // Ao voltar, devolve o foco à linha que estava aberta.
  useEffect(() => {
    if (openId === null && lastOpened.current) rows.current.get(lastOpened.current)?.focus();
  }, [openId]);

  function onListKey(event: KeyboardEvent<HTMLUListElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Home" && event.key !== "End") return;
    const ids = items.map((item) => item.id);
    const active = ids.indexOf((document.activeElement as HTMLElement | null)?.dataset.dossierId ?? "");
    let next = active;
    if (event.key === "ArrowDown") next = Math.min(ids.length - 1, active + 1);
    else if (event.key === "ArrowUp") next = Math.max(0, active - 1);
    else if (event.key === "Home") next = 0;
    else next = ids.length - 1;
    event.preventDefault();
    rows.current.get(ids[next])?.focus();
  }

  function onDetailKey(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Escape") return;
    event.preventDefault(); // não fecha o painel de contexto: Esc só volta à lista
    open(null);
  }

  if (current) {
    return (
      // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- atalho de teclado delegado: só reage a teclas que borbulham de controles focáveis internos
      <article className="dossier" aria-label={`Dossiê: ${current.title}`} onKeyDown={onDetailKey}>
        <button type="button" className="dossier__back" ref={backRef} onClick={() => open(null)}>← Voltar à lista</button>
        <DossierDetail item={current} />
      </article>
    );
  }

  if (!items.length) return <p className="combat-empty">{empty}</p>;
  return (
    <>
      {behind && <p className="dossier__behind">Atualizando…</p>}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- atalho de teclado delegado: só reage a teclas que borbulham de controles focáveis internos */}
      <ul className="dossier-list" onKeyDown={onListKey}>
        {items.map((item) => {
          // Chegou agora (animação "Novo" do codex.entry.reveal) => não repete o selo textual.
          const marker = arrivals.has(`dos:${item.id}`) ? null : markerFor(item, seen);
          return (
            <ArrivalLi key={item.id} id={`dos:${item.id}`}>
              <button
                type="button"
                className="dossier-row"
                data-dossier-id={item.id}
                ref={(node) => { if (node) rows.current.set(item.id, node); else rows.current.delete(item.id); }}
                onClick={() => open(item.id)}
              >
                {lead?.(item)}
                <span className="dossier-row__main">
                  <span className="dossier-row__title">{item.title}</span>
                  {subtitle && <span className="dossier-row__sub">{subtitle(item)}</span>}
                </span>
                <span className="dossier-row__flags">
                  {marker && <span className={"dossier-flag dossier-flag--" + marker}>{MARKER_LABEL[marker]}</span>}
                  <CertaintyBadge stamp={item.knowledge} />
                </span>
              </button>
            </ArrivalLi>
          );
        })}
      </ul>
    </>
  );
}
