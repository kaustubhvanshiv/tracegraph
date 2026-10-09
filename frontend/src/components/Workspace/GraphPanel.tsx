import { useEffect, useRef, useCallback, useState } from 'react';
import cytoscape from 'cytoscape';
import type { GraphResult, EntityType } from '../../types';
import { cytoscapeStylesheet, fcoseLayoutOptions, ENTITY_COLORS } from '../../utils/cytoscapeConfig';

interface Props {
  graph: GraphResult | null;
  loading: boolean;
  error: string | null;
  selectedEntityId: string | null;
  highlightedEntityIds: string[];
  onNodeSelected: (entityId: string | null) => void;
}

const ENTITY_TYPES: EntityType[] = ['User', 'Host', 'Server', 'IP', 'Process', 'File'];

// ── Toolbar SVG icons ──────────────────────────────────────────────────────
function IconZoomIn() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" /><line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}
function IconZoomOut() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}
function IconFit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
      <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );
}
function IconRelayout() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M23 4v6h-6" /><path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}
function IconFullscreen() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
      <polyline points="21 15 21 21 15 21" /><polyline points="3 9 3 3 9 3" />
    </svg>
  );
}
function IconExitFullscreen() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <polyline points="8 3 3 3 3 8" /><polyline points="21 8 21 3 16 3" />
      <polyline points="3 16 3 21 8 21" /><polyline points="16 21 21 21 21 16" />
    </svg>
  );
}
function IconClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
function IconFilter() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  );
}

// Entity type icon (simple letter-based fallback)
function EntityTypeIcon({ type }: { type: string }) {
  const icons: Record<string, string> = {
    User: 'U', Host: 'H', Server: 'S', IP: 'IP', Process: 'P', File: 'F',
  };
  return (
    <span
      className="inline-flex items-center justify-center w-6 h-6 rounded text-[10px] font-bold shrink-0"
      style={{
        backgroundColor: ENTITY_COLORS[type as EntityType] ?? '#4edea3',
        color: '#0b1326',
      }}
    >
      {icons[type] ?? type[0]}
    </span>
  );
}

