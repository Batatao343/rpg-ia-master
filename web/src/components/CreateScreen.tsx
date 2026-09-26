import { useEffect, useMemo, useState } from "react";
import * as api from "../api";
import type {
  CreateOptions,
  CreatePayload,
  GameResponse,
  OnboardingData,
  RaceTrait,
  StartScenario,
} from "../types";
import { Frame, Divider, Medallion } from "./ornaments";
import { VisualArtwork } from "./VisualArtwork";

const LEVELS = [
  { v: 1, label: "Iniciante · 1" },
  { v: 3, label: "Aventureiro · 3" },
  { v: 5, label: "Veterano · 5" },
  { v: 10, label: "Herói · 10" },
  { v: 20, label: "Lenda · 20" },
];

// spec onboarding-valoria (R5): wizard de 5 passos com navegação livre
const STEPS = ["O Mundo", "Origem", "Vocação", "Região", "Identidade"];

const ATTR_LABELS: Record<string, string> = {
  str: "FOR", dex: "DES", con: "CON", int: "INT", wis: "SAB", cha: "CAR",
};

// Resume os efeitos mecânicos ativos de um trait em chips curtos.
function traitEffectChips(t: RaceTrait): string[] {
  const chips: string[] = [];
  const eff = t.effects || {};
  const attrs = eff["attr_bonus"] as Record<string, number> | undefined;
  if (attrs) for (const [k, v] of Object.entries(attrs)) chips.push(`+${v} ${ATTR_LABELS[k] || k.toUpperCase()}`);
  const saves = eff["save_bonus"] as Record<string, number> | undefined;
  if (saves) for (const [k, v] of Object.entries(saves)) chips.push(`+${v} save ${ATTR_LABELS[k] || k.toUpperCase()}`);
  if (typeof eff["mana_bonus"] === "number") chips.push(`+${eff["mana_bonus"]} Mana`);
  if (typeof eff["stamina_bonus"] === "number") chips.push(`+${eff["stamina_bonus"]} Vigor`);
  if (typeof eff["defense_bonus"] === "number") chips.push(`+${eff["defense_bonus"]} Defesa`);
  if (typeof eff["gold_bonus"] === "number") chips.push(`+${eff["gold_bonus"]} ouro`);
  const resists = eff["condition_resist"] as string[] | undefined;
  if (resists?.length) chips.push(`resiste: ${[...new Set(resists.map((r) => r.normalize("NFC")))].slice(0, 3).join(", ")}`);
  const items = eff["start_items"] as string[] | undefined;
  if (items?.length) chips.push(...items);
  return chips;
}

interface Props {
  busy: boolean;
  continueData: GameResponse | null;
  onCreate: (payload: CreatePayload) => void;
  onContinue: () => void;
  onSimulate: () => void;
  onError: (msg: string) => void;
}

