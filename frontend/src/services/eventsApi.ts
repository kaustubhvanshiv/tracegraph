import { apiClient } from './apiClient';
import { SuccessResponse, EvidenceDetail } from '../types';

export const eventsApi = {
  getEvidence: async (investigationId: string, eventId: string): Promise<SuccessResponse<EvidenceDetail>> => {
    return apiClient.get(`/investigations/${investigationId}/events/${eventId}`);
  },
  
  // Note: Batch ingestion and other event routes exist, but the frontend primarily needs GET for evidence detail.
};
