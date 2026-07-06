import { useEffect, useState } from "react";
import { getCodex } from "../api";
import { mdLite } from "../lib";
import type { PlayerCodex } from "../types";

type Category = "locations" | "factions" | "characters" | "creatures" | "secrets";

const CATEGORIES: Array<[Category, string]> = [
  ["locations", "Locais"],
  ["factions", "Fações"],
  ["characters", "Personagens"],
  ["creatures", "Bestiário"],
  ["secrets", "Segredos"],
];

const TIER_ROMAN: Record<number, string> = { 1: "I", 2: "II", 3: "III", 4: "IV" };

export function CodexTab({
  gameId,
  turnCount,
  open,
}: {
  gameId: string | null | undefined;
  turnCount: number | undefined;
  open: boolean;
}) {
  const [codex, setCodex] = useState<PlayerCodex | null>(null);
  const [category, setCategory] = useState<Category>("locations");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !gameId) return;
    setLoading(true);
    getCodex(gameId)
      .then(setCodex)
      .catch(() => setCodex(null))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, gameId, turnCount]);

  if (!open) return null;

  if (loading && !codex) {
    return (
      <div>
        <p className="hud__label">Codex</p>
        <p className="combat-empty">Consultando os registros da jornada…</p>
      </div>
    );
  }

  if (!codex) {
    return (
      <div>
        <p className="hud__label">Codex</p>
        <p className="combat-empty">Nada registrado ainda — explore o mundo.</p>
      </div>
    );
  }

  return (
    <div>
      <p className="hud__label">Codex do jogador</p>
      <nav className="codex-cats" role="tablist">
        {CATEGORIES.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={category === id}
            className={"codex-cat" + (category === id ? " is-active" : "")}
            onClick={() => setCategory(id)}
          >
            {label} ({codex[id].length})
          </button>
        ))}
      </nav>

      {category === "locations" && (
        codex.locations.length ? (
          <ul className="codex-list">
            {codex.locations.map((loc) => (
              <li key={loc.id} className="codex-entry">
                <p className="codex-entry__name">{loc.name}</p>
                {loc.body && (
                  <p className="codex-entry__body" dangerouslySetInnerHTML={{ __html: mdLite(loc.body) }} />
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhum local visitado ainda.</p>
        )
      )}

      {category === "factions" && (
        codex.factions.length ? (
          <ul className="codex-list">
            {codex.factions.map((f) => (
              <li key={f.id} className="codex-entry">
                <p className="codex-entry__name">{f.name}</p>
                <p className="codex-entry__meta">
                  {f.knows_goal ? f.goal : "Plano desconhecido — descubra com quem sabe."}
                </p>
                {f.body && (
                  <p className="codex-entry__body" dangerouslySetInnerHTML={{ __html: mdLite(f.body) }} />
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhuma facção conhecida ainda.</p>
        )
      )}

      {category === "characters" && (
        codex.characters.length ? (
          <ul className="codex-list">
            {codex.characters.map((c, i) => (
              <li key={i} className={"codex-entry" + (c.knowledge_source === "mentioned" ? " codex-entry--heard" : "")}>
                <p className="codex-entry__name">
                  {c.name}
                  {c.knowledge_source === "mentioned" && <span className="codex-entry__hint"> · ouviu falar</span>}
                </p>
                <p className="codex-entry__meta">{[c.role, c.location].filter(Boolean).join(" · ") || "—"}</p>
                {(c.revealed_traits?.length ?? 0) > 0 && (
                  <p className="codex-entry__traits">
                    {c.revealed_traits!.map((t) => (
                      <span key={t.id} className="traitchip" title={t.description}>{t.name}</span>
                    ))}
                  </p>
                )}
                {c.body && (
                  <p className="codex-entry__body" dangerouslySetInnerHTML={{ __html: mdLite(c.body) }} />
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhum personagem conhecido ainda.</p>
        )
      )}

      {category === "creatures" && (
        codex.creatures.length ? (
          <ul className="codex-list codex-list--beasts">
            {codex.creatures.map((cr) => (
              <li key={cr.id} className={"codex-entry codex-beast codex-beast--tier" + cr.tier}>
                <div className="codex-beast__top">
                  <span className="codex-beast__seal" title={cr.tier_name}>{TIER_ROMAN[cr.tier]}</span>
                  <div>
                    <p className="codex-entry__name">{cr.name}</p>
                    <p className="codex-entry__meta">{cr.tier_name}{cr.regions?.length ? ` · ${cr.regions.join(", ")}` : ""}</p>
                  </div>
                </div>
                {cr.description && <p className="codex-entry__body">{cr.description}</p>}
                {cr.max_hp != null && (
                  <p className="codex-entry__meta">HP {cr.max_hp} · Defesa {cr.defense}</p>
                )}
                {Array.isArray(cr.attacks) && cr.attacks.length > 0 && (
                  <p className="codex-entry__meta">
                    Ataques: {cr.attacks.map((a) => (typeof a === "string" ? a : a.name)).join(", ")}
                  </p>
                )}
                {cr.loot && cr.loot.length > 0 && (
                  <p className="codex-entry__meta">Loot: {cr.loot.join(", ")}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhuma criatura registrada ainda.</p>
        )
      )}

      {category === "secrets" && (
        codex.secrets.length ? (
          <ul className="codex-list">
            {codex.secrets.map((s, i) => (
              <li key={i} className="codex-entry">
                <p className="codex-entry__body">{s.fact}</p>
                <p className="codex-entry__meta">revelado no turno {s.turn}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhum segredo revelado ainda.</p>
        )
      )}
    </div>
  );
}
