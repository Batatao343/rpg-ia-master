import { useEffect, useRef, useState } from "react";
import type { ImageQuote } from "../api";
import { shards } from "./AccountScreen";

export function ImageQuoteDialog({ quote, busy, error, onConfirm, onCancel }: {
  quote: ImageQuote; busy: boolean; error: string;
  onConfirm: () => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    cancelRef.current?.focus(); // ação segura (Cancelar) recebe o foco inicial
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { window.clearInterval(timer); node?.close(); };
  }, [quote.quote_id]);
  const expired = now >= Date.parse(quote.expires_at);
  const cost = shards(quote.credits_milli);
  const monster = quote.type === "monster";
  return <dialog ref={dialog} className="image-quote-dialog" aria-labelledby="image-quote-title"
    aria-describedby="image-quote-cost" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="image-quote-title">{monster ? "Gerar retrato" : quote.reformulation ? "Reformular imagem" : "Encomendar imagem"}</h2>
    <p id="image-quote-cost">Custo máximo: <strong>{cost} Estilhas</strong>.</p>
    <p>Ao confirmar, esse saldo fica reservado para uma geração. O débito será limitado a esse valor.</p>
    {monster && <p>A imagem fica num registro compartilhado: outros jogadores poderão vê-la sem custo. Se a geração falhar antes de começar, o saldo é liberado.</p>}
    <p>Válido até {new Date(quote.expires_at).toLocaleTimeString("pt-BR")}.</p>
    {expired && <p role="status">Cotação expirada. Feche e solicite uma nova cotação.</p>}
    {error && <p role="alert">{error}</p>}
    <div className="image-quote-actions">
      <button type="button" className="btn btn--ghost" disabled={busy} onClick={onCancel} ref={cancelRef}>Cancelar</button>
      <button type="button" className="btn" disabled={busy || expired} onClick={onConfirm}>
        {busy ? "Reservando…" : `Confirmar até ${cost} Estilhas`}
      </button>
    </div>
  </dialog>;
}
