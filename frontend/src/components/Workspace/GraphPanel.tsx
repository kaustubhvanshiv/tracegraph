import React, { useEffect, useMemo, useRef } from 'react';
import cytoscape from 'cytoscape';
import CytoscapeComponent from 'react-cytoscapejs';
import { useGraph } from '../../hooks/useGraph';
import { CYTOSCAPE_FCOSE_LAYOUT, CYTOSCAPE_STYLES } from '../../utils/cytoscapeConfig';

interface GraphPanelProps {
  investigationId: string;
  onNodeSelect?: (entityId: string | null) => void;
  highlightedEntityIds?: string[];
}

export const GraphPanel: React.FC<GraphPanelProps> = ({ investigationId, onNodeSelect, highlightedEntityIds = [] }) => {
  const { data, loading, error, fetchGraph } = useGraph(investigationId);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const elements = useMemo(() => {
    if (!data) return [];
    
    const rawNodes = data.nodes || [];
    const nodes = rawNodes.map(e => ({
      data: { 
        id: e.entity_id, 
        label: e.canonical_key, 
        entity_type: e.entity_type 
      }
    }));

    const rawEdges = data.edges || [];
    const edges = rawEdges.map(r => ({
      data: {
        id: `${r.source_id}-${r.target_id}-${r.type}`,
        source: r.source_id,
        target: r.target_id,
        type: r.type,
        combined_score: r.combined_score
      }
    }));

    return [...nodes, ...edges];
  }, [data]);

  const handleCyInit = (cy: cytoscape.Core) => {
    cyRef.current = cy;
    
    // Bind click events
    cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
      const node = evt.target;
      if (onNodeSelect) {
        onNodeSelect(node.id());
      }
    });

    cy.on('tap', (evt: cytoscape.EventObject) => {
      if (evt.target === cy) {
        // Clicked on background
        if (onNodeSelect) {
          onNodeSelect(null);
        }
      }
    });
  };

  // Apply highlights when highlightedEntityIds changes
  useEffect(() => {
    if (cyRef.current) {
      const cy = cyRef.current;
      cy.elements().removeClass('highlighted faded');
      
      if (highlightedEntityIds.length > 0) {
        // Find nodes to highlight
        const nodes = cy.nodes().filter((ele: cytoscape.NodeSingular) => highlightedEntityIds.includes(ele.id()));
        if (nodes.length > 0) {
          nodes.addClass('highlighted');
          // Add faded class to all other elements
          cy.elements().difference(nodes).addClass('faded');
        }
      }
    }
  }, [highlightedEntityIds, data]); // added data as dependency so it reapplies when graph loads

  return (
    <div className="flex flex-col h-full w-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="flex justify-between items-center p-4 border-b border-gray-100 bg-gray-50/50">
        <h2 className="text-lg font-semibold text-gray-800">Investigation Graph</h2>
        <button 
          onClick={() => fetchGraph()} 
          className="text-sm px-3 py-1.5 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-md shadow-sm transition-colors"
        >
          Refresh Graph
        </button>
      </div>
      
      <div className="flex-1 relative w-full h-full min-h-[400px]">
        {loading && !data && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-gray-600 font-medium">Loading graph data...</p>
            </div>
          </div>
        )}
        
        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-6 z-10">
            <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 max-w-md text-center">
              <p className="font-semibold mb-1">Error Loading Graph</p>
              <p className="text-sm">{error}</p>
            </div>
          </div>
        )}

        {elements.length === 0 && !loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <p className="text-gray-500">No nodes or edges found for this investigation.</p>
          </div>
        )}
        
        {elements.length > 0 && (
          <CytoscapeComponent
            elements={elements}
            style={{ width: '100%', height: '100%' }}
            stylesheet={CYTOSCAPE_STYLES}
            layout={CYTOSCAPE_FCOSE_LAYOUT}
            cy={handleCyInit}
            wheelSensitivity={0.1}
          />
        )}
      </div>
    </div>
  );
};
