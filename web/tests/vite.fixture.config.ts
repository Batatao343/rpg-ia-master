import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  publicDir: false,
  build: {
    lib: { entry: 'tests/artwork.fixture.tsx', name: 'ArtworkFixture', formats: ['iife'], fileName: () => 'fixture.js' },
    emptyOutDir: true,
  },
});
