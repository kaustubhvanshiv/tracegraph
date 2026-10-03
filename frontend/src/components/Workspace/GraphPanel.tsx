import { useEffect, useRef, useCallback } from 'react';
import cytoscape from 'cytoscape';
import type { GraphResult } from '../../types';
import { cytoscapeStylesheet, fcoseLayoutOptions, ENTITY_COLORS } from '../../utils/cytoscapeConfig';

interface Props {
  graph: GraphResult | null;
  loading: boolean;
  error: string | null;
  selectedEntityId: string | null;
  highlightedEntityIds: string[];
  onNodeSelected: (entityId: string | null) => void;
}

const ENTITY_TYPES = ['User', 'Host', 'Server', 'IP', 'Process', 'File'] as const;

export default function GraphPanel({
  graph,
  loading,
  error,
  selectedEntityId,
  highlightedEntityIds,
  onNodeSelected,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  // Init cytoscape
  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: cytoscapeStylesheet,
      layout: { name: 'preset' },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      minZoom: 0.1,
      maxZoom: 3,
    });

    cy.on('tap', 'node', (evt) => {
      onNodeSelected(evt.target.data('entity_id') as string);
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) onNodeSelected(null);
    });

    cyRef.current = cy;
    return () => { cy.destroy(); };
  }, [onNodeSelected]);

  // Load graph data
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !graph) return;

    const nodes = graph.nodes.map((n) => ({
      data: {
        id: n.entity_id,
        label: n.canonical_key,
        entity_id: n.entity_id,
        entity_type: n.entity_type,
      },
    }));

    const edges = graph.edges.map((e) => ({
      data: {
        id: e.relationship_id,
        source: e.source_entity_id,
        target: e.target_entity_id,
        label: e.relationship_type,
        relationship_id: e.relationship_id,
      },
    }));

    cy.elements().remove();
    cy.add([...nodes, ...edges]);
    cy.layout(fcoseLayoutOptions as cytoscape.LayoutOptions).run();
  }, [graph]);

  // Highlight selected + related nodes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass('highlighted dimmed');

    if (selectedEntityId) {
      const selected = cy.$(`#${selectedEntityId}`);
      if (selected.length) {
        const connected = selected.neighborhood();
        cy.elements().addClass('dimmed');
        selected.addClass('highlighted').removeClass('dimmed');
        connected.addClass('highlighted').removeClass('dimmed');
      }
    } else if (highlightedEntityIds.length) {
      cy.elements().addClass('dimmed');
      highlightedEntityIds.forEach((id) => {
        cy.$(`#${id}`).addClass('highlighted').removeClass('dimmed');
      });
    }
  }, [selectedEntityId, highlightedEntityIds]);

  const fitView = useCallback(() => {
    cyRef.current?.fit(undefined, 40);
  }, []);
  const zoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom(cy.zoom() * 1.2);
  }, []);
  const zoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom(cy.zoom() * 0.8);
  }, []);
  const reLayout = useCallback(() => {
    cyRef.current?.layout(fcoseLayoutOptions as cytoscape.LayoutOptions).run();
  }, []);

  return (
    <div className="sentinel-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-on-surface">Entity Graph</span>
          {graph && (
            <span className="badge-pill bg-surface-highest text-on-surface-muted mono">
              {graph.nodes.length} nodes · {graph.edges.length} edges
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {[
            { label: '+', title: 'Zoom in', fn: zoomIn },
            { label: '−', title: 'Zoom out', fn: zoomOut },
            { label: '⊡', title: 'Fit view', fn: fitView },
            { label: '⟳', title: 'Re-layout', fn: reLayout },
          ].map(({ label, title, fn }) => (
            <button
              key={title}
              title={title}
              onClick={fn}
              className="w-7 h-7 flex items-center justify-center rounded text-on-surface-muted hover:text-primary hover:bg-surface-highest text-base transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div className="relative flex-1">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface/80 z-10 rounded-b-xl">
            <div className="flex items-center gap-2 text-primary text-sm">
              <span className="animate-spin text-lg">◌</span> Loading graph…
            </div>
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <p className="text-error text-sm">{error}</p>
          </div>
        )}
        {!graph && !loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <p className="text-on-surface-muted text-sm">No graph data yet.</p>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full rounded-b-xl" />
      </div>

      {/* Legend */}
      <div className="px-4 py-2 flex items-center gap-3 flex-wrap border-t border-outline-variant/20">
        {ENTITY_TYPES.map((t) => (
          <span key={t} className="flex items-center gap-1 text-xs text-on-surface-muted">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: ENTITY_COLORS[t] }}
            />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