// ── Node detail card (shown when a node is selected) ────────────────────────
interface NodeCardProps {
  nodeData: { label: string; entity_type: string; entity_id: string } | null;
  eventCount?: number;
  onClose: () => void;
}
function NodeDetailCard({ nodeData, eventCount, onClose }: NodeCardProps) {
  if (!nodeData) return null;
  return (
    <div className="absolute top-3 left-3 z-20 w-64 bg-surface-highest/95 backdrop-blur-sm rounded-xl shadow-sentinel-md border border-outline-variant/20 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-2.5 px-3 py-2.5 border-b border-outline-variant/10">
        <EntityTypeIcon type={nodeData.entity_type} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-on-surface truncate">{nodeData.label}</p>
          <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-wide">{nodeData.entity_type} Entity</p>
        </div>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded text-on-surface-muted hover:text-on-surface hover:bg-surface-high transition-colors shrink-0"
          aria-label="Close"
        >
          <IconClose />
        </button>
      </div>

      {/* Tier badge */}
      <div className="px-3 pt-2.5 pb-1 flex items-center gap-2">
        <span className="badge-pill bg-secondary/20 text-secondary border border-secondary/30 font-mono text-[10px] uppercase tracking-widest">
          TIER 1 · HIGH
        </span>
      </div>

      {/* Metadata */}
      <div className="px-3 py-2 space-y-1.5">
        <div>
          <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-widest mb-0.5">Entity ID</p>
          <p className="text-xs text-on-surface font-mono truncate opacity-60">{nodeData.entity_id.slice(0, 16)}…</p>
        </div>
      </div>

      {/* Correlated events */}
      {eventCount !== undefined && eventCount > 0 && (
        <div className="mx-3 mb-3 px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/10 flex items-center justify-between">
          <span className="text-[10px] font-mono text-on-surface-muted uppercase tracking-wide">Correlated Events</span>
          <span className="text-sm font-bold text-primary font-mono">{eventCount.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
export default function GraphPanel({
  graph,
  loading,
  error,
  selectedEntityId,
  highlightedEntityIds,
  onNodeSelected,
}: Props) {
  // The panel wrapper ref — this is what goes fullscreen (not the cy canvas)
  const panelRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const layoutRef = useRef<cytoscape.Layouts | null>(null);
  const onNodeSelectedRef = useRef(onNodeSelected);

  const [containerReady, setContainerReady] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  // Ripple position for click-position pulse (null = hidden)
  const [ripple, setRipple] = useState<{ x: number; y: number; key: number } | null>(null);
  const prevSelectedRef = useRef<string | null>(null);

  // Node card data
  const [selectedNodeData, setSelectedNodeData] = useState<{
    label: string; entity_type: string; entity_id: string;
  } | null>(null);

  // Entity type filter
  const [activeTypeFilter, setActiveTypeFilter] = useState<EntityType | null>(null);

  // prefers-reduced-motion
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduceMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduceMotion(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  useEffect(() => { onNodeSelectedRef.current = onNodeSelected; }, [onNodeSelected]);

  // ── Fullscreen: attach to panel wrapper, not cy canvas ──────────────────
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      panelRef.current?.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  }, []);

  useEffect(() => {
    const onChange = () => {
      const inFs = document.fullscreenElement === panelRef.current;
      setIsFullscreen(inFs);
      // Give browser a tick to settle, then resize cy
      setTimeout(() => {
        cyRef.current?.resize();
        cyRef.current?.fit(undefined, 40);
      }, 80);
    };
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // Keyboard: Esc already handled by browser for fullscreen; also support F key
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'f' && !e.ctrlKey && !e.metaKey && !e.altKey) toggleFullscreen();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggleFullscreen]);

  // ── Layout helpers ───────────────────────────────────────────────────────
  const stopLayout = useCallback(() => {
    const l = layoutRef.current;
    layoutRef.current = null;
    l?.stop();
  }, []);

  const runLayout = useCallback(() => {
    const cy = cyRef.current;
    if (!cy || cy.nodes().empty()) return;
    stopLayout();
    const base = { ...fcoseLayoutOptions, animate: !reduceMotion, animationDuration: reduceMotion ? 0 : 500 };
    for (const opt of [base, { name: 'cose', animate: !reduceMotion }, { name: 'grid' }]) {
      try {
        const l = cy.layout(opt as cytoscape.LayoutOptions);
        layoutRef.current = l;
        l.one('layoutstop', () => {
          if (cy.destroyed() || cyRef.current !== cy || layoutRef.current !== l) return;
          layoutRef.current = null;
          cy.resize();
          cy.fit(undefined, 40);
        });
        l.run();
        return;
      } catch { stopLayout(); }
    }
  }, [stopLayout, reduceMotion]);

  // ── Init Cytoscape ───────────────────────────────────────────────────────
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
      const data = evt.target.data() as { entity_id: string; label: string; entity_type: string };
      onNodeSelectedRef.current(data.entity_id);
      setSelectedNodeData({ label: data.label, entity_type: data.entity_type, entity_id: data.entity_id });

      // Spawn ripple at the node's rendered position on screen
      if (containerRef.current) {
        const rp = evt.target.renderedPosition() as { x: number; y: number };
        setRipple({ x: rp.x, y: rp.y, key: Date.now() });
      }
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onNodeSelectedRef.current(null);
        setSelectedNodeData(null);
      }
    });

    cyRef.current = cy;
    return () => {
      stopLayout();
      if (cyRef.current === cy) cyRef.current = null;
      cy.destroy();
    };
  }, [containerReady, stopLayout]);

  // ── ResizeObserver ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      for (const e of entries) {
        if (e.contentRect.width > 0 && e.contentRect.height > 0) {
          setContainerReady(true);
          cyRef.current?.resize();
          cyRef.current?.fit(undefined, 40);
        }
      }
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // ── Load graph data ──────────────────────────────────────────────────────
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    stopLayout();
    if (!graph) { cy.elements().remove(); return; }

    const nodes = graph.nodes.map((n) => ({
      data: { id: n.entity_id, label: n.canonical_key, entity_id: n.entity_id, entity_type: n.entity_type },
    }));
    const edges = graph.edges.map((e) => ({
      data: { id: e.relationship_id, source: e.source_entity_id, target: e.target_entity_id, label: e.relationship_type, relationship_id: e.relationship_id },
    }));

    cy.elements().remove();
    cy.add([...nodes, ...edges]);
    cy.resize();
    if (nodes.length > 0) runLayout();
  }, [containerReady, graph, runLayout, stopLayout]);

  // ── Highlight / dim ──────────────────────────────────────────────────────
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass('highlighted dimmed');
    if (selectedEntityId) {
      const sel = cy.nodes(`[id = "${selectedEntityId}"]`);
      if (sel.length) {
        cy.elements().addClass('dimmed');
        sel.addClass('highlighted').removeClass('dimmed');
        sel.neighborhood().addClass('highlighted').removeClass('dimmed');
      }
    } else if (highlightedEntityIds.length) {
      cy.elements().addClass('dimmed');
      highlightedEntityIds.forEach((id) => {
        cy.nodes(`[id = "${id}"]`).addClass('highlighted').removeClass('dimmed');
      });
    }
  }, [containerReady, graph, selectedEntityId, highlightedEntityIds]);

  // ── Entity type filter ───────────────────────────────────────────────────
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    if (!activeTypeFilter) {
      cy.nodes().style('display', 'element');
      cy.edges().style('display', 'element');
    } else {
      cy.nodes().forEach((n) => {
        n.style('display', n.data('entity_type') === activeTypeFilter ? 'element' : 'none');
      });
      // Hide edges where either endpoint is hidden
      cy.edges().forEach((e) => {
        const src = e.source().style('display');
        const tgt = e.target().style('display');
        e.style('display', src === 'none' || tgt === 'none' ? 'none' : 'element');
      });
    }
  }, [activeTypeFilter, graph]);

  // ── Toolbar actions ──────────────────────────────────────────────────────
  const fitView = useCallback(() => { cyRef.current?.fit(undefined, 40); }, []);
  const zoomIn = useCallback(() => {
    const cy = cyRef.current; if (cy) cy.zoom({ level: cy.zoom() * 1.25, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);
  const zoomOut = useCallback(() => {
    const cy = cyRef.current; if (cy) cy.zoom({ level: cy.zoom() * 0.8, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      ref={panelRef}
      className={`flex flex-col min-h-0 overflow-hidden bg-surface-container rounded-xl ${isFullscreen ? 'rounded-none' : ''}`}
      style={isFullscreen ? { height: '100dvh', width: '100dvw' } : { height: '100%' }}
    >
      {/* ── Header ── */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 bg-surface-high/60">
        {/* Left: title + node/edge counts */}
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-sm font-semibold text-on-surface">Entity Graph</span>
          {graph && (
            <span className="badge-pill bg-surface-highest text-on-surface-muted font-mono text-[10px]">
              {graph.nodes.length} nodes · {graph.edges.length} edges
            </span>
          )}
        </div>

        {/* Right: toolbar */}
        <div className="flex items-center gap-0.5">
          {[
            { icon: <IconZoomIn />, title: 'Zoom in (scroll)', fn: zoomIn },
            { icon: <IconZoomOut />, title: 'Zoom out', fn: zoomOut },
            { icon: <IconFit />, title: 'Fit view', fn: fitView },
            { icon: <IconRelayout />, title: 'Re-run layout', fn: runLayout },
          ].map(({ icon, title, fn }) => (
            <button
              key={title}
              title={title}
              onClick={fn}
              className="w-8 h-8 flex items-center justify-center rounded text-on-surface-muted hover:text-primary hover:bg-surface-highest transition-colors touch-manipulation focus-ring"
            >
              {icon}
            </button>
          ))}

          {/* Separator */}
          <div className="w-px h-4 bg-outline-variant/30 mx-1" />

          <button
            title={isFullscreen ? 'Exit fullscreen (F)' : 'Enter fullscreen (F)'}
            onClick={toggleFullscreen}
            className="w-8 h-8 flex items-center justify-center rounded text-on-surface-muted hover:text-primary hover:bg-surface-highest transition-colors touch-manipulation focus-ring"
          >
            {isFullscreen ? <IconExitFullscreen /> : <IconFullscreen />}
          </button>
        </div>
      </div>

      {/* ── Canvas area ── */}
      <div className="relative flex-1 min-h-0 overflow-hidden">
        {/* Loading */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface/80 z-10">
            <div className="flex flex-col items-center gap-3">
              <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              <p className="text-primary text-xs font-mono">Loading graph…</p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <p className="text-error text-sm">{error}</p>
          </div>
        )}

        {/* Empty */}
        {!graph && !loading && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center z-10 gap-2">
            <svg className="w-10 h-10 text-on-surface-muted opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <circle cx="12" cy="12" r="3" /><circle cx="4" cy="6" r="2" />
              <circle cx="20" cy="6" r="2" /><circle cx="4" cy="18" r="2" />
              <circle cx="20" cy="18" r="2" />
              <line x1="6" y1="7" x2="10" y2="11" /><line x1="14" y1="11" x2="18" y2="7" />
              <line x1="6" y1="17" x2="10" y2="13" /><line x1="14" y1="13" x2="18" y2="17" />
            </svg>
            <p className="text-on-surface-muted text-sm">No graph data loaded yet.</p>
          </div>
        )}

        {/* Node detail card (overlaid on canvas) */}
        {selectedNodeData && (
          <NodeDetailCard
            nodeData={selectedNodeData}
            onClose={() => {
              setSelectedNodeData(null);
              onNodeSelected(null);
            }}
          />
        )}

        {/* Entity type filter chip (top-right of canvas) */}
        <div className="absolute top-3 right-3 z-20 flex items-center gap-1.5">
          <div className="flex items-center gap-1.5 bg-surface-highest/90 backdrop-blur-sm rounded-full px-2.5 py-1.5 border border-outline-variant/20">
            <IconFilter />
            <span className="text-[10px] font-mono text-on-surface-muted uppercase tracking-wide">Filter</span>
            {activeTypeFilter ? (
              <button
                onClick={() => setActiveTypeFilter(null)}
                className="flex items-center gap-1 ml-0.5"
              >
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ backgroundColor: ENTITY_COLORS[activeTypeFilter] }}
                />
                <span className="text-[10px] font-mono text-on-surface">{activeTypeFilter}</span>
                <span className="text-on-surface-muted hover:text-error transition-colors ml-0.5"><IconClose /></span>
              </button>
            ) : (
              <span className="text-[10px] font-mono text-on-surface-muted">All</span>
            )}
          </div>
        </div>

        {/* Positional ripple — spawns at exact node click coordinates */}
        {ripple && !reduceMotion && (
          <span
            key={ripple.key}
            className="pointer-events-none absolute z-30 rounded-full"
            style={{
              left: ripple.x,
              top: ripple.y,
              width: 0,
              height: 0,
              transform: 'translate(-50%, -50%)',
              // inline animation so it always originates at the node
              animation: 'graph-ripple 500ms ease-out forwards',
            }}
          />
        )}

        {/* Cytoscape canvas */}
        <div
          ref={containerRef}
          className="absolute inset-0 touch-pan-x touch-pan-y touch-pinch-zoom"
          style={{ touchAction: 'pan-x pan-y pinch-zoom' }}
        />
      </div>

      {/* ── Footer: Legend + type filter ── */}
      <div className="shrink-0 px-4 py-2.5 flex items-center justify-between bg-surface-high/40 border-t border-outline-variant/10">
        {/* Legend */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[10px] font-mono text-on-surface-muted uppercase tracking-widest hidden sm:block">Entity Schema</span>
          {ENTITY_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => setActiveTypeFilter(activeTypeFilter === t ? null : t)}
              title={`Filter: ${t} nodes`}
              className={`flex items-center gap-1.5 text-xs transition-all touch-manipulation rounded px-1.5 py-0.5 ${
                activeTypeFilter === t
                  ? 'bg-surface-highest text-on-surface'
                  : 'text-on-surface-muted hover:text-on-surface'
              }`}
            >
              <span
                className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 transition-all ${
                  activeTypeFilter === t ? 'scale-125' : ''
                }`}
                style={{ backgroundColor: ENTITY_COLORS[t] }}
              />
              <span className="font-mono text-[11px]">{t}</span>
            </button>
          ))}
        </div>

        {/* Zoom level indicator */}
        <span className="text-[10px] font-mono text-on-surface-muted hidden sm:block opacity-50 shrink-0 ml-4">
          100%
        </span>
      </div>
    </div>
  );
}
