import { AnimatePresence, motion } from "motion/react";
import type { SceneVisual } from "../types";
import { useState } from 'react';
import { ArtworkDialog } from './ArtworkDialog';

export function SceneArtwork({ scene }: { scene?: SceneVisual | null }) {
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  if (!scene?.asset) return null;
  const image = scene.asset.variants.display;
  const key = `${scene.asset.asset_id}:${image.url}`;
  return (
    <div className="scene-art">
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
          transition={{ duration: 0.45 }}
          onError={() => setFailedKey(key)}
        />}
      </AnimatePresence>
      <div className="scene-art__veil" />
      <p>{scene.location_name}{scene.scope === "regional" ? " · visão regional" : ""}</p>
      {failedKey === key ? <span role="status">Arte indisponível</span> :
        <button type="button" className="art-expand" onClick={() => setExpandedKey(key)}
          aria-label={`Ampliar imagem de ${scene.location_name}`}>Ampliar</button>}
      {expandedKey === key && <ArtworkDialog url={image.url} alt={scene.asset.alt} onClose={() => setExpandedKey(null)} />}
    </div>
  );
}
