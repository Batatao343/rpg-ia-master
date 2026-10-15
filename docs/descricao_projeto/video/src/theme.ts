import {loadFont as loadCinzel} from '@remotion/google-fonts/Cinzel';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';
import type {Group} from './types';

export const FONT_TITLE = loadCinzel('normal', {weights: ['600', '700'], subsets: ['latin', 'latin-ext']}).fontFamily;
export const FONT_BODY = loadInter('normal', {weights: ['400', '500', '600', '700'], subsets: ['latin', 'latin-ext']}).fontFamily;
export const FONT_MONO = loadMono('normal', {weights: ['400', '600'], subsets: ['latin', 'latin-ext']}).fontFamily;

export const C = {
  bg0: '#0b0a0d',
  bg1: '#15121a',
  panel: 'rgba(255,245,225,0.04)',
  panelBorder: 'rgba(232,200,140,0.18)',
  text: '#efe6d6',
  muted: '#a99c88',
  dim: '#6f6557',
  gold: '#e3b765',
};

export const GROUP_COLORS: Record<Group, string> = {
  llm: '#b98cff',
  python: '#e6a94a',
  data: '#5fbfa8',
  io: '#6ea4e8',
  infra: '#98a3b3',
  neutral: '#cdbb9d',
};

export const GROUP_LABEL: Record<Group, string> = {
  llm: 'LLM',
  python: 'Python determinístico',
  data: 'Dados',
  io: 'Entrada/Saída',
  infra: 'Infra',
  neutral: '',
};

// Área útil para os visuais (abaixo do cabeçalho, acima das legendas)
export const STAGE = {x: 110, y: 150, w: 1700, h: 700};
