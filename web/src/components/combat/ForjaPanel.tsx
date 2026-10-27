import { useState } from "react";
import type { CardView, ForjaView } from "../../types";
import { forgetChoices, purgeChoices, type RewardSender } from "../../cardRewards";

interface Props {
  forja: ForjaView;
  cards: CardView[];
  busy: boolean;
  onForge: RewardSender;
}

/** SPEC-333 R4/R5/R8: a Forja do baralho, fora de encontro. O servidor diz o que está permitido
 *  (`forja.permitido`, `esquecer.*`, `purgar.*`); aqui só há botões e a mensagem de volta. */
export function ForjaPanel({ forja, cards, busy, onForge }: Props) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const locked = busy || pending;
  const nameOf = (id: string) => cards.find((c) => c.id === id)?.name ?? id;

  async function run(request: Parameters<RewardSender>[0]) {
    if (locked) return;
    setPending(true);
    try {
      const out = await onForge(request);
      setMessage(out.message);
    } finally {
      setPending(false);
    }
  }

  const forget = forgetChoices(forja);
  const purge = purgeChoices(forja);
  return (
    <section className="forja" aria-label="Forja do Baralho">
      <h2 className="forja__title">Forja do Baralho</h2>
      {!forja.permitido && <p className="forja__why" role="note">{forja.motivo || "Agora não é seguro mexer no Baralho."}</p>}
      <p className="forja__hint">O Baralho precisa de ao menos {forja.baralho_min} Cartas; esquecer não apaga do Acervo.</p>
      <ul className="forja__deck">
        {forja.baralho.map((row) => (
          <li key={row.id} className="forja__row">
            <span className="forja__name">{row.name}{row.copias > 1 ? ` ×${row.copias}` : ""}</span>
            <span className="forja__actions">
              {row.esquecivel ? forget.map((choice) => (
                <button key={choice.via} className="btn btn--ghost" type="button"
                  disabled={locked || !choice.enabled} data-forja-forget={`${row.id}:${choice.via}`}
                  onClick={() => run({ kind: "forja", acao: "esquecer", card_id: row.id, via: choice.via })}>
                  {choice.label}
                </button>
              )) : <em className="forja__curse">Cicatriz: só sai com Purgar</em>}
            </span>
          </li>
        ))}
      </ul>
      {forja.afiar.afiaveis.length > 0 && (
        <div className="forja__sharpen">
          <h3>Afiar</h3>
          <p className="forja__hint">
            {forja.afiar.material ? "Consome 1 material raro." : "Falta um material raro."}
          </p>
          {forja.afiar.afiaveis.map((id) => (
            <button key={id} className="btn btn--ghost" type="button"
              disabled={locked || !forja.permitido || !forja.afiar.material} data-forja-sharpen={id}
              onClick={() => run({ kind: "forja", acao: "afiar", card_id: id })}>
              Afiar {nameOf(id)}
            </button>
          ))}
        </div>
      )}
      {forja.cicatrizes.length > 0 && (
        <div className="forja__scars">
          <h3>Cicatrizes no Baralho</h3>
          {forja.cicatrizes.map((scar) => (
            <div key={scar.scar_id} className="forja__row">
              <span className="forja__name">{scar.name}</span>
              <span className="forja__actions">
                {purge.map((choice) => (
                  <button key={choice.via} className="btn btn--ghost" type="button"
                    disabled={locked || !choice.enabled} data-forja-purge={`${scar.scar_id}:${choice.via}`}
                    onClick={() => run({ kind: "forja", acao: "purgar", scar_id: scar.scar_id, via: choice.via })}>
                    {choice.label}
                  </button>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="forja__msg" role="status" aria-live="polite">{message}</p>
    </section>
  );
}
