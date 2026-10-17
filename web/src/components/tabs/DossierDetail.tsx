import type {
  CreatureDossier, DossierBase, DossierClaim, FactionDossier, LocationDossier, NpcDossier, SecretDossier, VisualAsset,
} from "../../types";
import { mdLite } from "../../lib";
import { VisualArtwork } from "../VisualArtwork";
import { CertaintyBadge, KnowledgeNotes } from "./CertaintyBadge";

const TIER_ROMAN: Record<number, string> = { 1: "I", 2: "II", 3: "III", 4: "IV" };

// R13: corpos sempre por `mdLite` (escapa &, <, > antes de formatar) — só em conteúdo de elemento.
function Body({ text }: { text?: string }) {
  if (!text) return null;
  return <p className="codex-entry__body" dangerouslySetInnerHTML={{ __html: mdLite(text) }} />;
}

/** R9: arte só se o servidor enviou (asset público). Sem arte => placeholder honesto, nunca inferido por nome. */
function Portrait({ item }: { item: DossierBase }) {
  const asset = item.art && item.art.variants
    ? ({ ...item.art, subject_type: item.kind, subject_id: item.id, title: item.title } as unknown as VisualAsset)
    : null;
  if (!asset) {
    return (
      <p className="dossier__noart" data-testid="dossier-no-art">Sem retrato registrado.</p>
    );
  }
  return <VisualArtwork asset={asset} name={item.title} variant="portrait" expandable={false} />;
}

function Claims({ title, claims, hint, empty }: { title: string; claims: DossierClaim[]; hint?: string; empty?: string }) {
  return (
    <section className="dossier__section">
      <h4 className="dossier__h">{title}</h4>
      {hint && <p className="dossier__hint">{hint}</p>}
      {claims.length ? (
        <ul className="codex-notes">
          {claims.map((claim, index) => (
            <li key={index} className="codex-note"><CertaintyBadge stamp={claim.knowledge} /> {claim.text}</li>
          ))}
        </ul>
      ) : (empty ? <p className="combat-empty">{empty}</p> : null)}
    </section>
  );
}

function Header({ item, sub }: { item: DossierBase; sub?: string }) {
  return (
    <header className="dossier__head">
      <h3 className="dossier__title">{item.title}</h3>
      {sub && <p className="codex-entry__meta">{sub}</p>}
      <p className="codex-entry__meta">
        <CertaintyBadge stamp={item.knowledge} /> atualizado no turno {item.last_updated_turn}
      </p>
    </header>
  );
}

function NpcView({ item }: { item: NpcDossier }) {
  return (
    <>
      <Header item={item} sub={[item.role, item.location].filter(Boolean).join(" · ") || undefined} />
      <Portrait item={item} />
      <p className="codex-entry__meta">
        Relação: <b>{item.disposition_label}</b> ({item.relationship}/10)
        {item.status === "morto" && " · morto"}
        {item.knowledge_source === "mentioned" && " · só ouviu falar"}
      </p>
      {item.revealed_traits.length > 0 && (
        <p className="codex-entry__traits">
          {item.revealed_traits.map((trait) => (
            <span key={trait.id} className="traitchip">{trait.name}</span>
          ))}
        </p>
      )}
      <Body text={item.body} />
      <Claims title="O que você sabe" claims={item.claims} empty="Nenhuma afirmação registrada." />
      <Claims title="O que ele parece saber" claims={item.appears_to_know}
        hint="Inferência sua, a partir do que ele viu ou ouviu em cena."
        empty="Nada percebido ainda." />
      {item.encounters.length > 0 && (
        <section className="dossier__section">
          <h4 className="dossier__h">Encontros</h4>
          <ul className="codex-notes">
            {item.encounters.map((enc, index) => (
              <li key={index} className="codex-note">Turno {enc.turn} · {enc.outcome}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function LocationView({ item }: { item: LocationDossier }) {
  return (
    <>
      <Header item={item} sub={item.region || undefined} />
      <Portrait item={item} />
      <Body text={item.body} />
      {item.npcs.length > 0 && <p className="codex-entry__meta">Pessoas conhecidas aqui: {item.npcs.join(", ")}</p>}
      {item.creatures.length > 0 && <p className="codex-entry__meta">Criaturas avistadas: {item.creatures.join(", ")}</p>}
      {item.events.length > 0 && (
        <ul className="codex-notes">
          {item.events.map((ev, index) => <li key={index} className="codex-note">Turno {ev.turn} · {ev.outcome}</li>)}
        </ul>
      )}
      <KnowledgeNotes notes={item.notes} />
    </>
  );
}

function FactionView({ item }: { item: FactionDossier }) {
  return (
    <>
      <Header item={item} sub={item.region || undefined} />
      <p className="codex-entry__meta">
        {item.knows_goal ? item.goal : "Plano desconhecido — descubra com quem sabe."}
      </p>
      <p className="codex-entry__meta">Postura: {item.disposition} · Reputação: {item.reputation}</p>
      {item.intel_stale
        ? <p className="dossier__hint">{item.stale_label}</p>
        : item.progress != null && <p className="codex-entry__meta">Progresso conhecido: {item.progress}%</p>}
      <Body text={item.body} />
      <KnowledgeNotes notes={item.notes} />
    </>
  );
}

function SecretView({ item }: { item: SecretDossier }) {
  return (
    <>
      <Header item={item} sub={`revelado no turno ${item.turn}`} />
      <p className="codex-entry__body">{item.fact}</p>
      <KnowledgeNotes notes={item.notes} />
    </>
  );
}

function CreatureView({ item }: { item: CreatureDossier }) {
  return (
    <>
      <Header item={item} sub={`${TIER_ROMAN[item.tier] ?? item.tier} · ${item.tier_name}${item.regions?.length ? ` · ${item.regions.join(", ")}` : ""}`} />
      <Portrait item={item} />
      {item.rarity_note && <p className="codex-entry__meta">{item.rarity_note}</p>}
      {item.description && <p className="codex-entry__body">{item.description}</p>}
      {item.max_hp != null && <p className="codex-entry__meta">HP {item.max_hp} · Defesa {item.defense}</p>}
      {Array.isArray(item.attacks) && item.attacks.length > 0 && (
        <p className="codex-entry__meta">
          Ataques: {item.attacks.map((a) => (typeof a === "string" ? a : a.name)).join(", ")}
        </p>
      )}
      {item.loot && item.loot.length > 0 && <p className="codex-entry__meta">Loot: {item.loot.join(", ")}</p>}
      {item.revealed_cards && item.revealed_cards.length > 0 && (
        <p className="codex-entry__meta">Cartas reveladas: {item.revealed_cards.map((c) => c.name).join(", ")}</p>
      )}
      {item.revealed_resistances && item.revealed_resistances.length > 0 && (
        <p className="codex-entry__meta">Resistências reveladas: {item.revealed_resistances.join(", ")}</p>
      )}
      <KnowledgeNotes notes={item.notes} />
    </>
  );
}

export function DossierDetail({ item }: { item: DossierBase }) {
  switch (item.kind) {
    case "npc": return <NpcView item={item as NpcDossier} />;
    case "location": return <LocationView item={item as LocationDossier} />;
    case "faction": return <FactionView item={item as FactionDossier} />;
    case "secret": return <SecretView item={item as SecretDossier} />;
    case "creature": return <CreatureView item={item as CreatureDossier} />;
  }
}
