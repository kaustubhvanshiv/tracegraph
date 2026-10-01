import { apiClient } from './apiClient';
import { SuccessResponse, SummaryResult } from '../types';

export const summaryApi = {
  getSummary: async (investigationId: string): Promise<SuccessResponse<SummaryResult>> => {
    return apiClient.get(`/investigations/${investigationId}/summary`);
  },

  generateSummary: async (
    investigationId: string, 
    forceRefresh: boolean = false
  ): Promise<SuccessResponse<SummaryResult>> => {
    return apiClient.post(`/investigations/${investigationId}/summary`, null, {
      params: { force_refresh: forceRefresh }
    });
  },
};
