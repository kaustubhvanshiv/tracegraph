import { useEffect, useRef, useCallback, useState } from 'react';
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
  const layoutRef = useRef<cytoscape.Layouts | null>(null);
  const onNodeSelectedRef = useRef(onNodeSelected);
  const [containerReady, setContainerReady] = useState(false);
  const [selectionPulse, setSelectionPulse] = useState<string | null>(null);
  const [reduceMotion, setReduceMotion] = useState(false);
  const prevSelectedRef = useRef<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Check prefers-reduced-motion on mount
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduceMotion(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  // Keep event handlers current without rebuilding the Cytoscape instance.
  useEffect(() => {
    onNodeSelectedRef.current = onNodeSelected;
  }, [onNodeSelected]);

  // Trigger selection pulse animation when selection changes
  useEffect(() => {
    if (selectedEntityId && selectedEntityId !== prevSelectedRef.current) {
      setSelectionPulse(selectedEntityId);
      // Clear after animation completes
      setTimeout(() => setSelectionPulse(null), 400);
    }
    prevSelectedRef.current = selectedEntityId;
  }, [selectedEntityId]);

  const stopLayout = useCallback(() => {
    const layout = layoutRef.current;
    layoutRef.current = null;
    layout?.stop();
  }, []);

  const runLayout = useCallback(() => {
    const cy = cyRef.current;
    if (!cy || cy.nodes().empty()) return;

    stopLayout();
    const baseOptions = { ...fcoseLayoutOptions, animate: !reduceMotion, animationDuration: reduceMotion ? 0 : 500 };
    const options = [baseOptions, { name: 'cose', animate: !reduceMotion }, { name: 'grid' }];
    for (const option of options) {
      try {
        const layout = cy.layout(option as cytoscape.LayoutOptions);
        layoutRef.current = layout;
        layout.one('layoutstop', () => {
          if (cy.destroyed() || cyRef.current !== cy || layoutRef.current !== layout) return;
          layoutRef.current = null;
          // Animated layouts may finish after the canvas has resized.
          cy.resize();
          cy.fit(undefined, 40);
        });
        layout.run();
        return;
      } catch {
        stopLayout();
      }
    }
  }, [stopLayout]);

  // Init cytoscape when container has dimensions
  useEffect(() => {
    if (!containerRef.current || !containerReady) return;

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
      onNodeSelectedRef.current(evt.target.data('entity_id') as string);
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) onNodeSelectedRef.current(null);
    });

    cyRef.current = cy;
    return () => {
      stopLayout();
      if (cyRef.current === cy) cyRef.current = null;
      cy.destroy();
    };
  }, [containerReady, stopLayout]);

  // ResizeObserver to detect when container gets dimensions
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          setContainerReady(true);
          if (cyRef.current) {
            cyRef.current.resize();
            cyRef.current.fit(undefined, 40);
          }
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Load graph data
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    stopLayout();
    if (!graph) {
      cy.elements().remove();
      return;
    }

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
    cy.resize();

    if (nodes.length > 0) {
      runLayout();
    }
  }, [containerReady, graph, runLayout, stopLayout]);

  // Highlight selected + related nodes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass('highlighted dimmed');

    if (selectedEntityId) {
      const selected = cy.nodes(`[id = "${selectedEntityId}"]`);
      if (selected.length) {
        const connected = selected.neighborhood();
        cy.elements().addClass('dimmed');
        selected.addClass('highlighted').removeClass('dimmed');
        connected.addClass('highlighted').removeClass('dimmed');
      }
    } else if (highlightedEntityIds.length) {
      cy.elements().addClass('dimmed');
      highlightedEntityIds.forEach((id) => {
        const target = cy.nodes(`[id = "${id}"]`);
        if (target.length) {
          target.addClass('highlighted').removeClass('dimmed');
        }
      });
    }
  }, [containerReady, graph, selectedEntityId, highlightedEntityIds]);

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

  const toggleFullscreen = useCallback(() => {
    if (!isFullscreen) {
      containerRef.current?.requestFullscreen?.().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  }, [isFullscreen]);

  // Handle fullscreen change events (e.g., user presses Esc)
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);
  return (
    <div className={`sentinel-card flex flex-col h-full min-h-0 overflow-hidden ${selectionPulse ? 'selection-pulse' : ''} ${isFullscreen ? 'fixed inset-0 z-50 rounded-none' : ''}`}>
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-outline-variant/20">
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
            { label: '⟳', title: 'Re-layout', fn: runLayout },
          ].map(({ label, title, fn }) => (
            <button
              key={title}
              title={title}
              onClick={fn}
              className="w-7 h-7 md:w-8 md:h-8 flex items-center justify-center rounded text-on-surface-muted hover:text-primary hover:bg-surface-highest text-base transition-colors touch-manipulation focus-ring"
            >
              {label}
            </button>
          ))}
          <button
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
            onClick={toggleFullscreen}
            className="w-7 h-7 md:w-8 md:h-8 flex items-center justify-center rounded text-on-surface-muted hover:text-primary hover:bg-surface-highest text-base transition-colors touch-manipulation focus-ring"
          >
            {isFullscreen ? '⛶' : '⛶'}
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="relative flex-1 min-h-0 overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface/80 z-10 rounded-b-xl loading-pulse">
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
        <div
          ref={containerRef}
          className="absolute inset-0 touch-pan-x touch-pan-y touch-pinch-zoom"
          style={{ touchAction: 'pan-x pan-y pinch-zoom' }}
        />
      </div>

      {/* Legend */}
      <div className="shrink-0 px-4 py-2 flex items-center gap-2 md:gap-3 flex-wrap border-t border-outline-variant/20">
        {ENTITY_TYPES.map((t) => (
          <span key={t} className="flex items-center gap-1 text-xs text-on-surface-muted whitespace-nowrap">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: ENTITY_COLORS[t] }}
            />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
