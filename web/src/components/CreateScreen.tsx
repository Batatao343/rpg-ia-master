import { useEffect, useState } from "react";
import * as api from "../api";
import type { CreateOptions, CreatePayload, GameResponse } from "../types";

const LEVELS = [
  { v: 1, label: "Iniciante · 1" },
  { v: 3, label: "Aventureiro · 3" },
  { v: 5, label: "Veterano · 5" },
  { v: 10, label: "Herói · 10" },
  { v: 20, label: "Lenda · 20" },
];

interface Props {
  busy: boolean;
  continueData: GameResponse | null;
  onCreate: (payload: CreatePayload) => void;
  onContinue: () => void;
  onError: (msg: string) => void;
}

export function CreateScreen({ busy, continueData, onCreate, onContinue, onError }: Props) {
  const [opts, setOpts] = useState<CreateOptions>({ races: [], classes: [], regions: [] });
  const [name, setName] = useState("");
  const [race, setRace] = useState("");
  const [className, setClassName] = useState("");
  const [region, setRegion] = useState("");
  const [level, setLevel] = useState(1);
  const [backstory, setBackstory] = useState("");

  useEffect(() => {
    api
      .getOptions()
      .then((o) => {
        setOpts(o);
        setRace((r) => r || o.races[0] || "");
        setClassName((c) => c || o.classes[0] || "");
        setRegion((rg) => rg || o.regions[0] || "");
      })
      .catch((e) =>
        onError("Não consegui carregar as opções. A API está rodando? (" + (e?.message || e) + ")"),
      );
  }, [onError]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onCreate({
      name: name.trim() || "Herói",
      race,
      class_name: className,
      region,
      level,
      backstory: backstory.trim(),
    });
  }

  return (
    <main className="create">
      <div className="create__frame">
        <header className="create__head">
          <p className="kicker">Dark Fantasy · Narração por IA</p>
          <h1 className="create__title">Forje sua lenda</h1>
          <p className="create__sub">
            Um mundo sombrio aguarda. Defina quem caminha nele — o resto, a história escreve.
          </p>
        </header>

        <form className="form" autoComplete="off" onSubmit={submit}>
          <div className="field">
            <label htmlFor="f-name">Nome do herói</label>
            <input
              id="f-name"
              type="text"
              placeholder="Ex.: Valerius"
              maxLength={40}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="form__row">
            <div className="field">
              <label htmlFor="f-race">Origem (raça)</label>
              <select id="f-race" value={race} onChange={(e) => setRace(e.target.value)}>
                {opts.races.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="f-class">Vocação (classe)</label>
              <select id="f-class" value={className} onChange={(e) => setClassName(e.target.value)}>
                {opts.classes.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="field">
            <label htmlFor="f-region">Região inicial</label>
            <select id="f-region" value={region} onChange={(e) => setRegion(e.target.value)}>
              {opts.regions.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>Nível inicial</label>
            <div className="segmented" role="radiogroup" aria-label="Nível inicial">
              {LEVELS.map((l) => (
                <button
                  type="button"
                  key={l.v}
                  className="seg"
                  aria-pressed={level === l.v}
                  onClick={() => setLevel(l.v)}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label htmlFor="f-back">
              Passado <span className="muted">(opcional)</span>
            </label>
            <textarea
              id="f-back"
              rows={2}
              maxLength={280}
              placeholder="Uma linha sobre de onde você veio e o que carrega."
              value={backstory}
              onChange={(e) => setBackstory(e.target.value)}
            />
          </div>

          <div className="form__actions">
            {continueData && (
              <button type="button" className="btn btn--ghost" onClick={onContinue}>
                Continuar jornada anterior
              </button>
            )}
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {busy ? "Forjando…" : "Começar a jornada"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
