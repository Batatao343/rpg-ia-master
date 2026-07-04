import { useMemo, useState } from "react";
import { motion } from "motion/react";
import type { EligibleAbility, PlayerStats } from "../types";

const ATTRS: Array<[string, string]> = [
  ["str", "Força"], ["dex", "Destreza"], ["con", "Constituição"],
  ["int", "Inteligência"], ["wis", "Sabedoria"], ["cha", "Carisma"],
];

interface Props {
  player: PlayerStats;
  busy: boolean;
  onChoose: (choiceId: string, pick: { ability_id?: string; attr?: string }) => void;
  onLater: () => void;
}

/** Fase 4.1: modal de level up — a escolha de ramo é a escolha de SUBCLASSE
 *  (irreversível: aprender de um ramo tranca o rival), então o modal apresenta
 *  os ramos com nome/tema, não uma lista chapada. */
export function LevelUpModal({ player, busy, onChoose, onLater }: Props) {
  const choice = player.pending_choices[0];
  const lu = player.level_up ?? {};
  const [picked, setPicked] = useState<string | null>(null);

  const groups = useMemo(() => {
    const eligible = lu.eligible ?? [];
    const trunk = eligible.filter((a) => !a.branch);
    const byBranch = new Map<string, EligibleAbility[]>();
    for (const a of eligible) {
      if (!a.branch) continue;
      const arr = byBranch.get(a.branch) ?? [];
      arr.push(a);
      byBranch.set(a.branch, arr);
    }
    return { trunk, byBranch };
  }, [lu.eligible]);

  if (!choice) return null;
  const isAbility = choice.kind === "ability";
  const branches = lu.branches ?? {};
  const lockedIn = lu.current_branch ?? null;

  return (
    <div className="overlay overlay--levelup" role="dialog" aria-modal="true">
      <motion.div
        className="lvlup"
        initial={{ opacity: 0, y: 14, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      >
        <p className="lvlup__kicker">Nível {choice.level} alcançado</p>
        <h2 className="lvlup__title">
          {isAbility ? "Escolha uma habilidade" : "Fortaleça um atributo"}
        </h2>

        {isAbility ? (
          <div className="lvlup__groups">
            {groups.trunk.length > 0 && (
              <section className="lvlup__group">
                <h3 className="lvlup__branch">Caminho comum</h3>
                <ul className="lvlup__list">
                  {groups.trunk.map((a) => (
                    <AbilityCard key={a.id} a={a} picked={picked === a.id}
                                 onPick={() => setPicked(a.id)} />
                  ))}
                </ul>
              </section>
            )}
            {[...groups.byBranch.entries()].map(([bid, list]) => {
              const info = branches[bid];
              return (
                <section key={bid} className="lvlup__group lvlup__group--branch">
                  <h3 className="lvlup__branch">
                    {info?.name ?? bid}
                    {lockedIn === bid && <span className="lvlup__locked">seu caminho</span>}
                  </h3>
                  {info?.theme && !lockedIn && (
                    <p className="lvlup__theme">
                      {info.theme} — <em>escolher este caminho fecha o outro para sempre.</em>
                    </p>
                  )}
                  {info?.theme && lockedIn === bid && (
                    <p className="lvlup__theme">{info.theme}</p>
                  )}
                  <ul className="lvlup__list">
                    {list.map((a) => (
                      <AbilityCard key={a.id} a={a} picked={picked === a.id}
                                   onPick={() => setPicked(a.id)} />
                    ))}
                  </ul>
                </section>
              );
            })}
            {(lu.eligible ?? []).length === 0 && (
              <p className="muted">Nenhuma habilidade elegível agora — volte após subir mais um nível.</p>
            )}
          </div>
        ) : (
          <div className="lvlup__attrs">
            {ATTRS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={"lvlup__attr" + (picked === key ? " is-picked" : "")}
                onClick={() => setPicked(key)}
              >
                <b>{label}</b>
                <span>+1</span>
              </button>
            ))}
          </div>
        )}

        <div className="lvlup__actions">
          <button className="btn" type="button" onClick={onLater} disabled={busy}>
            Deixar para depois
          </button>
          <button
            className="btn btn--primary"
            type="button"
            disabled={busy || !picked || (isAbility && (lu.eligible ?? []).length === 0)}
            onClick={() =>
              picked && onChoose(choice.id, isAbility ? { ability_id: picked } : { attr: picked })
            }
          >
            {busy ? "…" : "Confirmar"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function AbilityCard({ a, picked, onPick }: { a: EligibleAbility; picked: boolean; onPick: () => void }) {
  const cost = a.cost > 0 ? `${a.cost} ${a.resource_type}` : "sem custo";
  return (
    <li>
      <button type="button" className={"lvlup__card" + (picked ? " is-picked" : "")} onClick={onPick}>
        <span className="lvlup__card-top">
          <b>{a.name}</b>
          <span className="lvlup__tier">tier {a.tier} · {cost}</span>
        </span>
        <span className="lvlup__desc">{a.description}</span>
      </button>
    </li>
  );
}
