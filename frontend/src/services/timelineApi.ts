import { apiClient } from './apiClient';
import { SuccessResponse, TimelineResult } from '../types';

export const timelineApi = {
  getTimeline: async (
    investigationId: string, 
    params?: { 
      start_time?: string; 
      end_time?: string; 
      entity_id?: string; 
      event_type?: string; 
      severity?: string; 
    }
  ): Promise<SuccessResponse<TimelineResult>> => {
    return apiClient.get(`/investigations/${investigationId}/timeline`, { params });
  },
};
