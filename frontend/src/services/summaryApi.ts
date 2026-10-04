import { apiClient, unwrap } from './client';
import type { SummaryResult } from '../types';

export const summaryApi = {
  generate: async (
    investigationId: string,
    forceRefresh = false
  ): Promise<SummaryResult> => {
    const { data } = await apiClient.post(
      `/api/investigations/${investigationId}/summary`,
      null,
      { params: { force_refresh: forceRefresh } }
    );
    return unwrap(data);
  },

  get: async (investigationId: string): Promise<SummaryResult> => {
    const { data } = await apiClient.get(
      `/api/investigations/${investigationId}/summary`
    );
    return unwrap(data);
  },
};
