import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { SceneVisual } from "../types";
import { useState } from 'react';
import { ArtworkDialog } from './ArtworkDialog';
import { Icon } from "../design/icons";

/** SPEC-321 R4: `collapsed` (mobile) reduz a faixa a ≤ 72 px por troca de classe — sem animar altura. */
export function SceneArtwork({ scene, collapsed = false, onToggle }: {
  scene?: SceneVisual | null; collapsed?: boolean; onToggle?: () => void;
}) {
  const reduce = useReducedMotion(); // SPEC-216 R8: opacidade tambem fica estatica com reduced motion
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  if (!scene?.asset) return null;
  const image = scene.asset.variants.display;
  const key = `${scene.asset.asset_id}:${image.url}`;
  return (
    <div className={"scene-art" + (collapsed ? " is-collapsed" : "")}>
      <AnimatePresence mode="wait">
        {failedKey !== key && <motion.img
          key={`${scene.location_id}:${scene.asset.asset_id}`}
          src={image.url}
          width={image.width}
          height={image.height}
          alt={scene.asset.alt}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.45 }}
          onError={() => setFailedKey(key)}
        />}
      </AnimatePresence>
      <div className="scene-art__veil" />
      <p>{scene.location_name}{scene.scope === "regional" ? " · visão regional" : ""}</p>
      {failedKey === key ? <span role="status">Arte indisponível</span> :
        !collapsed && <button type="button" className="art-expand" onClick={() => setExpandedKey(key)}
          aria-label={`Ampliar imagem de ${scene.location_name}`}>Ampliar</button>}
      {onToggle && (
        <button type="button" className="scene-art__toggle" onClick={onToggle} aria-expanded={!collapsed}
          aria-label={collapsed ? `Mostrar a arte de ${scene.location_name}` : "Recolher a arte da cena"}>
          <Icon name={collapsed ? "caret-down" : "caret-up"} />
        </button>
      )}
      {expandedKey === key && <ArtworkDialog url={image.url} alt={scene.asset.alt} onClose={() => setExpandedKey(null)} />}
    </div>
  );
}
