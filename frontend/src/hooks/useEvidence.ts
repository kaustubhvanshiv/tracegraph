import { useState, useCallback } from 'react';
import { eventsApi } from '../services';
import { EvidenceDetail } from '../types';

export const useEvidence = (investigationId: string) => {
  const [data, setData] = useState<EvidenceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEvidence = useCallback(async (eventId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await eventsApi.getEvidence(investigationId, eventId);
      setData(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch evidence details');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  return {
    data,
    loading,
    error,
    fetchEvidence
  };
};
