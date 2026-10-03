import { useState, useCallback } from 'react';
import { summaryApi } from '../services/summaryApi';
import type { SummaryResult } from '../types';

export const useSummary = (investigationId: string) => {
  const [data, setData] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; isUnavailable: boolean } | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await summaryApi.get(investigationId);
      setData(res);
    } catch (err: any) {
      if (err.code === 'SUMMARY_NOT_FOUND' || err?.response?.status === 404) {
        return;
      }
      const isUnavailable =
        err.code === 'AI_UNAVAILABLE' ||
        err.code === 'SERVICE_UNAVAILABLE' ||
        err?.response?.status === 503;

      setError({
        message: err.message || 'Failed to fetch AI summary',
        isUnavailable,
      });
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const generateSummary = useCallback(
    async (forceRefresh: boolean = false) => {
      setLoading(true);
      setError(null);
      try {
        const res = await summaryApi.generate(investigationId, forceRefresh);
        setData(res);
      } catch (err: any) {
        const isUnavailable =
          err.code === 'AI_UNAVAILABLE' ||
          err.code === 'SERVICE_UNAVAILABLE' ||
          err?.response?.status === 503;

        setError({
          message: err.message || 'Failed to generate AI summary',
          isUnavailable,
        });
      } finally {
        setLoading(false);
      }
    },
    [investigationId]
  );

  return {
    data,
    loading,
    error,
    fetchSummary,
    getSummary: fetchSummary,
    generateSummary,
  };
};
