import cytoscape from 'cytoscape';
// @ts-ignore
import fcose from 'cytoscape-fcose';

cytoscape.use(fcose);

export const CYTOSCAPE_FCOSE_LAYOUT = {
  name: 'fcose',
  quality: 'default',
  randomize: true,
  animate: true,
  animationDuration: 1000,
  fit: true,
  padding: 30,
  nodeDimensionsIncludeLabels: true,
  uniformNodeDimensions: false,
  packComponents: true,
  step: 'all',
};

// Vibrant color palette
const COLORS = {
  host: '#3b82f6', // blue-500
  user: '#8b5cf6', // violet-500
  ip: '#10b981', // emerald-500
  process: '#f59e0b', // amber-500
  file: '#ef4444', // red-500
  default: '#6b7280', // gray-500
  edge: '#9ca3af', // gray-400
  edgeSelected: '#4b5563', // gray-600
  label: '#1f2937', // gray-800
};

export const CYTOSCAPE_STYLES: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      'background-color': (ele: any) => {
        const type = ele.data('entity_type');
        return COLORS[type as keyof typeof COLORS] || COLORS.default;
      },
      'label': 'data(label)',
      'color': COLORS.label,
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 5,
      'font-size': '12px',
      'font-family': 'Inter, sans-serif',
      'font-weight': 'bold',
      'border-width': 2,
      'border-color': '#ffffff',
      'width': 30,
      'height': 30,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#000000',
      'border-opacity': 0.5,
    },
  },
  {
    selector: 'edge',
    style: {
      'width': (ele: any) => {
        // Line width correlates to combined_score slightly
        const score = ele.data('combined_score') || 0.5;
        return Math.max(1, score * 3);
      },
      'line-color': COLORS.edge,
      'target-arrow-color': COLORS.edge,
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(type)',
      'font-size': '10px',
      'color': COLORS.edgeSelected,
      'text-rotation': 'autorotate',
      'text-background-opacity': 1,
      'text-background-color': '#ffffff',
      'text-background-padding': '2px',
    },
  },
  {
    selector: 'edge:selected',
    style: {
      'line-color': COLORS.edgeSelected,
      'target-arrow-color': COLORS.edgeSelected,
      'width': 3,
    },
  },
  {
    selector: '.highlighted',
    style: {
      'border-width': 4,
      'border-color': '#000',
      'shadow-blur': 10,
      'shadow-color': '#000',
      'shadow-opacity': 0.8,
    } as any
  },
  {
    selector: '.faded',
    style: {
      'opacity': 0.2,
    }
  }
];
