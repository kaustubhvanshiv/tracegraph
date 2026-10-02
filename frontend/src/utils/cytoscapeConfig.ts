import type { EntityType } from '../types';

/** Node background colour per entity type (Obsidian Sentinel palette) */
export const ENTITY_COLORS: Record<EntityType, string> = {
  User: '#3b82f6',
  Host: '#10b981',
  Server: '#ef4444',
  IP: '#8b5cf6',
  Process: '#f59e0b',
  File: '#64748b',
};

// Use plain objects — cytoscape accepts { selector, css } OR { selector, style }
// at runtime. We cast to `object[]` to avoid strict TS fighting us on the union type.
export const cytoscapeStylesheet = [
  {
    selector: 'node',
    css: {
      'background-color': '#4edea3',
      'label': 'data(label)',
      'color': '#dae2fd',
      'font-size': '11px',
      'font-family': 'Inter, sans-serif',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 4,
      'width': 36,
      'height': 36,
      'border-width': 2,
      'border-color': '#3c4a42',
      'text-background-color': '#0b1326',
      'text-background-opacity': 0.7,
      'text-background-padding': '2px',
    },
  },
  // Per-type node colouring
  ...(['User', 'Host', 'Server', 'IP', 'Process', 'File'] as EntityType[]).map((t) => ({
    selector: `node[entity_type = "${t}"]`,
    css: { 'background-color': ENTITY_COLORS[t] },
  })),
  // Selected / highlighted node
  {
    selector: 'node:selected, node.highlighted',
    css: {
      'border-width': 3,
      'border-color': '#4edea3',
      'border-opacity': 1,
      'overlay-color': '#4edea3',
      'overlay-padding': 6,
      'overlay-opacity': 0.15,
    },
  },
  // Dimmed node
  {
    selector: 'node.dimmed',
    css: { 'opacity': 0.25 },
  },
  // Base edge
  {
    selector: 'edge',
    css: {
      'width': 1.5,
      'line-color': '#3c4a42',
      'target-arrow-color': '#3c4a42',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(label)',
      'font-size': '9px',
      'color': '#86948a',
      'font-family': 'Inter, sans-serif',
      'text-rotation': 'autorotate',
      'text-background-color': '#0b1326',
      'text-background-opacity': 0.8,
      'text-background-padding': '2px',
    },
  },
  // Highlighted edge
  {
    selector: 'edge.highlighted',
    css: {
      'line-color': '#4edea3',
      'target-arrow-color': '#4edea3',
      'width': 2.5,
    },
  },
  // Dimmed edge
  {
    selector: 'edge.dimmed',
    css: { 'opacity': 0.15 },
  },
// cytoscape accepts this shape at runtime; cast to bypass strict union typing
] as unknown as cytoscape.StylesheetCSS[];

/** fCoSE layout options */
export const fcoseLayoutOptions = {
  name: 'fcose',
  animate: true,
  animationDuration: 500,
  fit: true,
  padding: 40,
  nodeRepulsion: 4500,
  idealEdgeLength: 120,
  edgeElasticity: 0.45,
  numIter: 2500,
  tile: true,
  tilingPaddingVertical: 10,
  tilingPaddingHorizontal: 10,
};
