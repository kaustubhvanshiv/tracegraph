import { apiClient, unwrap } from './client';
import type {
  Investigation,
  Note,
  CreateInvestigationPayload,
  PatchInvestigationPayload,
  NotePayload,
  InvestigationStatus,
} from '../types';

export const investigationsApi = {
  list: async (params?: {
    status?: InvestigationStatus;
    limit?: number;
    offset?: number;
  }): Promise<Investigation[]> => {
    const { data } = await apiClient.get('/api/investigations', { params });
    return unwrap(data);
  },

  get: async (id: string): Promise<Investigation> => {
    const { data } = await apiClient.get(`/api/investigations/${id}`);
    return unwrap(data);
  },

  create: async (payload: CreateInvestigationPayload): Promise<Investigation> => {
    const { data } = await apiClient.post('/api/investigations', payload);
    return unwrap(data);
  },

  patch: async (id: string, payload: PatchInvestigationPayload): Promise<Investigation> => {
    const { data } = await apiClient.patch(`/api/investigations/${id}`, payload);
    return unwrap(data);
  },

  getNotes: async (id: string): Promise<Note[]> => {
    const { data } = await apiClient.get(`/api/investigations/${id}/notes`);
    return unwrap(data);
  },

  addNote: async (id: string, payload: NotePayload): Promise<Note> => {
    const { data } = await apiClient.post(`/api/investigations/${id}/notes`, payload);
    return unwrap(data);
  },
};
