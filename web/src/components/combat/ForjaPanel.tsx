import { useEffect, useRef, useState } from "react";
import type { CardView, ForjaView } from "../../types";
import { forgetChoices, purgeChoices, type RewardSender } from "../../cardRewards";

interface Props {
  forja: ForjaView;
  cards: CardView[];
  busy: boolean;
  onForge: RewardSender;
}

interface Pending { origin: string; text: string; request: Parameters<RewardSender>[0] }

/** SPEC-333 R4/R5/R8 + SPEC-342 R12.3/R17: a Forja do baralho, fora de encontro. O servidor diz o que está permitido
 *  (`forja.permitido`, `esquecer.*`, `purgar.*`). A linha é selecionável e UMA barra de ações abaixo da lista age sobre a
 *  selecionada. Tudo que tira carta ou custa ouro pede um 2º passo inline (sem modal): Confirmar · Cancelar · Esc. */
export function ForjaPanel({ forja, cards, busy, onForge }: Props) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [deckSel, setDeckSel] = useState<string | null>(null);
  const [scarSel, setScarSel] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Pending | null>(null);
  const rootRef = useRef<HTMLElement>(null);
  const locked = busy || pending;
  const nameOf = (id: string) => cards.find((c) => c.id === id)?.name ?? id;

  useEffect(() => {
    if (confirm) rootRef.current?.querySelector<HTMLElement>("[data-forja-confirm]")?.focus();
  }, [confirm]);

  async function run(request: Parameters<RewardSender>[0]) {
    if (locked) return;
    setPending(true);
    setConfirm(null);
    try {
      const out = await onForge(request);
      setMessage(out.message);
    } finally {
      setPending(false);
    }
  }

  function cancel() {
    const origin = confirm?.origin;
    setConfirm(null);
    if (origin) window.setTimeout(() => rootRef.current?.querySelector<HTMLElement>(`[data-forja-origin="${origin}"]`)?.focus(), 0);
  }

  const forget = forgetChoices(forja);
  const purge = purgeChoices(forja);
  const row = forja.baralho.find((r) => r.id === deckSel) ?? null;
  const scar = forja.cicatrizes.find((s) => s.scar_id === scarSel) ?? null;
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- Esc desfaz a confirmação inline (equivalente de teclado do "Cancelar")
    <section className="forja" aria-label="Forja do Baralho" ref={rootRef}
      onKeyDown={(e) => { if (e.key === "Escape" && confirm) { e.stopPropagation(); cancel(); } }}>
      <h3 className="forja__title section-label">Forja do Baralho</h3>
      {!forja.permitido && <p className="forja__why" role="note">{forja.motivo || "Agora não é seguro mexer no Baralho."}</p>}
      <p className="forja__hint">O Baralho precisa de ao menos {forja.baralho_min} Cartas; esquecer não apaga do Acervo.</p>
      <ul className="forja__deck">
        {forja.baralho.map((r) => (
          <li key={r.id}>
            <button type="button" className="forja__row" aria-pressed={deckSel === r.id} data-forja-row={r.id}
              onClick={() => { setDeckSel((cur) => (cur === r.id ? null : r.id)); setConfirm(null); }}>
              <span className="forja__name">{r.name}{r.copias > 1 ? ` ×${r.copias}` : ""}</span>
              {!r.esquecivel && <em className="forja__curse">Cicatriz: só sai com Purgar</em>}
            </button>
          </li>
        ))}
      </ul>
      {row && row.esquecivel && (
        <div className="forja__bar" role="group" aria-label={`Ações para ${row.name}`}>
          {forget.map((choice) => (
            <button key={choice.via} className="btn btn--ghost btn--sm" type="button"
              disabled={locked || !choice.enabled} data-forja-forget={`${row.id}:${choice.via}`} data-forja-origin={`forget:${choice.via}`}
              onClick={() => setConfirm({
                origin: `forget:${choice.via}`,
                text: choice.via === "templo" ? `${row.name} sai do Baralho no templo: ${choice.label}.` : `${row.name} sai do Baralho (segue no Acervo).`,
                request: { kind: "forja", acao: "esquecer", card_id: row.id, via: choice.via },
              })}>
              {choice.label}
            </button>
          ))}
        </div>
      )}
      {forja.afiar.afiaveis.length > 0 && (
        <div className="forja__sharpen">
          <h4 className="section-label">Afiar</h4>
          <p className="forja__hint">
            {forja.afiar.material ? "Consome 1 material raro." : "Falta um material raro."}
          </p>
          <div className="forja__bar">
            {forja.afiar.afiaveis.map((id) => (
              <button key={id} className="btn btn--ghost btn--sm" type="button"
                disabled={locked || !forja.permitido || !forja.afiar.material} data-forja-sharpen={id}
                onClick={() => run({ kind: "forja", acao: "afiar", card_id: id })}>
                Afiar {nameOf(id)}
              </button>
            ))}
          </div>
        </div>
      )}
      {forja.cicatrizes.length > 0 && (
        <div className="forja__scars">
          <h4 className="section-label">Cicatrizes no Baralho</h4>
          <ul className="forja__deck">
            {forja.cicatrizes.map((s) => (
              <li key={s.scar_id}>
                <button type="button" className="forja__row" aria-pressed={scarSel === s.scar_id} data-forja-scar={s.scar_id}
                  onClick={() => { setScarSel((cur) => (cur === s.scar_id ? null : s.scar_id)); setConfirm(null); }}>
                  <span className="forja__name">{s.name}</span>
                </button>
              </li>
            ))}
          </ul>
          {scar && (
            <div className="forja__bar" role="group" aria-label={`Ações para ${scar.name}`}>
              {purge.map((choice) => (
                <button key={choice.via} className="btn btn--ghost btn--sm" type="button"
                  disabled={locked || !choice.enabled} data-forja-purge={`${scar.scar_id}:${choice.via}`} data-forja-origin={`purge:${choice.via}`}
                  onClick={() => setConfirm({
                    origin: `purge:${choice.via}`,
                    text: `Purgar ${scar.name}: ${choice.label}.`,
                    request: { kind: "forja", acao: "purgar", scar_id: scar.scar_id, via: choice.via },
                  })}>
                  {choice.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {confirm && (
        <div className="forja__confirm" role="group" aria-label="Confirmar ação da Forja">
          <span>{confirm.text}</span>
          <button type="button" className="btn btn--primary btn--sm" data-forja-confirm disabled={locked} onClick={() => run(confirm.request)}>Confirmar</button>
          <button type="button" className="btn btn--ghost btn--sm" data-forja-cancel onClick={cancel}>Cancelar</button>
        </div>
      )}
      <p className="forja__msg" role="status" aria-live="polite">{message}</p>
    </section>
  );
}
