import { useState } from "react";
import type { VisualAsset } from "../types";

export function VisualArtwork({ asset, name, caption, className = "" }: {
  asset: VisualAsset | null;
  name: string;
  caption?: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (!asset || failed) {
    return (
      <figure className={`visual-art visual-art--fallback ${className}`}>
        <div className="visual-art__monogram" aria-hidden>{name.trim().charAt(0) || "?"}</div>
        <figcaption><strong>{name}</strong>{caption && <span>{caption}</span>}</figcaption>
      </figure>
    );
  }
  const { thumbnail, display } = asset.variants;
  return (
    <figure className={`visual-art ${className}`} style={{ backgroundColor: asset.placeholder_color }}>
      <img
        src={display.url}
        srcSet={`${thumbnail.url} ${thumbnail.width}w, ${display.url} ${display.width}w`}
        sizes="(max-width: 600px) 92vw, 720px"
        width={display.width}
        height={display.height}
        alt={asset.alt}
        loading="lazy"
        onError={() => setFailed(true)}
      />
      {(name || caption) && <figcaption><strong>{name}</strong>{caption && <span>{caption}</span>}</figcaption>}
    </figure>
  );
}
