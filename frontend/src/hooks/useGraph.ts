import { useState, useCallback } from 'react';
import { graphApi } from '../services/graphApi';
import type { GraphResult, EntityDetail } from '../types';

export function useGraph(investigationId: string) {
  const [graph, setGraph] = useState<GraphResult | null>(null);
  const [entityDetail, setEntityDetail] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await graphApi.getGraph(investigationId);
      setGraph(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const fetchEntityDetail = useCallback(
    async (entityId: string) => {
      try {
        const data = await graphApi.getEntity(investigationId, entityId);
        setEntityDetail(data);
      } catch {
        setEntityDetail(null);
      }
    },
    [investigationId]
  );

  const pivot = useCallback(
    async (entityId: string) => {
      setLoading(true);
      try {
        const data = await graphApi.pivot(investigationId, entityId);
        setGraph(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Pivot failed');
      } finally {
        setLoading(false);
      }
    },
    [investigationId]
  );

  return { graph, entityDetail, loading, error, fetchGraph, fetchEntityDetail, pivot };
}
