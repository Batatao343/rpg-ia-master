// SPEC-427: a fila de uma ação do compositor. A decisão (esperar/enviar/devolver) é de `decideQueued`; aqui ficam o
// estado, o efeito que chama `onAction` UMA vez (do render em que `busy` já é falso) e a devolução ao rascunho.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ActionOptions } from "../types";
import { loadPending } from "../pendingOperation";
import { turnLocked } from "../turnLock";
import { getChatSession, setChatSession } from "../workspace/chatSessionStore";
import {
  QUEUE_REMOVED, QUEUED_ANNOUNCE, QUEUED_REPLACED, canEnqueue, decideQueued, mergeDraft, returnNote,
  type QueueBase, type QueuedAction, type ReturnReason,
} from "../queuedAction";

export interface QueuedActionApi {
  queued: string | null;
  /** `true` quando o texto foi para a fila (o chamador esvazia o campo). */
  enqueue: (text: string) => boolean;
  remove: () => void;
  /** Nota visível abaixo do campo (devolução). */
  note: string | null;
  /** Texto para a região viva única do compositor. */
  liveNote: string | null;
  clearNote: () => void;
}

export function useQueuedAction({ base, owner, onAction, reactionCardId, setInput, focusInput }: {
  base: QueueBase;
  owner: string | undefined;
  onAction: (text: string, options?: ActionOptions) => void;
  reactionCardId?: string;
  setInput: (update: string | ((current: string) => string)) => void;
  focusInput: () => void;
}): QueuedActionApi {
  const [queued, setQueued] = useState<QueuedAction | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [liveNote, setLiveNote] = useState<string | null>(null);
  const queuedRef = useRef<QueuedAction | null>(null);
  const sentSeq = useRef<number | null>(null);
  const live = useRef({ base, onAction, reactionCardId, setInput, focusInput, owner });
  useEffect(() => { live.current = { base, onAction, reactionCardId, setInput, focusInput, owner }; });

  const drop = useCallback((gid: string) => {
    queuedRef.current = null; setQueued(null); setLiveNote(null);
    setChatSession(gid, { queued: undefined });
  }, []);

  const giveBack = useCallback((q: QueuedAction, text: string, announce: string) => {
    live.current.setInput(current => mergeDraft(q.text, current));
    setNote(text); setLiveNote(announce);
  }, []);

  // R11: voltou à partida com `queued` gravado → vira rascunho; montar nunca envia.
  useEffect(() => {
    const gid = base.gid;
    const stored = gid ? getChatSession(gid).queued : undefined;
    if (!gid || !stored) return;
    setChatSession(gid, { queued: undefined });
    const text = returnNote("left");
    live.current.setInput(current => mergeDraft(stored, current));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- conversão única no mount
    setNote(text); setLiveNote(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Novo turno: o anúncio de devolução do turno anterior sai da região viva (SPEC-320 R1/R14). Declarado ANTES da
  // decisão: uma devolução do mesmo commit grava depois e vence.
  useEffect(() => {
    if (!queuedRef.current) setLiveNote(null);
  }, [base.seq]);

  // R8: decide no render em que o turno fecha. Limpa a fila ANTES de chamar `onAction` (2ª execução não acha nada).
  useEffect(() => {
    const q = queuedRef.current;
    if (!q) return;
    const cur = live.current;
    const decision = decideQueued(q, { ...cur.base,
      pendingStored: !!cur.owner && !!loadPending(cur.owner, q.gid), online: navigator.onLine !== false });
    if (decision.kind === "wait") return;
    const wasFocusLost = !document.activeElement || document.activeElement === document.body
      || !!document.activeElement.closest(".queued-action");
    drop(q.gid);
    if (decision.kind === "send" && turnLocked()) { // I2: um envio manual saiu primeiro (janela do commit do `state`)
      const text = returnNote("sent-elsewhere");
      giveBack(q, text, text);
      return;
    }
    if (decision.kind === "send") {
      if (sentSeq.current === q.seq) return;
      sentSeq.current = q.seq;
      cur.onAction(q.text, { reaction_card_id: cur.reactionCardId });
      return;
    }
    const reason: ReturnReason = decision.reason;
    const text = returnNote(reason);
    giveBack(q, text, text);
    if (wasFocusLost) cur.focusInput();
  }, [base.busy, base.seq, base.stage, base.delivered, queued, drop, giveBack]);

  const enqueue = useCallback((text: string): boolean => {
    const cur = live.current.base;
    const clean = text.trim();
    if (!canEnqueue(cur, clean) || !cur.gid) return false;
    const replacing = queuedRef.current !== null;
    const q: QueuedAction = { text: clean, seq: cur.seq, gid: cur.gid, combatResultId: cur.combatResultId, choiceId: cur.choiceId };
    queuedRef.current = q; setQueued(q); setNote(null);
    setLiveNote(replacing ? QUEUED_REPLACED : QUEUED_ANNOUNCE);
    setChatSession(cur.gid, { queued: clean });
    return true;
  }, []);

  const remove = useCallback(() => {
    const q = queuedRef.current;
    if (!q) return;
    drop(q.gid);
    giveBack(q, "", QUEUE_REMOVED);
    setNote(null);
    live.current.focusInput();
  }, [drop, giveBack]);

  const clearNote = useCallback(() => { setNote(null); setLiveNote(null); }, []);

  return { queued: queued?.text ?? null, enqueue, remove, note, liveNote, clearNote };
}
