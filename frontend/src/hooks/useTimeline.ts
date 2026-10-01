import { useState, useCallback } from 'react';
import { timelineApi } from '../services';
import { TimelineResult } from '../types';

export const useTimeline = (investigationId: string) => {
  const [data, setData] = useState<TimelineResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTimeline = useCallback(async (params?: {
    start_time?: string;
    end_time?: string;
    entity_id?: string;
    event_type?: string;
    severity?: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const response = await timelineApi.getTimeline(investigationId, params);
      setData(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch timeline');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  return {
    data,
    loading,
    error,
    fetchTimeline
  };
};
