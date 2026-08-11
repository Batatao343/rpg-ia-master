import { useEffect, useMemo, useState } from "react";
import * as api from "../api";
import type {
  CombatSimulatorOptions,
  CombatSimulatorPayload,
} from "../types";
import { Divider, Frame, Medallion } from "./ornaments";

const CATEGORY_LABELS: Record<string, string> = {
  lacaio: "Lacaios",
  padrao: "Padrão",
  elite: "Elites",
  nomeado: "Nomeados",
  chefe: "Chefes",
};

interface Props {
  busy: boolean;
  onStart: (payload: CombatSimulatorPayload) => void;
  onBack: () => void;
  onError: (message: string) => void;
}

export function CombatSimulatorScreen({ busy, onStart, onBack, onError }: Props) {
  const [options, setOptions] = useState<CombatSimulatorOptions | null>(null);
  const [className, setClassName] = useState("");
  const [level, setLevel] = useState<1 | 3 | 5 | 10>(1);
  const [enemyId, setEnemyId] = useState("");
  const [quantity, setQuantity] = useState<1 | 2 | 3>(1);

  useEffect(() => {
    api.getCombatSimulatorOptions()
      .then((loaded) => {
        setOptions(loaded);
        setClassName((current) => current || loaded.classes[0] || "");
        setEnemyId((current) => current || loaded.enemies[0]?.id || "");
      })
      .catch((error: unknown) => {
        const detail = error instanceof Error ? error.message : String(error);
        onError(`Não consegui abrir o laboratório. (${detail})`);
      });
  }, [onError]);

  const groupedEnemies = useMemo(() => {
    const groups = new Map<string, CombatSimulatorOptions["enemies"]>();
    for (const enemy of options?.enemies ?? []) {
      const current = groups.get(enemy.category) ?? [];
      current.push(enemy);
      groups.set(enemy.category, current);
    }
    return groups;
  }, [options]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!className || !enemyId) return;
    onStart({ class_name: className, level, enemy_id: enemyId, quantity });
  }

  return (
    <main className="create simulator-screen">
      <Frame className="create__frame simulator-screen__frame">
        <div className="create__seal"><Medallion size={48} /></div>
        <header className="create__head">
          <p className="kicker">Motor real · Zero LLM</p>
          <h1 className="create__title">Laboratório de combate</h1>
          <p className="create__sub">
            Entre direto na arena para testar Cartas, Reações, Ferimentos e a IA
            tática dos inimigos, sem avançar uma campanha.
          </p>
        </header>
        <Divider />

        {!options ? (
          <p className="simulator-screen__loading" role="status">
            Preparando o bestiário…
          </p>
        ) : (
          <form className="form" onSubmit={submit}>
            <div className="form__row">
              <div className="field">
                <label htmlFor="sim-class">Classe</label>
                <select
                  id="sim-class"
                  value={className}
                  onChange={(event) => setClassName(event.target.value)}
                >
                  {options.classes.map((classOption) => (
                    <option key={classOption} value={classOption}>{classOption}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Nível</label>
                <div className="segmented" role="radiogroup" aria-label="Nível da simulação">
                  {options.levels.map((levelOption) => (
                    <button
                      key={levelOption}
                      type="button"
                      className="seg"
                      aria-pressed={level === levelOption}
                      onClick={() => setLevel(levelOption)}
                    >
                      {levelOption}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="field">
              <label htmlFor="sim-enemy">Inimigo</label>
              <select
                id="sim-enemy"
                value={enemyId}
                onChange={(event) => setEnemyId(event.target.value)}
              >
                {[...groupedEnemies.entries()].map(([category, enemies]) => (
                  <optgroup key={category} label={CATEGORY_LABELS[category] ?? category}>
                    {enemies.map((enemy) => (
                      <option key={enemy.id} value={enemy.id}>{enemy.name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            <div className="field">
              <label>Quantidade</label>
              <div className="segmented" role="radiogroup" aria-label="Quantidade de inimigos">
                {options.quantities.map((quantityOption) => (
                  <button
                    key={quantityOption}
                    type="button"
                    className="seg"
                    aria-pressed={quantity === quantityOption}
                    onClick={() => setQuantity(quantityOption)}
                  >
                    {quantityOption}
                  </button>
                ))}
              </div>
            </div>

            <p className="simulator-screen__note">
              A arena usa o mesmo motor da campanha. Não concede XP, loot ou
              progresso narrativo.
            </p>
            <div className="form__actions">
              <button className="btn btn--primary" type="submit" disabled={busy || !enemyId}>
                {busy ? "Abrindo arena…" : "Entrar na arena"}
              </button>
              <button className="btn btn--ghost" type="button" disabled={busy} onClick={onBack}>
                Voltar
              </button>
            </div>
          </form>
        )}
      </Frame>
    </main>
  );
}
