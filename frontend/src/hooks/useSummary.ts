import { useState, useCallback } from 'react';
import { summaryApi } from '../services';
import { SummaryResult } from '../types';

export const useSummary = (investigationId: string) => {
  const [data, setData] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string, isUnavailable: boolean } | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await summaryApi.getSummary(investigationId);
      setData(response.data);
    } catch (err) {
      const errorObj = err as any; // Safe cast for API error handling
      
      // If it's just a 404 (no summary yet), that's not an error. Leave data as null.
      if (errorObj.code === 'SUMMARY_NOT_FOUND' || errorObj?.response?.status === 404) {
        return;
      }
      
      const isUnavailable = errorObj.code === 'AI_UNAVAILABLE' || errorObj.code === 'SERVICE_UNAVAILABLE' || errorObj?.response?.status === 503;
      
      setError({
        message: errorObj.message || 'Failed to fetch AI summary',
        isUnavailable
      });
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  const generateSummary = useCallback(async (forceRefresh: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const response = await summaryApi.generateSummary(investigationId, forceRefresh);
      setData(response.data);
    } catch (err) {
      const errorObj = err as any;
      const isUnavailable = errorObj.code === 'AI_UNAVAILABLE' || errorObj.code === 'SERVICE_UNAVAILABLE' || errorObj?.response?.status === 503;
      
      setError({
        message: errorObj.message || 'Failed to generate AI summary',
        isUnavailable
      });
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  return {
    data,
    loading,
    error,
    fetchSummary,
    generateSummary
  };
};
