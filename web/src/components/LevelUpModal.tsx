import { useState } from "react";
import { motion } from "motion/react";
import type { EligibleAbility, PlayerStats } from "../types";

const VIRTUES: Array<[string, string]> = [
  ["forca", "Força"], ["agilidade", "Agilidade"], ["corpo", "Corpo"],
  ["mente", "Mente"], ["carisma", "Carisma"],
];

export interface LevelUpPick {
  card_id?: string;
  evolve_card_id?: string;
  caminho?: "A" | "B";
  virtude?: string;
  subclass_id?: string;
  virtue_card_id?: string;
}

interface Props {
  player: PlayerStats;
  busy: boolean;
  onChoose: (choiceId: string, pick: LevelUpPick) => void;
  onLater: () => void;
}

export function LevelUpModal({ player, busy, onChoose, onLater }: Props) {
  const choice = player.pending_choices[0];
  const lu = player.level_up ?? {};
  const [picked, setPicked] = useState<LevelUpPick | null>(null);
  if (!choice) return null;

  const isCard = choice.kind === "carta" || choice.kind === "ability";
  const isSubclass = choice.kind === "subclass";
  const isMastery = choice.kind === "virtue_mastery";
  const pickedKey = picked?.card_id
    ?? (picked?.evolve_card_id ? `${picked.evolve_card_id}-${picked.caminho}`
      : picked?.virtude ?? picked?.subclass_id ?? picked?.virtue_card_id);
  const title = isSubclass ? "Escolha sua subclasse"
    : isMastery ? "Aprofunde uma Carta de Virtude"
      : isCard ? "Expanda seu Acervo" : "Fortaleça uma Virtude";

  return (
    <div className="overlay overlay--levelup" role="dialog" aria-modal="true">
      <motion.div className="lvlup" initial={{ opacity: 0, y: 14, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}>
        <p className="lvlup__kicker">Nível {choice.level} alcançado</p>
        <h2 className="lvlup__title">{title}</h2>

        {isSubclass ? (
          <div className="lvlup__groups">
            <p>Esta escolha é permanente nesta linha do tempo e define suas Cartas de ramo.</p>
            <ul className="lvlup__list">
              {(lu.subclasses ?? []).map((subclass) => (
                <li key={subclass.id}>
                  <button type="button"
                    className={`lvlup__card${pickedKey === subclass.id ? " is-picked" : ""}`}
                    onClick={() => setPicked({ subclass_id: subclass.id })}>
                    <span className="lvlup__card-top"><b>{subclass.name}</b></span>
                    <span className="lvlup__desc">{subclass.identity}</span>
                    <span className="lvlup__desc">{subclass.playstyle}</span>
                    <span className="lvlup__desc">Contrapartida: {subclass.tradeoff}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : isMastery ? (
          <div className="lvlup__attrs">
            {(lu.virtue_cards ?? []).map((card) => (
              <button key={card.card_id} type="button"
                className={`lvlup__attr${pickedKey === card.card_id ? " is-picked" : ""}`}
                disabled={card.mastery >= 2}
                onClick={() => setPicked({ virtue_card_id: card.card_id })}>
                <b>{card.card_id}</b>
                <span>Maestria {card.mastery} → {Math.min(2, card.mastery + 1)}</span>
              </button>
            ))}
          </div>
        ) : isCard ? (
          <div className="lvlup__groups">
            {(lu.eligible ?? []).length > 0 && (
              <section className="lvlup__group">
                <h3 className="lvlup__branch">Aprender uma Carta</h3>
                <ul className="lvlup__list">
                  {(lu.eligible ?? []).map((card) => (
                    <CardChoice key={card.id} card={card} picked={pickedKey === card.id}
                      onPick={() => setPicked({ card_id: card.id })} />
                  ))}
                </ul>
              </section>
            )}
            {(lu.evolvable ?? []).length > 0 && (
              <section className="lvlup__group lvlup__group--branch">
                <h3 className="lvlup__branch">Evoluir uma Carta</h3>
                <ul className="lvlup__list">
                  {(lu.evolvable ?? []).map((card) => (
                    <li key={card.id} className="lvlup__evolve">
                      <b>{card.name}</b>
                      <div>
                        {(["A", "B"] as const).map((path) => (
                          <button key={path} type="button"
                            className={pickedKey === `${card.id}-${path}` ? "is-picked" : ""}
                            onClick={() => setPicked({ evolve_card_id: card.id, caminho: path })}>
                            Caminho {path}
                          </button>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        ) : (
          <div className="lvlup__attrs">
            {VIRTUES.map(([key, label]) => (
              <button key={key} type="button"
                className={`lvlup__attr${pickedKey === key ? " is-picked" : ""}`}
                disabled={(player.virtudes?.[key as keyof PlayerStats["virtudes"]] ?? 0) >= 5}
                onClick={() => setPicked({ virtude: key })}>
                <b>{label}</b>
                <span>{player.virtudes?.[key as keyof PlayerStats["virtudes"]] ?? 0} → +1</span>
              </button>
            ))}
          </div>
        )}

        <div className="lvlup__actions">
          <button className="btn" type="button" onClick={onLater}
            disabled={busy || isSubclass}>Depois</button>
          <button className="btn btn--primary" type="button" disabled={busy || !picked}
            onClick={() => picked && onChoose(choice.id, picked)}>
            {busy ? "…" : "Confirmar"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function CardChoice({ card, picked, onPick }: {
  card: EligibleAbility; picked: boolean; onPick: () => void;
}) {
  return (
    <li>
      <button type="button" className={`lvlup__card${picked ? " is-picked" : ""}`} onClick={onPick}>
        <span className="lvlup__card-top">
          <b>{card.name}</b>
          <span className="lvlup__tier">
            {card.tier_label ?? `Tier ${card.tier}`} · Nv. {card.level_req ?? 1} · {card.cost}E · {card.frequency ?? "livre"}
          </span>
        </span>
        <span className="lvlup__desc">{card.description}</span>
      </button>
    </li>
  );
}
