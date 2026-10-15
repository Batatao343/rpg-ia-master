export type Group = 'llm' | 'python' | 'data' | 'io' | 'infra' | 'neutral';

export type Visual =
  | {type: 'title'; heading: string; subheading?: string}
  | {type: 'bullets'; heading: string; items: string[]}
  | {
      type: 'graph';
      heading: string;
      direction?: 'LR' | 'TB';
      nodes: {id: string; label: string; group?: Group}[];
      edges: {from: string; to: string; label?: string}[];
    }
  | {type: 'flow'; heading: string; steps: {label: string; detail?: string}[]}
  | {type: 'code'; heading: string; file?: string; language?: string; code: string}
  | {type: 'stats'; heading: string; items: {value: string; label: string}[]}
  | {
      type: 'compare';
      heading: string;
      left: {title: string; items: string[]};
      right: {title: string; items: string[]};
    }
  | {type: 'table'; heading: string; columns: string[]; rows: string[][]}
  | {type: 'callout'; kind?: 'info' | 'warn' | 'key'; heading: string; text: string}
  | {type: 'example'; heading: string; lines: {label: string; value: string}[]};

export type Scene = {
  id: string;
  title: string;
  narration: string;
  visual: Visual;
  // preenchidos pelo build (scripts/build_timeline.py)
  durationInFrames: number;
  audioFrames: number;
  chapterIndex: number;
  chapterTitle: string;
  color: string;
};

export type Timeline = {
  title: string;
  fps: number;
  chapters: {id: string; title: string; color: string; startFrame: number; frames: number}[];
  scenes: Scene[];
  totalFrames: number;
  silent?: boolean; // sem narração: legenda é o texto principal
  music?: string | null; // trilha de fundo em public/
};
