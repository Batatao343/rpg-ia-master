import { useRef, useState } from "react";
import * as api from "../api";
import { errMsg, errRequestId } from "../lib/errorMessages";
import { portraitErrorBanner, shouldHidePortraitOffer, withinShownPrice, withoutPortraitOffer, withPortraitPending, withPortraitRestored, snapshotPortraits } from "../lib/portraitOrder";
import type { AppCore } from "./core";

/** Cotação de imagem / retrato pago (SPEC-326, 352, 367, 387). Movido de `App.tsx` sem mudar corpo (SPEC-383). */
export function useImageQuote(core: AppCore, refreshBalance: (expectedOwner: string, generation: number) => Promise<void>) {
  const { session, owner, data, setData, setBanner, authRequired } = core;
  const [imageQuote, setImageQuote] = useState<{ quote: api.ImageQuote; gameId: string; session: number; actionId: string; enemyId?: string } | null>(null);
  const portraitSnapshot = useRef<{ gameId: string; enemyId: string; shot: Record<string, unknown> } | null>(null); // SPEC-387 R8
  const portraitInFlight = useRef(false); // SPEC-367 R5: trava síncrona (React state não pega 2 cliques no mesmo tick)
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState("");

  function resetImageQuote() {
    setImageQuote(null);
    setImageBusy(false);
    setImageError("");
  }

  async function openImageQuote(id: string, type: api.ImageQuote["type"] = "player", reformulation = false, offerId?: string) {
    const generation = session.current;
    setImageBusy(true); setImageError("");
    try {
      const quote = await api.requestImageQuote(id, type, reformulation, offerId);
      if (session.current === generation) setImageQuote({ quote, gameId: id, session: generation, actionId: crypto.randomUUID() });
    } catch (error) {
      if (session.current === generation) setBanner({ msg: "Cotação indisponível: " + errMsg(error), kind: "warn", requestId: errRequestId(error) });
    } finally { if (session.current === generation) setImageBusy(false); }
  }

  /** SPEC-352 R12: retrato pago de inimigo. O "Gerar" inline já foi o consentimento; se a cotação real não passa
   *  do preço mostrado, confirma direto (sem 2º modal). Cotação maior abre o diálogo da 326 com o preço real. */
  async function handleGeneratePortrait(enemyId: string, shownShards: number, shownMilli?: string) {
    const gameId = data?.game_id;
    if (!gameId || imageBusy || portraitInFlight.current) return;
    portraitInFlight.current = true;
    const generation = session.current;
    setImageBusy(true); setImageError("");
    // SPEC-387 R8: o chip vira "Gerando retrato…" no mesmo frame; erro/cancelamento devolve o retrato anterior.
    portraitSnapshot.current = { gameId, enemyId, shot: snapshotPortraits(data, enemyId) };
    setData(prev => (prev?.game_id === gameId ? withPortraitPending(prev, enemyId) : prev));
    try {
      const quote = await api.requestImageQuote(gameId, "monster", false, undefined, enemyId);
      if (session.current !== generation) return;
      const current = { quote, gameId, session: generation, actionId: crypto.randomUUID(), enemyId };
      if (withinShownPrice(quote.credits_milli, shownShards, shownMilli)) await confirmImageQuote(current, true);
      else setImageQuote(current);
    } catch (error) {
      if (session.current === generation) {
        const status = error instanceof api.HttpError ? error.status : undefined;
        const code = error instanceof api.HttpError ? error.code : undefined;
        restorePortrait();
        if (shouldHidePortraitOffer(status, code)) setData(prev => (prev?.game_id === gameId ? withoutPortraitOffer(prev, enemyId) : prev));
        setBanner({ ...portraitErrorBanner(status, code, "Cotação indisponível: " + errMsg(error)), requestId: errRequestId(error) });
      }
    } finally { portraitInFlight.current = false; if (session.current === generation) setImageBusy(false); }
  }

  /** SPEC-387 R8: devolve o `retrato` guardado (erro, cancelamento ou "Agora não"); no-op sem pedido em curso. */
  function restorePortrait() {
    const snap = portraitSnapshot.current;
    portraitSnapshot.current = null;
    if (snap) setData(prev => (prev?.game_id === snap.gameId ? withPortraitRestored(prev, snap.enemyId, snap.shot) : prev));
  }

  async function confirmImageQuote(direct?: typeof imageQuote, inline = false) {
    const current = direct ?? imageQuote;
    if (!current || (imageBusy && !inline) || current.session !== session.current) return;
    setImageBusy(true); setImageError("");
    try {
      const art = await api.confirmPlayerArt(current.gameId, current.actionId, current.quote.quote_id);
      if (session.current !== current.session) return;
      setData(prev => prev?.game_id === current.gameId ? (current.quote.type === "monster" && current.enemyId
        ? withPortraitPending(prev, current.enemyId) : prev) : prev);
      setData(prev => prev?.game_id === current.gameId ? {
        ...prev,
        portrait_generation_id: art.generation_id && current.quote.type === "player"
          ? art.generation_id : prev.portrait_generation_id,
        art_generations: art.art_generations ?? prev.art_generations,
        art_offers: art.art_offers ?? prev.art_offers,
      } : prev);
      setImageQuote(null);
      portraitSnapshot.current = null; // confirmado: o servidor já está "gerando"
      setBanner({
        msg: current.quote.type === "monster" ? "Retrato encomendado. O saldo foi reservado."
          : "Imagem confirmada. O saldo foi reservado e a geração será processada.",
        kind: "info",
      });
      if (authRequired) void refreshBalance(owner.current, current.session);
    } catch (error) {
      if (session.current !== current.session) return;
      if (current.quote.type === "monster") {
        // 409/402/503 do retrato: aviso curto (nada cobrado); o diálogo, se aberto, fecha.
        const status = error instanceof api.HttpError ? error.status : undefined;
        const code = error instanceof api.HttpError ? error.code : undefined;
        setImageQuote(null);
        restorePortrait();
        setBanner({ ...portraitErrorBanner(status, code, "Não foi possível confirmar: " + errMsg(error)), requestId: errRequestId(error) });
      } else setImageError("Não foi possível confirmar: " + errMsg(error));
    } finally { if (session.current === current.session) setImageBusy(false); }
  }

  return { imageQuote, setImageQuote, imageBusy, imageError, resetImageQuote, openImageQuote,
    handleGeneratePortrait, confirmImageQuote, restorePortrait };
}
