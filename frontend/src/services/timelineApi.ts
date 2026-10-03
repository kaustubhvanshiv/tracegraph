import { apiClient, unwrap } from './client';
import type { TimelineResult, EvidenceDetail } from '../types';

export const timelineApi = {
  getTimeline: async (
    investigationId: string,
    params?: {
      start_time?: string;
      end_time?: string;
      entity_id?: string;
      event_type?: string;
      severity?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<TimelineResult> => {
    const { data } = await apiClient.get(
      `/api/investigations/${investigationId}/timeline`,
      { params }
    );
    return unwrap(data);
  },

  getEvidence: async (
    investigationId: string,
    eventId: string
  ): Promise<EvidenceDetail> => {
    const { data } = await apiClient.get(
      `/api/investigations/${investigationId}/events/${eventId}`
    );
    return unwrap(data);
  },
};
