import { apiClient } from './apiClient';
import { SuccessResponse, InvestigationNote } from '../types';

export const notesApi = {
  list: async (investigationId: string): Promise<SuccessResponse<InvestigationNote[]>> => {
    return apiClient.get(`/investigations/${investigationId}/notes`);
  },

  create: async (investigationId: string, body: string): Promise<SuccessResponse<InvestigationNote>> => {
    return apiClient.post(`/investigations/${investigationId}/notes`, { body });
  },
};
