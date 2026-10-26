import { useEffect, useState, type ReactNode } from "react";
import * as api from "../../api";
import type { GameResponse, VisualAsset, WoundTrackView } from "../../types";
import { FichaTab, type EquipFn } from "../Hud";
import { GeneratedPortrait } from "../GeneratedPortrait";
import { QuestsTab } from "../QuestsTab";
import { Sigil } from "../Sigil";
import { VisualArtwork } from "../VisualArtwork";
import { WoundTrack } from "../WoundTrack";
import { RovingTablist } from "../../workspace/RovingTablist";
import { evolutionHistory } from "./journey";
import "./tabs.css";

type Section = "ficha" | "jornada";

// Capas de raça/classe vêm do catálogo visual público (/data/options). Uma busca por sessão de página.
let coversPromise: Promise<NonNullable<import("../../types").CreateOptions["visuals"]> | null> | null = null;
function loadCovers() {
  coversPromise ??= api.getOptions().then((o) => o.visuals ?? null).catch(() => null);
  return coversPromise;
}

/** R10: sem retrato gerado → capa de classe do catálogo; sem capa → monograma honesto. */
function PortraitFallback({ className, name }: { className: string; name: string }) {
  const [asset, setAsset] = useState<VisualAsset | null>(null);
  useEffect(() => {
    let live = true;
    void loadCovers().then((v) => { if (live) setAsset(v?.classes?.[className] ?? null); });
    return () => { live = false; };
  }, [className]);
  return <VisualArtwork asset={asset} name={name} caption={className} className="char-portrait" variant="card" />;
}

const hasWounds = (data: GameResponse) =>
  Object.values(data.player_stats.ferimentos ?? {}).some((rows) => Array.isArray(rows) && rows.length > 0);

function woundsFrom(data: GameResponse): WoundTrackView {
  const p = data.player_stats;
  const raw = (p.ferimentos ?? {}) as Record<string, unknown[]>;
  const pick = (k: string) => (Array.isArray(raw[k]) ? raw[k] : []) as WoundTrackView["by_severity"]["leve"];
  return {
    vitality: p.vitalidade, max_vitality: p.max_vitalidade, slots: {},
    by_severity: { leve: pick("leve"), grave: pick("grave"), critico: pick("critico") },
  };
}

/** SPEC-209 R8–R13: ficha completa + Jornada. Tudo vem de `GameResponse`; nada é recalculado aqui. */
export function CharacterTab({ data, hitKey, onEquip, busy, artPanel }: {
  data: GameResponse | null; hitKey: number; onEquip?: EquipFn; busy?: boolean;
  /** SPEC-321 R6: cotação de retrato e imagens encomendadas (saíram do topo da tela). */
  artPanel?: ReactNode;
}) {
  const [section, setSection] = useState<Section>("ficha");
  const p = data?.player_stats;
  const sub = [p?.class_name, p?.subclass, p?.race].filter(Boolean).join(" · ") || "—";
  const scars = p?.scars ?? [];
  const history = evolutionHistory(data?.chronicle);
  return (
    <div className="ws-sheet">
      <div className="ws-sheet__head">
        <span className="hud__sigil"><Sigil size={36} /></span>
        <div className="hud__id">
          <p className="hud__name">{p?.name || "—"}</p>
          <p className="hud__sub">{sub}</p>
          <p className="hud__sub">Nível {p?.level ?? 1} · turno {data?.world?.turn_count ?? 0}
            {busy && <span className="char-sync"> · atualizando…</span>}</p>
        </div>
      </div>
      <RovingTablist<Section>
        items={[{ id: "ficha", label: "Ficha" }, { id: "jornada", label: "Jornada · Missões" }]}
        selected={section} onSelect={setSection} label="Seções do personagem"
        idPrefix="personagem" className="codex-cats" tabClassName="codex-cat" controlsActiveOnly />
      <div role="tabpanel" id={`personagem-panel-${section}`} aria-labelledby={`personagem-tab-${section}`}
        className="ws-sheet__body">
        {section === "ficha" && data && (
          data.portrait_generation_id ? (
            <GeneratedPortrait key={`${data.game_id}:${data.portrait_generation_id}`}
              gameId={data.game_id} generationId={data.portrait_generation_id} />
          ) : (
            <PortraitFallback key={data.game_id} className={p?.class_name ?? ""} name={p?.name ?? ""} />
          )
        )}
        {section === "ficha" && artPanel}
        {section === "ficha" && data && hasWounds(data) && <WoundTrack wounds={woundsFrom(data)} />}
        {section === "ficha" && <FichaTab data={data} hpHitKey={hitKey} onEquip={onEquip} busy={busy} />}
        {section === "ficha" && scars.length > 0 && (
          <div>
            <h3 className="hud__label">Cicatrizes</h3>
            <ul className="char-scars">
              {scars.map((scar) => (
                <li key={scar.id} className="char-scar">
                  {scar.origem && <p><b>{scar.origem}</b></p>}
                  <p>{scar.consequencia_negativa}</p>
                  {scar.habilidade_positiva_relacionada && (
                    <p className="char-scar__good">+ {scar.habilidade_positiva_relacionada}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {section === "jornada" && (
          <>
            <QuestsTab quest={data?.quest} />
            <div>
              <h3 className="hud__label">Evolução do herói</h3>
              {history.length === 0 ? (
                <p className="combat-empty">Nenhum marco de evolução registrado ainda.</p>
              ) : (
                <ul className="char-journey">
                  {history.map((text, i) => <li key={i} className="char-journey__item">{text}</li>)}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
