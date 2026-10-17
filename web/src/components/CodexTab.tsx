import { useEffect, useRef, useState, type ReactNode } from "react";
import { getCodex } from "../api";
import { mdLite } from "../lib";
import type { DossiersPayload, PlayerCodex } from "../types";
import { categoryCount } from "../codexKnowledge";
import { isProjectionBehind } from "../dossiers";
import { CertaintyBadge, KnowledgeNotes } from "./tabs/CertaintyBadge";
import { DossierBrowser } from "./tabs/DossierBrowser";
import { useDossiers } from "./tabs/useDossiers";
import { RovingTablist } from "../workspace/RovingTablist";
import { ArrivalLi, ArrivalsProvider, NO_ARRIVALS } from "../design/primitives";

type Category = "locations" | "factions" | "characters" | "creatures" | "secrets";

const CATEGORIES: Array<[Category, string]> = [
  ["locations", "Locais"],
  ["factions", "Fações"],
  ["characters", "Personagens"],
  ["creatures", "Bestiário"],
  ["secrets", "Segredos"],
];

const TIER_ROMAN: Record<number, string> = { 1: "I", 2: "II", 3: "III", 4: "IV" };

const KnowledgeBadge = CertaintyBadge;

/** Seção extra do Codex (SPEC-204 D1): Pessoas, Fações-reputação, Crônica. */
export interface CodexSection {
  id: string;
  label: string;
  /** Insere a seção logo antes desta categoria (default: no fim). */
  before?: Category;
  render: (codex: PlayerCodex | null, dossiers?: DossiersPayload | null) => ReactNode;
}

/** Codex do jogador (`GET /game/codex`) — compartilhado pelas abas Codex e Bestiário. */
export function codexEntryIds(codex: PlayerCodex): Set<string> {
  const ids = new Set<string>();
  codex.locations.forEach((x) => ids.add(`loc:${x.id}`));
  codex.factions.forEach((x) => ids.add(`fac:${x.id}`));
  codex.characters.forEach((x) => ids.add(`chr:${x.name}`));
  codex.creatures.forEach((x) => ids.add(`crt:${x.id}`));
  codex.secrets.forEach((x) => ids.add(`sec:${x.turn}:${x.fact}`));
  return ids;
}

