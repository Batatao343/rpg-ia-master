import { AnimatePresence, motion } from "motion/react";
import type { SceneVisual } from "../types";

export function SceneArtwork({ scene }: { scene?: SceneVisual | null }) {
  if (!scene?.asset) return null;
  const image = scene.asset.variants.display;
  return (
    <div className="scene-art">
      <AnimatePresence mode="wait">
        <motion.img
          key={`${scene.location_id}:${scene.asset.asset_id}`}
          src={image.url}
          width={image.width}
          height={image.height}
          alt={scene.asset.alt}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45 }}
        />
      </AnimatePresence>
      <div className="scene-art__veil" />
      <p>{scene.location_name}{scene.scope === "regional" ? " · visão regional" : ""}</p>
    </div>
  );
}
