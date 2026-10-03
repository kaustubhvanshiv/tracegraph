import { apiClient, unwrap } from './client';
import type { Note, NotePayload } from '../types';

export const notesApi = {
  list: async (investigationId: string): Promise<Note[]> => {
    const { data } = await apiClient.get(`/api/investigations/${investigationId}/notes`);
    return unwrap(data);
  },

  create: async (investigationId: string, payload: NotePayload): Promise<Note> => {
    const { data } = await apiClient.post(`/api/investigations/${investigationId}/notes`, payload);
    return unwrap(data);
  },
};
