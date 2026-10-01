import { apiClient } from './apiClient';
import { SuccessResponse, GraphResult, Entity } from '../types';

export const graphApi = {
  getGraph: async (
    investigationId: string, 
    params?: { 
      entity_type?: string; 
      relationship_type?: string; 
      start_time?: string; 
      end_time?: string; 
    }
  ): Promise<SuccessResponse<GraphResult>> => {
    return apiClient.get(`/investigations/${investigationId}/graph`, { params });
  },

  pivot: async (
    investigationId: string, 
    entityId: string, 
    hops: number = 1
  ): Promise<SuccessResponse<GraphResult>> => {
    return apiClient.get(`/investigations/${investigationId}/graph/pivot`, { 
      params: { entity_id: entityId, hops } 
    });
  },

  getEntity: async (
    investigationId: string, 
    entityId: string
  ): Promise<SuccessResponse<Entity>> => {
    return apiClient.get(`/investigations/${investigationId}/entities/${entityId}`);
  },
};
