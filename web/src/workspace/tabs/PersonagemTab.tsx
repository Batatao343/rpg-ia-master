import { useState } from "react";
import type { GameResponse } from "../../types";
import { FichaTab, type EquipFn } from "../../components/Hud";
import { GeneratedPortrait } from "../../components/GeneratedPortrait";
import { QuestsTab } from "../../components/QuestsTab";
import { Medallion } from "../../components/ornaments";
import { RovingTablist } from "../RovingTablist";

type Section = "ficha" | "jornada";

/** SPEC-204 D1: Ficha + Missões ("Jornada") do herói. */
export function PersonagemTab({ data, hitKey, onEquip, busy }: {
  data: GameResponse | null; hitKey: number; onEquip?: EquipFn; busy?: boolean;
}) {
  const [section, setSection] = useState<Section>("ficha");
  const p = data?.player_stats;
  const sub = [p?.class_name, p?.race].filter(Boolean).join(" · ") || "—";
  return (
    <div className="ws-sheet">
      <div className="ws-sheet__head">
        <span className="hud__medallion"><Medallion size={36} /></span>
        <div className="hud__id">
          <p className="hud__name">{p?.name || "—"}</p>
          <p className="hud__sub">{sub}</p>
        </div>
      </div>
      <RovingTablist<Section>
        items={[{ id: "ficha", label: "Ficha" }, { id: "jornada", label: "Jornada · Missões" }]}
        selected={section} onSelect={setSection} label="Seções do personagem"
        idPrefix="personagem" className="codex-cats" tabClassName="codex-cat" controlsActiveOnly />
      <div role="tabpanel" id={`personagem-panel-${section}`} aria-labelledby={`personagem-tab-${section}`}
        className="ws-sheet__body">
        {section === "ficha" && data?.portrait_generation_id && <GeneratedPortrait
          key={`${data.game_id}:${data.portrait_generation_id}`}
          gameId={data.game_id} generationId={data.portrait_generation_id} />}
        {section === "ficha" && <FichaTab data={data} hpHitKey={hitKey} onEquip={onEquip} busy={busy} />}
        {section === "jornada" && <QuestsTab quest={data?.quest} />}
      </div>
    </div>
  );
}
