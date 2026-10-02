import { useState, useCallback } from 'react';
import { timelineApi } from '../services/timelineApi';
import type { TimelineResult, EvidenceDetail } from '../types';

export function useTimeline(investigationId: string) {
  const [timeline, setTimeline] = useState<TimelineResult | null>(null);
  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTimeline = useCallback(
    async (params?: {
      entity_id?: string;
      event_type?: string;
      severity?: string;
      limit?: number;
    }) => {
      setLoading(true);
      setError(null);
      try {
        const data = await timelineApi.getTimeline(investigationId, params);
        setTimeline(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load timeline');
      } finally {
        setLoading(false);
      }
    },
    [investigationId]
  );

  const fetchEvidence = useCallback(
    async (eventId: string) => {
      setEvidenceLoading(true);
      try {
        const data = await timelineApi.getEvidence(investigationId, eventId);
        setEvidence(data);
      } catch {
        setEvidence(null);
      } finally {
        setEvidenceLoading(false);
      }
    },
    [investigationId]
  );

  return {
    timeline,
    evidence,
    loading,
    evidenceLoading,
    error,
    fetchTimeline,
    fetchEvidence,
  };
}
