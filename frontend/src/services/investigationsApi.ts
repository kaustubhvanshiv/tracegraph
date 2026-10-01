import { apiClient } from './apiClient';
import { 
  SuccessResponse, 
  Investigation, 
  InvestigationNote, 
  InvestigationStatus,
  InvestigationOutcome
} from '../types';

export const investigationsApi = {
  list: async (limit = 50, offset = 0): Promise<SuccessResponse<Investigation[]>> => {
    return apiClient.get(`/investigations`, { params: { limit, offset } });
  },

  get: async (id: string): Promise<SuccessResponse<Investigation>> => {
    return apiClient.get(`/investigations/${id}`);
  },

  create: async (payload: { title: string; description: string }): Promise<SuccessResponse<Investigation>> => {
    return apiClient.post(`/investigations`, payload);
  },

  updateStatus: async (
    id: string, 
    status: InvestigationStatus, 
    outcome?: InvestigationOutcome
  ): Promise<SuccessResponse<Investigation>> => {
    return apiClient.patch(`/investigations/${id}`, { status, outcome });
  },

  getNotes: async (id: string): Promise<SuccessResponse<InvestigationNote[]>> => {
    return apiClient.get(`/investigations/${id}/notes`);
  },

  addNote: async (id: string, content: string): Promise<SuccessResponse<InvestigationNote>> => {
    return apiClient.post(`/investigations/${id}/notes`, { content });
  },
};
