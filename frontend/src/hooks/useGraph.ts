import { useState, useCallback } from 'react';
import { graphApi } from '../services';
import { GraphResult } from '../types';

export const useGraph = (investigationId: string) => {
  const [data, setData] = useState<GraphResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async (params?: {
    entity_type?: string;
    relationship_type?: string;
    start_time?: string;
    end_time?: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const response = await graphApi.getGraph(investigationId, params);
      setData(response.data);
    } catch (err) {
      const error = err as Error | { message?: string };
      setError(error.message || 'Failed to fetch graph');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const pivot = useCallback(async (entityId: string, hops: number = 1) => {
    setLoading(true);
    setError(null);
    try {
      const response = await graphApi.pivot(investigationId, entityId, hops);
      // Append pivot results to current graph data, avoiding duplicates
      setData(prev => {
        if (!prev) return response.data;
        
        const rawNodes = prev.nodes || [];
        const rawEdges = prev.edges || [];
        const resNodes = response.data.nodes || [];
        const resEdges = response.data.edges || [];

        const existingEntityIds = new Set(rawNodes.map(e => e.entity_id));
        const newEntities = resNodes.filter(e => !existingEntityIds.has(e.entity_id));
        
        const existingEdgeIds = new Set(rawEdges.map(r => `${r.source_id}-${r.target_id}-${r.type}`));
        const newRelationships = resEdges.filter(r => !existingEdgeIds.has(`${r.source_id}-${r.target_id}-${r.type}`));
        
        return {
          investigation_id: prev.investigation_id,
          nodes: [...rawNodes, ...newEntities],
          edges: [...rawEdges, ...newRelationships]
        };
      });
    } catch (err) {
      const error = err as Error | { message?: string };
      setError(error.message || 'Failed to pivot graph');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  return {
    data,
    loading,
    error,
    fetchGraph,
    pivot
  };
};