export function CreateScreen({ busy, continueData, onCreate, onContinue, onSimulate, onError }: Props) {
  const [opts, setOpts] = useState<CreateOptions>({ races: [], classes: [], regions: [] });
  const [lore, setLore] = useState<OnboardingData | null>(null);
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [race, setRace] = useState("");
  const [className, setClassName] = useState("");
  const [region, setRegion] = useState("");
  const [level, setLevel] = useState(1);
  const [backstory, setBackstory] = useState("");
  const [appearance, setAppearance] = useState("");
  const [visualExclusions, setVisualExclusions] = useState("");
  const [artBrief, setArtBrief] = useState("");
  const [artBriefBusy, setArtBriefBusy] = useState(false);
  const [generatePortrait, setGeneratePortrait] = useState(false);
  // spec inicio-personalizado (R9): passo 6 — prólogo confirmável
  const [scenario, setScenario] = useState<StartScenario | null>(null);
  const [prologueBusy, setPrologueBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.getOptions(), api.getOnboarding().catch(() => null)])
      .then(([o, ob]) => {
        setOpts(o);
        setLore(ob);
        setRace((r) => r || o.races[0] || "");
        setClassName((c) => c || o.classes[0] || "");
        setRegion((rg) => rg || o.regions[0] || "");
      })
      .catch((e) =>
        onError("Não consegui carregar as opções. A API está rodando? (" + (e?.message || e) + ")"),
      );
  }, [onError]);

  // Cards de raça na ordem canônica de origins.json (chaveados por id no lore)
  const raceCards = useMemo(() => {
    if (!lore) return [];
    return (opts.races_full || []).map((r) => ({ full: r, card: lore.races[r.id] }));
  }, [lore, opts]);

  const regionCards = useMemo(() => (lore ? Object.entries(lore.regions) : []), [lore]);

  function payload(): CreatePayload {
    return {
      name: name.trim() || "Herói",
      race,
      class_name: className,
      region,
      level,
      backstory: backstory.trim(),
      appearance: appearance.trim(),
      visual_exclusions: visualExclusions.trim(),
      generate_portrait: generatePortrait && !!artBrief,
    };
  }

  // Fallback: sem lore (arquivo/endpoint indisponível), mantém o formulário clássico
  const wizard = !!lore;

  // Passo 5 → 6: gera o prólogo (1 chamada SMART no servidor) e mostra a
  // tela de confirmação. Falha → volta ao passo 5 com aviso (nunca trava).
  async function requestPrologue() {
    setStep(5);
    setPrologueBusy(true);
    setScenario(null);
    try {
      const r = await api.postPrologue(payload());
      setScenario(r.scenario);
    } catch (e) {
      onError("O prólogo falhou: " + ((e as Error)?.message || e));
      setStep(4);
    } finally {
      setPrologueBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (wizard) {
      void requestPrologue();
    } else {
      onCreate(payload());
    }
  }

  async function reviewArtBrief() {
    setArtBriefBusy(true);
    try {
      const result = await api.postArtBrief({
        name: name.trim() || "Herói", race, class_name: className, region,
        appearance, visual_exclusions: visualExclusions,
      });
      setArtBrief(result.rendered_prompt);
    } catch (error) {
      onError("Não consegui montar o brief visual: " + ((error as Error)?.message || error));
    } finally {
      setArtBriefBusy(false);
    }
  }

  const canNext = step === 1 ? !!race : step === 2 ? !!className : step === 3 ? !!region : true;

  return (
    <main className="create">
      <Frame className={"create__frame" + (wizard && step >= 1 && step <= 3 ? " create__frame--wide" : "")}>
        <div className="create__seal"><Medallion size={48} /></div>
        <header className="create__head">
          <p className="kicker">Dark Fantasy · Narração por IA</p>
          <h1 className="create__title">Forje sua lenda</h1>
          {(!wizard || step === 0) && (
            <p className="create__sub">
              Um mundo sombrio aguarda. Defina quem caminha nele — o resto, a história escreve.
            </p>
          )}
        </header>

        <button
          type="button"
          className="simulator-shortcut"
          disabled={busy}
          onClick={onSimulate}
        >
          <span aria-hidden>⚔</span>
          <span><strong>Simular combate</strong><small>Entrar direto na arena · zero LLM</small></span>
        </button>

        {wizard && step < 5 && (
          <nav className="wizard__steps" aria-label="Passos da criação">
            {STEPS.map((label, i) => (
              <button
                key={label}
                type="button"
                className="wizard__step"
                aria-current={step === i ? "step" : undefined}
                onClick={() => setStep(i)}
              >
                <span className="wizard__stepnum">{i + 1}</span>
                <span className="wizard__steplabel">{label}</span>
              </button>
            ))}
          </nav>
        )}

        <Divider />

        {wizard && step === 0 && (
          <section className="wizard__intro">
            <h2 className="wizard__title">{lore.world_intro.title}</h2>
            {lore.world_intro.paragraphs.map((p, i) => (
              <p key={i} className="wizard__para">{p}</p>
            ))}
            <div className="form__actions">
              <button type="button" className="btn btn--primary" onClick={() => setStep(1)}>
                Continuar
              </button>
              <button type="button" className="btn btn--ghost" onClick={() => setStep(1)}>
                Pular introdução
              </button>
              {continueData && (
                <button type="button" className="btn btn--ghost" onClick={onContinue}>
                  Continuar jornada anterior
                </button>
              )}
            </div>
          </section>
        )}

        {wizard && step === 1 && (
          <section>
            <h2 className="wizard__title">Quem você é?</h2>
            <div className="cards" role="radiogroup" aria-label="Origem (raça)">
              {raceCards.map(({ full, card }) => (
                <article
                  key={full.id}
                  className="card"
                  data-selected={race === full.name}
                >
                  <VisualArtwork asset={opts.visuals?.races?.[full.id] ?? null}
                    name={card?.name || full.name} className="card__art" variant="card" />
                  <button type="button" className="card__name card__select" aria-pressed={race === full.name}
                    onClick={() => setRace(full.name)}>{card?.name || full.name}</button>
                  <span className="card__tagline">{card?.tagline || full.desc}</span>
                  {card && <span className="card__desc">{card.description}</span>}
                  <span className="card__chips">
                    {(full.traits || []).map((t) => (
                      <span key={t.id} className="chip" title={t.desc}>{t.name}</span>
                    ))}
                    {(full.traits || []).flatMap(traitEffectChips).map((c, i) => (
                      <span key={"e" + i} className="chip chip--mech">{c}</span>
                    ))}
                  </span>
                </article>
              ))}
            </div>
          </section>
        )}

        {wizard && step === 2 && (
          <section>
            <h2 className="wizard__title">Como você sobrevive?</h2>
            <div className="cards" role="radiogroup" aria-label="Vocação (classe)">
              {opts.classes.map((cls) => {
                const card = lore.classes[cls];
                return (
                  <article
                    key={cls}
                    className="card"
                    data-selected={className === cls}
                  >
                    <VisualArtwork asset={opts.visuals?.classes?.[cls] ?? null}
                      name={cls} className="card__art" variant="card" />
                    <button type="button" className="card__name card__select" aria-pressed={className === cls}
                      onClick={() => setClassName(cls)}>{cls}</button>
                    {card && (
                      <>
                        <span className="card__tagline">{card.tagline}</span>
                        <span className="card__desc">{card.description}</span>
                        <span className="card__hook">{card.playstyle}</span>
                      </>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        )}

        {wizard && step === 3 && (
          <section>
            <h2 className="wizard__title">De onde você vem?</h2>
            <div className="cards" role="radiogroup" aria-label="Região inicial">
              {regionCards.map(([rid, card]) => (
                <button
                  key={rid}
                  type="button"
                  className="card"
                  aria-pressed={region === card.name}
                  onClick={() => setRegion(card.name)}
                >
                  <span className="card__name">{card.name}</span>
                  <span className="card__tagline">{card.tagline}</span>
                  <span className="card__desc">{card.description}</span>
                  <span className="card__hook">{card.hook}</span>
                  <span className="card__chips"><span className="chip chip--mech">{card.bonus}</span></span>
                </button>
              ))}
            </div>
          </section>
        )}

        {(!wizard || step === 4) && (
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

            {!wizard && (
              <>
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
              </>
            )}

            {wizard && (
              <p className="wizard__summary">
                {race} · {className} · {region}
              </p>
            )}

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
                Quem é você? <span className="muted">(opcional)</span>
              </label>
              <textarea
                id="f-back"
                rows={3}
                maxLength={2000}
                placeholder="De onde veio, o que busca, o que deixou para trás? Sua descrição molda o início da história."
                value={backstory}
                onChange={(e) => setBackstory(e.target.value)}
              />
            </div>

            <div className="field">
              <label htmlFor="f-appearance">
                Aparência visual <span className="muted">(opcional, não altera mecânica)</span>
              </label>
              <textarea id="f-appearance" rows={3} maxLength={1000}
                placeholder="Descreva idade adulta, pele, cabelo, corpo, roupas, cicatrizes e detalhes que devem ser preservados."
                value={appearance} onChange={(e) => { setAppearance(e.target.value); setArtBrief(""); setGeneratePortrait(false); }} />
            </div>
            <div className="field">
              <label htmlFor="f-visual-exclusions">O que não deve aparecer</label>
              <input id="f-visual-exclusions" maxLength={500}
                placeholder="Ex.: sem elmo, sem capa, sem pose acrobática"
                value={visualExclusions}
                onChange={(e) => { setVisualExclusions(e.target.value); setArtBrief(""); setGeneratePortrait(false); }} />
            </div>
            <button type="button" className="btn btn--ghost" disabled={artBriefBusy}
              onClick={() => void reviewArtBrief()}>
              {artBriefBusy ? "Adaptando…" : "Revisar brief visual (sem gerar/cobrar)"}
            </button>
            {artBrief && (
              <>
                <details className="field" open>
                  <summary>Brief adaptado às âncoras de Valoria</summary>
                  <pre className="wizard__para">{artBrief}</pre>
                </details>
                <label className="field">
                  <span>
                    <input type="checkbox" checked={generatePortrait}
                      onChange={(event) => setGeneratePortrait(event.target.checked)} />{" "}
                    Confirmo a geração do retrato com GPT Image
                  </span>
                  <small className="muted">
                    Esta chamada pode ter custo no provedor. O jogo continua normalmente se estiver desativada ou falhar.
                  </small>
                </label>
              </>
            )}

            <div className="form__actions">
              {continueData && (
                <button type="button" className="btn btn--ghost" onClick={onContinue}>
                  Continuar jornada anterior
                </button>
              )}
              {wizard && (
                <button type="button" className="btn btn--ghost" onClick={() => setStep(3)}>
                  Voltar
                </button>
              )}
              <button type="submit" className="btn btn--primary" disabled={busy || prologueBusy}>
                {wizard
                  ? prologueBusy ? "Tecendo…" : "Tecer o prólogo"
                  : busy ? "Forjando…" : "Começar a jornada"}
              </button>
            </div>
          </form>
        )}

        {wizard && step === 5 && (
          <section className="prologue">
            {prologueBusy || !scenario ? (
              <div className="prologue__loading" role="status">
                <p className="wizard__title">O destino tece seu prólogo…</p>
                <p className="wizard__para prologue__pulse">
                  {name.trim() || "Herói"} · {race} · {className} · {region}
                </p>
              </div>
            ) : (
              <>
                <h2 className="wizard__title">{scenario.arc_title}</h2>
                <p className="wizard__summary">
                  {name.trim() || "Herói"} · {race} · {className} · nível {level} · {region}
                </p>
                {scenario.prologue.split(/\n+/).map((p, i) => (
                  <p key={i} className="wizard__para prologue__text">{p}</p>
                ))}
                {scenario.seed_npcs.length > 0 && (
                  <div className="prologue__npcs">
                    {scenario.seed_npcs.map((n) => (
                      <span key={n.name} className="chip" title={n.persona}>
                        {n.name} — {n.role}
                      </span>
                    ))}
                  </div>
                )}
                <div className="form__actions">
                  <button
                    type="button"
                    className="btn btn--primary"
                    disabled={busy}
                    onClick={() => onCreate({ ...payload(), scenario })}
                  >
                    {busy ? "Forjando…" : "Começar a jornada"}
                  </button>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={busy}
                    onClick={() => setStep(4)}
                  >
                    Refinar história
                  </button>
                </div>
              </>
            )}
          </section>
        )}

        {wizard && step > 0 && step < 4 && (
          <div className="form__actions wizard__nav">
            {continueData && (
              <button type="button" className="btn btn--ghost" onClick={onContinue}>
                Continuar jornada anterior
              </button>
            )}
            <button type="button" className="btn btn--ghost" onClick={() => setStep(step - 1)}>
              Voltar
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!canNext}
              onClick={() => setStep(step + 1)}
            >
              Continuar
            </button>
          </div>
        )}
      </Frame>
    </main>
  );
}