export function usePlayerCodex(gameId: string | null | undefined, turnCount: number | undefined, open: boolean) {
  const [codex, setCodex] = useState<PlayerCodex | null>(null);
  const [loading, setLoading] = useState(false);
  // codex.entry.reveal (M24): ids que chegaram do servidor DEPOIS da primeira leitura deste jogo.
  const [arrivals, setArrivals] = useState<ReadonlySet<string>>(NO_ARRIVALS);
  const known = useRef<{ gameId: string; ids: Set<string> } | null>(null);
  useEffect(() => {
    if (!open || !gameId) return;
    let active = true;
    setLoading(true);
    getCodex(gameId)
      .then((value) => {
        if (!active) return;
        const ids = codexEntryIds(value);
        const prev = known.current?.gameId === gameId ? known.current.ids : null;
        setArrivals(prev ? new Set([...ids].filter((id) => !prev.has(id))) : NO_ARRIVALS);
        known.current = { gameId, ids };
        setCodex(value);
      })
      .catch(() => { if (active) setCodex(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, gameId, turnCount]);
  return { codex, loading, arrivals };
}

export function CodexTab({
  gameId,
  turnCount,
  open,
  excludeCategories = [],
  sections = [],
  unavailable,
  section,
  onSection,
}: {
  gameId: string | null | undefined;
  turnCount: number | undefined;
  open: boolean;
  excludeCategories?: Category[];
  sections?: CodexSection[];
  /** Ex.: laboratório de combate — explica e não consulta a API. */
  unavailable?: string;
  /** Seção controlada pelo workspace (ex.: "Ler a crônica" no memorial). */
  section?: string;
  onSection?: (id: string) => void;
}) {
  const live = open && !unavailable;
  const { payload: dossiers, failed: dossiersFailed, arrivals: dossierArrivals } = useDossiers(gameId, turnCount, live);
  // Endpoint novo indisponível => formato antigo (§3.4); com dossiês, o Codex antigo não é consultado.
  const { codex, loading, arrivals } = usePlayerCodex(gameId, turnCount, live && dossiersFailed);
  const categories = CATEGORIES.filter(([id]) => !excludeCategories.includes(id));
  const order: string[] = [];
  for (const [id] of categories) {
    for (const extra of sections) if (extra.before === id) order.push(extra.id);
    order.push(id);
  }
  for (const extra of sections) if (!extra.before) order.push(extra.id);
  const [ownCategory, setOwnCategory] = useState<string>(order[0] ?? "locations");
  const category = section && order.includes(section) ? section : ownCategory;
  const setCategory = (id: string) => { setOwnCategory(id); onSection?.(id); };

  if (unavailable) {
    return (
      <div>
        <p className="hud__label">Codex</p>
        <p className="combat-empty">{unavailable}</p>
      </div>
    );
  }

  const items = order.map((id) => {
    const extraSection = sections.find((section) => section.id === id);
    if (extraSection) return { id, label: extraSection.label };
    const label = CATEGORIES.find(([cat]) => cat === id)?.[1] ?? id;
    const n = dossiers ? dossierCount(dossiers, id as Category) : codex ? categoryCount(codex, id as Category) : null;
    return { id, label: n === null ? label : `${label} (${n})` };
  });
  const extra = sections.find((section) => section.id === category);

  return (
    <div>
      <p className="hud__label">Codex do jogador</p>
      <RovingTablist items={items} selected={category} onSelect={setCategory}
        label="Seções do Codex" idPrefix="codex" className="codex-cats" tabClassName="codex-cat" controlsActiveOnly />
      <div role="tabpanel" id={`codex-panel-${category}`} aria-labelledby={`codex-tab-${category}`} className="codex-section">
        <ArrivalsProvider value={dossiers ? dossierArrivals : arrivals}>
        {extra ? extra.render(codex, dossiers) : dossiers && gameId && DOSSIER_CATEGORIES.includes(category as Category) ? (
          <DossierCategory dossiers={dossiers} gameId={gameId} category={category as Category} turnCount={turnCount} />
        ) : loading && !codex ? (
          <p className="combat-empty">Consultando os registros da jornada…</p>
        ) : !codex ? (
          <p className="combat-empty">Nada registrado ainda — explore o mundo.</p>
        ) : (
          <CodexCategory codex={codex} category={category as Category} />
        )}
        </ArrivalsProvider>
      </div>
    </div>
  );
}

export function CreatureList({ creatures }: { creatures: PlayerCodex["creatures"] }) {
  if (!creatures.length) return <p className="combat-empty">Nenhuma criatura registrada ainda.</p>;
  return (
    <ul className="codex-list codex-list--beasts">
      {creatures.map((cr) => (
        <ArrivalLi key={cr.id} id={`crt:${cr.id}`} className={"codex-entry codex-beast codex-beast--tier" + cr.tier}>
          <div className="codex-beast__top">
            <span className="codex-beast__seal" title={cr.tier_name}>{TIER_ROMAN[cr.tier]}</span>
            <div>
              <p className="codex-entry__name">{cr.name} <KnowledgeBadge stamp={cr.knowledge} /></p>
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
          <KnowledgeNotes notes={cr.notes} />
        </ArrivalLi>
      ))}
    </ul>
  );
}

export function CodexCategory({ codex, category }: { codex: PlayerCodex; category: Category }) {
  return (
    <>
      {category === "locations" && (
        codex.locations.length ? (
          <ul className="codex-list">
            {codex.locations.map((loc) => (
              <ArrivalLi key={loc.id} id={`loc:${loc.id}`} className="codex-entry">
                <p className="codex-entry__name">{loc.name} <KnowledgeBadge stamp={loc.knowledge} /></p>
                {loc.body && (
                  <p className="codex-entry__body" dangerouslySetInnerHTML={{ __html: mdLite(loc.body) }} />
                )}
                <KnowledgeNotes notes={loc.notes} />
              </ArrivalLi>
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
              <ArrivalLi key={f.id} id={`fac:${f.id}`} className="codex-entry">
                <p className="codex-entry__name">{f.name} <KnowledgeBadge stamp={f.knowledge} /></p>
                <p className="codex-entry__meta">
                  {f.knows_goal ? f.goal : "Plano desconhecido — descubra com quem sabe."}
                </p>
                {f.body && (
                  <p className="codex-entry__body" dangerouslySetInnerHTML={{ __html: mdLite(f.body) }} />
                )}
                <KnowledgeNotes notes={f.notes} />
              </ArrivalLi>
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
              <ArrivalLi key={i} id={`chr:${c.name}`} className={"codex-entry" + (c.knowledge_source === "mentioned" ? " codex-entry--heard" : "")}>
                <p className="codex-entry__name">
                  {c.name}
                  {c.knowledge_source === "mentioned" && <span className="codex-entry__hint"> · ouviu falar</span>}
                  {" "}<KnowledgeBadge stamp={c.knowledge} />
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
                <KnowledgeNotes notes={c.notes} />
              </ArrivalLi>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhum personagem conhecido ainda.</p>
        )
      )}

      {category === "creatures" && <CreatureList creatures={codex.creatures} />}

      {category === "secrets" && (
        codex.secrets.length ? (
          <ul className="codex-list">
            {codex.secrets.map((s, i) => (
              <ArrivalLi key={i} id={`sec:${s.turn}:${s.fact}`} className="codex-entry">
                <p className="codex-entry__body">{s.fact}</p>
                <p className="codex-entry__meta">revelado no turno {s.turn} <KnowledgeBadge stamp={s.knowledge} /></p>
                <KnowledgeNotes notes={s.notes} />
              </ArrivalLi>
            ))}
          </ul>
        ) : (
          <p className="combat-empty">Nenhum segredo revelado ainda.</p>
        )
      )}
    </>
  );
}

const DOSSIER_CATEGORIES: Category[] = ["locations", "factions", "characters", "secrets"];

function dossierCount(d: DossiersPayload, category: Category): number {
  const s = d.sections;
  return category === "locations" ? s.locations.length : category === "factions" ? s.factions.length
    : category === "characters" ? s.npcs.length : category === "secrets" ? s.secrets.length : d.bestiary.length;
}

/** SPEC-211: categorias do Codex servidas por dossiês (contagem só dos visíveis, R8). */
export function DossierCategory({ dossiers, gameId, category, turnCount }: {
  dossiers: DossiersPayload; gameId: string; category: Category; turnCount?: number;
}) {
  const behind = isProjectionBehind(dossiers, turnCount);
  if (category === "locations") {
    return <DossierBrowser gameId={gameId} tabId="locations" items={dossiers.sections.locations}
      empty="Nenhum local visitado ainda." behind={behind}
      subtitle={(l) => l.region || ""} />;
  }
  if (category === "characters") {
    return <DossierBrowser gameId={gameId} tabId="characters" items={dossiers.sections.npcs}
      empty="Nenhum personagem conhecido ainda." behind={behind}
      subtitle={(n) => [n.role, n.location].filter(Boolean).join(" · ")} />;
  }
  if (category === "factions") {
    return <DossierBrowser gameId={gameId} tabId="factions" items={dossiers.sections.factions}
      empty="Nenhuma facção conhecida ainda." behind={behind}
      subtitle={(f) => (f.knows_goal ? f.goal : "Plano desconhecido")} />;
  }
  return <DossierBrowser gameId={gameId} tabId="secrets" items={dossiers.sections.secrets}
    empty="Nenhum segredo revelado ainda." behind={behind}
    subtitle={(x) => `revelado no turno ${x.turn}`} />;
}
