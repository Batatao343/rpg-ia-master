import React from 'react';
import { createRoot } from 'react-dom/client';
import { VisualArtwork } from '../src/components/VisualArtwork';
import { SceneArtwork } from '../src/components/SceneArtwork';
import type { VisualAsset, SceneVisual } from '../src/types';
import '../src/styles.css';

const root = createRoot(document.getElementById('fixture')!);
Object.assign(window, {
  renderArtwork(asset: VisualAsset, scene: SceneVisual) {
    root.render(<main style={{ padding: 20, maxWidth: 800 }}>
      <VisualArtwork asset={asset} name="Retrato de teste" variant="card" />
      <SceneArtwork scene={scene} />
    </main>);
  },
});
